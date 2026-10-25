"""Core Synchronization Engine coordinating Tally extraction and Firebase loading."""
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from config.settings import settings
from src.firebase.client import FirebaseClient
from src.sync.state import SyncStateManager
from src.tally.client import TallyClient
from src.tally.odbc_client import TallyODBCClient
from src.utils.company_helper import get_target_company_name, verify_company_match
from src.utils.logger import console, logger


class SyncEngine:
    """Orchestrates extraction from Tally and loading into Firestore."""

    def __init__(
        self,
        tally_client: Optional[TallyClient] = None,
        firebase_client: Optional[FirebaseClient] = None,
        state_manager: Optional[SyncStateManager] = None,
        company: Optional[str] = None,
    ):
        # An explicitly injected client always takes priority (enables testing/mocking).
        # Only fall back to settings-driven auto-selection when no client is provided.
        self.company = company
        if tally_client is not None:
            self.tally = tally_client
        elif settings.tally.use_odbc:
            logger.info("Operating in Tally ODBC Mode.")
            self.tally = TallyODBCClient()
        else:
            self.tally = TallyClient(company=self.company)

        self.firebase = firebase_client or FirebaseClient()
        self.state_manager = state_manager or SyncStateManager()

    def run_sync(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        full_resync: bool = False
    ) -> Dict[str, Any]:
        """Executes a single synchronization cycle.

        Args:
            from_date: Optional start date filter (YYYYMMDD or YYYY-MM-DD)
            to_date: Optional end date filter (YYYYMMDD or YYYY-MM-DD)
            full_resync: If True, ignores previous AlterID state and pulls all vouchers matching range.
        """
        start_time = time.time()
        start_iso = datetime.now(timezone.utc).isoformat()
        logger.info(f"--- Starting Sales Voucher Sync Cycle at {start_iso} ---")

        # Resolve intended target company
        target_company = self.company or get_target_company_name()

        # Guard: Check active company in Tally to prevent syncing wrong company datasets
        active_company = None
        try:
            if hasattr(self.tally, "get_active_company"):
                active_company = self.tally.get_active_company()
        except Exception as e:
            logger.debug(f"Could not retrieve active company from Tally: {e}")

        if active_company:
            is_match, mismatch_reason = verify_company_match(active_company, target_company)
            if not is_match and target_company:
                err_msg = (
                    f"Security Guard: Active company in Tally Prime ('{active_company}') does NOT match "
                    f"the configured target company ('{target_company}'). Sync blocked to prevent syncing wrong company data. "
                    f"Please switch to '{target_company}' in Tally Prime."
                )
                logger.error(err_msg)
                self.state_manager.record_sync_failure(err_msg)
                return {
                    "status": "FAILED",
                    "error": err_msg,
                    "synced_count": 0,
                    "active_company": active_company,
                    "target_company": target_company,
                    "duration_seconds": round(time.time() - start_time, 2),
                }
            elif not target_company:
                target_company = active_company
                logger.info(f"Target company auto-detected from Tally Prime: '{target_company}'")

        # Format dates if passed as YYYY-MM-DD into YYYYMMDD for Tally
        tally_from_date = from_date.replace("-", "") if from_date else None
        tally_to_date = to_date.replace("-", "") if to_date else None

        # Determine starting AlterID (guarded by company)
        if full_resync or tally_from_date or tally_to_date:
            last_alter_id = 0
            logger.info("Full or date-filtered sync requested: AlterID filter reset to 0.")
        else:
            last_alter_id = self.state_manager.get_last_alter_id(company_name=target_company)
            logger.info(f"Incremental sync: Checking for vouchers altered after AlterID: {last_alter_id}")

        try:
            # 1. Fetch vouchers from Tally
            vouchers = self.tally.fetch_sales_vouchers(
                from_date=tally_from_date,
                to_date=tally_to_date,
                from_alter_id=last_alter_id,
                company=target_company
            )

            if not vouchers:
                logger.info(f"No new or modified sales vouchers found in Tally for '{target_company or 'Active'}'.")
                duration = round(time.time() - start_time, 2)
                self.state_manager.record_sync_success(last_alter_id, 0, company_name=target_company)
                return {
                    "status": "SUCCESS",
                    "synced_count": 0,
                    "max_alter_id": last_alter_id,
                    "company_name": target_company,
                    "duration_seconds": duration,
                }

            # Stamp each voucher with the verified company name and deduplicate
            dedup_map: Dict[str, Dict[str, Any]] = {}
            for v in vouchers:
                if not v.get("company_name"):
                    v["company_name"] = target_company or active_company or ""
                doc_id = v.get("doc_id") or ""
                v_num = str(v.get("voucher_number") or "").strip().lower()
                v_type = str(v.get("voucher_type") or "").strip().upper()
                c_name = str(v.get("company_name") or "").strip().lower()
                v_date = str(v.get("date") or "").strip()
                k = f"{c_name}::{v_type}::{v_num}::{v_date}" if v_num else doc_id
                if k not in dedup_map or int(v.get("alter_id") or 0) >= int(dedup_map[k].get("alter_id") or 0):
                    dedup_map[k] = v

            vouchers = list(dedup_map.values())
            logger.info(f"Found {len(vouchers)} unique voucher(s) for company '{target_company or 'Active'}' to sync to Firestore.")

            # 2. Push to Firestore with incremental state checkpointing per batch
            committed_alter_id = last_alter_id
            committed_count = 0

            def on_batch_commit(chunk: list, total_so_far: int):
                nonlocal committed_alter_id, committed_count
                chunk_max_alter = max((v.get("alter_id", 0) for v in chunk), default=committed_alter_id)
                committed_alter_id = max(committed_alter_id, chunk_max_alter)
                committed_count = total_so_far
                # Checkpoint state to disk/cache with company name
                self.state_manager.record_sync_success(committed_alter_id, len(chunk), company_name=target_company)

            try:
                synced_count = self.firebase.upsert_vouchers(
                    vouchers,
                    batch_size=settings.sync.batch_size,
                    on_batch_success=on_batch_commit
                )
            except Exception as batch_exc:
                logger.error(
                    f"Sync partially succeeded before failing: {committed_count}/{len(vouchers)} "
                    f"vouchers committed up to AlterID {committed_alter_id}."
                )
                raise batch_exc

            duration = round(time.time() - start_time, 2)
            logger.info(
                f"[green]Sync completed successfully![/green] Synced {synced_count} voucher(s) "
                f"in {duration}s. New Max AlterID: {committed_alter_id}"
            )

            return {
                "status": "SUCCESS",
                "synced_count": synced_count,
                "max_alter_id": committed_alter_id,
                "duration_seconds": duration,
            }

        except Exception as e:
            logger.error(f"[red]Sync failed with error:[/red] {e}", exc_info=True)
            self.state_manager.record_sync_failure(str(e))
            duration = round(time.time() - start_time, 2)
            return {
                "status": "FAILED",
                "error": str(e),
                "synced_count": 0,
                "duration_seconds": duration,
            }

    def start_daemon(self, interval_seconds: Optional[int] = None) -> None:
        """Runs the sync process continuously on a recurring schedule."""
        import signal
        try:
            import schedule
        except ImportError:
            raise ImportError("The 'schedule' library is required to run the CLI daemon. Please run: pip install schedule")

        interval = interval_seconds or settings.sync.interval_seconds
        console.rule("[bold cyan]Tally Prime -> Firebase Sync Daemon Started[/bold cyan]")
        console.print(f"[dim]Sync interval set to: every {interval} seconds.[/dim]")
        console.print("[yellow]Press Ctrl+C or send SIGTERM to terminate daemon at any time.[/yellow]\n")

        running = True

        def handle_shutdown(signum, frame):
            nonlocal running
            running = False
            console.print("\n[bold yellow]Daemon received termination signal. Exiting cleanly...[/bold yellow]")

        # Register termination signal handlers
        signal.signal(signal.SIGINT, handle_shutdown)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, handle_shutdown)

        # Run immediate first sync
        self.run_sync()

        # Schedule recurring job
        schedule.every(interval).seconds.do(self.run_sync)

        while running:
            schedule.run_pending()
            time.sleep(1)
