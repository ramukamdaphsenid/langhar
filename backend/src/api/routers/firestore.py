"""Firestore management endpoints: clear collection and cleanup duplicates."""
from typing import Optional

from fastapi import APIRouter, HTTPException
from src.firebase.client import FirebaseClient
from src.sync.state import SyncStateManager
from src.utils.logger import logger

router = APIRouter()


@router.post("/api/firestore/clear")
def clear_firestore_data(company_name: Optional[str] = None):
    """Deletes all sales vouchers from Firestore and resets AlterID watermark to 0."""
    try:
        firebase = FirebaseClient()
        deleted_count = firebase.clear_all_vouchers(company_name=company_name)
        # Also reset sync state watermark so subsequent sync pulls from scratch cleanly
        state_mgr = SyncStateManager()
        state_mgr.reset()
        logger.info(f"[FIRESTORE CLEAR] Cleared {deleted_count} voucher(s) from Firestore and reset watermark.")
        return {
            "status": "SUCCESS",
            "deleted_count": deleted_count,
            "message": f"Successfully deleted {deleted_count} voucher(s) from Firestore and reset sync watermark to #0."
        }
    except Exception as e:
        logger.error(f"[FIRESTORE CLEAR] Failed to clear Firestore: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to clear Firestore data: {e}")


@router.post("/api/firestore/cleanup")
def cleanup_firestore_duplicates(company_name: Optional[str] = None):
    """Scans Firestore collection, removes non-allowed voucher types and duplicate records."""
    try:
        firebase = FirebaseClient()
        stats = firebase.cleanup_redundant_and_duplicate_vouchers(company_name=company_name)
        # Checkpoint sync state total synced count with remaining clean count
        try:
            state_mgr = SyncStateManager()
            state = state_mgr.load_state()
            state["total_vouchers_synced"] = stats["remaining"]
            state_mgr.save_state(state)
        except Exception:
            pass

        logger.info(f"[FIRESTORE CLEANUP] Finished: {stats}")
        return {
            "status": "SUCCESS",
            "message": (
                f"Cleanup complete: removed {stats['total_deleted']} redundant/duplicate vouchers "
                f"({stats['deleted_non_allowed']} non-allowed types, {stats['deleted_duplicates']} duplicates). "
                f"{stats['remaining']} clean vouchers retained."
            ),
            "details": stats
        }
    except Exception as e:
        logger.error(f"[FIRESTORE CLEANUP] Failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to cleanup Firestore duplicates: {e}")
