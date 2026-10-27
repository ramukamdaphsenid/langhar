"""Voucher retrieval endpoint for live Tally data."""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from config.settings import settings
from src.tally.client import TallyClient
from src.tally.odbc_client import TallyODBCClient
from src.tally.queries import VOUCHER_SCREEN_TYPES
from src.utils.active_company import require_active_company
from src.utils.company_helper import verify_company_match
from src.utils.logger import logger

router = APIRouter()


@router.get("/api/vouchers")
def get_vouchers(
    limit: Optional[int] = None,
    search: Optional[str] = None,
    company_id: Optional[str] = None,
):
    """Retrieve vouchers from live Tally for its currently active company."""
    try:
        company = require_active_company(company_id)
    except RuntimeError as error:
        status_code = 409 if company_id and "changed" in str(error).lower() else 503
        raise HTTPException(status_code=status_code, detail=str(error))

    vouchers: List[Dict[str, Any]] = []
    company_id = company["company_id"]
    target_comp = company["company_name"]

    tally = TallyClient(company=target_comp)
    if not tally.is_available():
        raise HTTPException(status_code=503, detail="Tally Prime is not reachable. Open Tally and retry.")

    verifier = TallyODBCClient() if settings.tally.use_odbc else tally
    active_company = verifier.get_active_company()
    if not active_company:
        raise HTTPException(status_code=503, detail="Tally is reachable, but its active company could not be verified.")
    if not verify_company_match(active_company, target_comp)[0]:
        raise HTTPException(status_code=409, detail="Tally's active company changed. Refresh and try again.")

    try:
        vouchers = tally.fetch_vouchers(
            company=target_comp,
            voucher_types=VOUCHER_SCREEN_TYPES,
        )
        active_after_export = verifier.get_active_company()
        if not active_after_export or not verify_company_match(active_after_export, target_comp)[0]:
            raise HTTPException(status_code=409, detail="Tally's active company changed during voucher loading.")
    except HTTPException:
        raise
    except Exception as error:
        logger.error(f"[VOUCHERS] Direct Tally query failed for '{target_comp}': {error}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Could not load vouchers directly from Tally Prime: {error}") from error

    for voucher in vouchers:
        voucher["company_id"] = company_id
    logger.info(f"[VOUCHERS] Loaded {len(vouchers)} live vouchers from Tally Prime (Company: {target_comp}).")

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
    paginated = vouchers[:limit] if limit and limit > 0 else vouchers

    return {
        "source": "live",
        "total": total_count,
        "returned": len(paginated),
        "vouchers": paginated
    }
