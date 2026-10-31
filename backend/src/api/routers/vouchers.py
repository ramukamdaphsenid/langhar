"""Voucher retrieval endpoint for live Tally data."""
from fastapi import APIRouter, HTTPException
from src.tally.client import TallyClient
from src.tally.queries import VOUCHER_SCREEN_TYPES
from src.utils.logger import logger

router = APIRouter()


@router.get("/api/vouchers")
def get_vouchers():
    """Retrieve vouchers for whichever company is currently active in Tally."""
    tally = TallyClient()
    if not tally.is_available():
        raise HTTPException(status_code=503, detail="Tally Prime is not reachable. Open Tally and retry.")

    try:
        vouchers = tally.fetch_vouchers(
            voucher_types=VOUCHER_SCREEN_TYPES,
        )
    except HTTPException:
        raise
    except Exception as error:
        logger.error(f"[VOUCHERS] Direct Tally query failed: {error}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Could not load vouchers directly from Tally Prime: {error}") from error

    logger.info(f"[VOUCHERS] Loaded {len(vouchers)} live vouchers from the active Tally company.")

    return {
        "source": "live",
        "total": len(vouchers),
        "vouchers": vouchers,
    }
