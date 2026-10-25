"""System-level API endpoints: health, status and diagnostics."""
from datetime import datetime, timezone
import time

from fastapi import APIRouter
from config.settings import settings
from src.api import runtime
from src.firebase.client import FirebaseClient
from src.sync.state import SyncStateManager
from src.tally.client import TallyClient
from src.tally.odbc_client import TallyODBCClient
from src.utils.company_helper import get_target_company_name, verify_company_match
from src.utils.logger import logger

router = APIRouter()


@router.get("/api/health")
def api_health():
    """Simple API health check."""
    return {"status": "ok", "service": "tally-firebase-sync-api", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/api/status")
def get_status():
    """Fetch current synchronization status, state, daemon state, and configuration (non-blocking)."""
    state_mgr = SyncStateManager()
    state = state_mgr.load_state()

    # Calculate countdown
    next_countdown = None
    if runtime.daemon_manager.is_running and runtime.daemon_manager.next_run_epoch:
        rem = int(runtime.daemon_manager.next_run_epoch - time.time())
        next_countdown = max(0, rem)

    tally_target = f"ODBC DSN: {settings.tally.odbc_dsn}" if settings.tally.use_odbc else f"{settings.tally.url} (XML API)"

    target_company = get_target_company_name()
    active_tally_company = runtime._last_known_tally_company
    company_match_ok = runtime._last_known_company_match
    company_match_msg = runtime._last_known_company_msg

    if active_tally_company and target_company:
        company_match_ok, company_match_msg = verify_company_match(active_tally_company, target_company)

    return {
        "is_syncing": runtime.is_syncing,
        "state": {
            "last_alter_id": state.get("last_alter_id", 0),
            "last_sync_timestamp": state.get("last_sync_timestamp"),
            "total_vouchers_synced": state.get("total_vouchers_synced", 0),
            "last_status": state.get("last_status", "NEVER_RUN"),
            "last_error": state.get("last_error"),
            "synced_company_name": state.get("synced_company_name"),
            "state_file": str(state_mgr.state_file.resolve()),
        },
        "daemon": {
            "is_running": runtime.daemon_manager.is_running,
            "interval_seconds": runtime.daemon_manager.interval,
            "last_run": runtime.daemon_manager.last_run_timestamp,
            "next_countdown_seconds": next_countdown,
        },
        "last_sync_result": runtime.last_sync_result,
        "config": {
            "tally_url": settings.tally.url,
            "tally_target": tally_target,
            "tally_company": target_company or "Current Active Company",
            "target_company": target_company,
            "active_tally_company": active_tally_company,
            "company_match_ok": company_match_ok,
            "company_match_message": company_match_msg,
            "tally_use_odbc": settings.tally.use_odbc,
            "firebase_collection": settings.firebase.collection_name,
            "credentials_path": str(settings.firebase.credentials_path),
            "credentials_exists": settings.firebase.credentials_path.exists(),
        }
    }


@router.get("/api/check")
def check_connections():
    """Perform live diagnostic health check for Tally and Firebase."""
    runtime._last_known_tally_company = None
    runtime._last_known_company_match = None
    runtime._last_known_company_msg = None

    # 1. Tally check
    target_comp = get_target_company_name()
    if settings.tally.use_odbc:
        tally = TallyODBCClient()
        target = f"ODBC DSN: {settings.tally.odbc_dsn}"
    else:
        tally = TallyClient(company=target_comp)
        target = f"{tally.url} (XML API)"

    tally_ok, tally_msg = tally.check_connection()
    if tally_ok:
        try:
            active_c = tally.get_active_company()
            if active_c:
                runtime._last_known_tally_company = active_c
                runtime._last_known_company_match, runtime._last_known_company_msg = verify_company_match(active_c, target_comp)
        except Exception:
            pass

    # 2. Firebase check
    firebase = FirebaseClient()
    fb_target = f"Collection: {settings.firebase.collection_name}"
    fb_ok, fb_msg = firebase.check_connection()

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tally": {
            "ok": tally_ok,
            "message": tally_msg,
            "target": target,
            "instructions": None if tally_ok else "Ensure Tally Prime is running with Server/ODBC enabled on port 9000."
        },
        "firebase": {
            "ok": fb_ok,
            "message": fb_msg,
            "target": fb_target,
            "credentials_found": settings.firebase.credentials_path.exists(),
            "instructions": None if fb_ok else f"Place your valid serviceAccountKey.json at {settings.firebase.credentials_path.resolve()}."
        }
    }


