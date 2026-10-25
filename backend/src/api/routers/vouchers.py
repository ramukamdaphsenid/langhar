"""Voucher retrieval endpoints: sample data preview from live Tally, Firestore or mock."""
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from config.settings import settings
from src.firebase.client import FirebaseClient
from src.sync.state import SyncStateManager
from src.tally.client import TallyClient
from src.tally.odbc_client import TallyODBCClient
from src.tally.parser import is_allowed_voucher_type, parse_tally_vouchers_xml
from src.utils.company_helper import get_target_company_name
from src.utils.logger import logger

router = APIRouter()


@router.get("/api/vouchers/sample")
def get_sample_vouchers(limit: Optional[int] = None, search: Optional[str] = None, source_pref: Optional[str] = None):
    """Retrieve vouchers for preview (from live Tally, Firestore, or mock dataset).
    
    When Tally is disconnected or unreachable, automatically loads data from Firebase Firestore.
    """
    vouchers: List[Dict[str, Any]] = []
    source = "live"
    target_comp = get_target_company_name()

    # If limit is 0 or negative, treat as None (no limit)
    query_limit = limit if (limit is not None and limit > 0) else None

    # 1. If firestore source requested explicitly
    if source_pref == "firestore":
        try:
            fb = FirebaseClient()
            vouchers = fb.get_vouchers(limit=query_limit, company_name=target_comp)
            source = "firestore"
            logger.info(f"[VOUCHERS] Loaded {len(vouchers)} vouchers directly from Firestore for '{target_comp or 'All'}'.")
        except Exception as fb_err:
            logger.warning(f"Failed to fetch vouchers from Firestore: {fb_err}")

    # 2. Try querying Tally if not resolved and not explicitly firestore
    if not vouchers and source != "firestore":
        tally = TallyODBCClient() if settings.tally.use_odbc else TallyClient(company=target_comp)
        is_tally_online = False
        try:
            is_tally_online = tally.is_available()
        except Exception:
            is_tally_online = False

        if is_tally_online and source_pref != "mock":
            try:
                vouchers = tally.fetch_sales_vouchers(company=target_comp)
                source = "live"
                logger.info(f"[VOUCHERS] Loaded {len(vouchers)} live vouchers from Tally Prime (Company: {target_comp or 'Active'}).")
            except Exception as e:
                logger.warning(f"[VOUCHERS] Query to live Tally failed ({e}). Falling back to Firebase Firestore.")
                is_tally_online = False

        # If Tally is disconnected or query failed, load from Firebase Firestore!
        if not vouchers and source_pref != "mock":
            try:
                fb = FirebaseClient()
                vouchers = fb.get_vouchers(limit=query_limit, company_name=target_comp)
                source = "firestore"
                logger.info(
                    f"[VOUCHERS] Tally Prime is disconnected/unreachable. "
                    f"Successfully loaded {len(vouchers)} vouchers from Firebase Firestore for '{target_comp or 'All'}'."
                )
            except Exception as fb_err:
                logger.warning(f"[VOUCHERS] Could not fetch vouchers from Firestore ({fb_err}). Falling back to mock dataset.")

        # If neither Tally nor Firestore could provide vouchers, fallback to mock file
        if not vouchers:
            source = "mock"
            logger.info("Reading vouchers from mock test dataset...")
            mock_file = Path("tests/mock_sales_vouchers.xml")
            if mock_file.exists():
                with open(mock_file, "r", encoding="utf-8") as f:
                    vouchers = parse_tally_vouchers_xml(f.read())
            else:
                vouchers = []

    # Filter strictly for RICE SALES and RICE SALES TAXABLE
    vouchers = [
        v for v in vouchers
        if is_allowed_voucher_type(v.get("voucher_type"))
    ]

    # Optional search filtering
    if search:
        s = search.lower()
        vouchers = [
            v for v in vouchers
            if s in str(v.get("voucher_number", "")).lower()
            or s in str(v.get("party_name", "")).lower()
            or s in str((v.get("party") or {}).get("name", "")).lower()
            or s in str(v.get("vehicle_number", "")).lower()
            or s in str(v.get("party_gstin", "")).lower()
            or s in str(v.get("guid", "")).lower()
        ]

    total_count = len(vouchers)
    if source == "firestore":
        try:
            synced_total = SyncStateManager().load_state().get("total_vouchers_synced", 0)
            if synced_total > total_count:
                total_count = synced_total
        except Exception:
            pass

    paginated = vouchers[:query_limit] if query_limit else vouchers

    return {
        "source": source,
        "total": total_count,
        "returned": len(paginated),
        "vouchers": paginated
    }
