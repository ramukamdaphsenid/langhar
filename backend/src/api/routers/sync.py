"""Synchronization control endpoints: manual sync trigger, daemon control, state reset."""
from fastapi import APIRouter, BackgroundTasks, HTTPException
from src.api import runtime
from src.api.schemas import DaemonStartRequest, SyncRequest
from src.sync.engine import SyncEngine
from src.sync.state import SyncStateManager
from src.utils.logger import logger

router = APIRouter()


def _execute_sync_worker(req: SyncRequest):
    try:
        runtime.is_syncing = True
        logger.info(f"[MANUAL SYNC] Initiated (from_date={req.from_date}, to_date={req.to_date}, full={req.full})")
        engine = SyncEngine()
        result = engine.run_sync(from_date=req.from_date, to_date=req.to_date, full_resync=req.full)
        runtime.last_sync_result = result
        logger.info(f"[MANUAL SYNC] Completed: {result.get('status')} - Synced {result.get('synced_count', 0)} vouchers.")
    except Exception as e:
        logger.error(f"[MANUAL SYNC] Execution failed: {e}")
        runtime.last_sync_result = {"status": "FAILED", "error": str(e), "synced_count": 0}
    finally:
        runtime.is_syncing = False
        runtime.sync_lock.release()


@router.post("/api/sync")
def trigger_sync(req: SyncRequest = SyncRequest(), background_tasks: BackgroundTasks = None, async_run: bool = False):
    """Trigger an immediate synchronization run (sync or async non-blocking)."""
    if not runtime.sync_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A synchronization run is already actively in progress.")

    if async_run and background_tasks:
        runtime.is_syncing = True
        background_tasks.add_task(_execute_sync_worker, req)
        return {
            "status": "ACCEPTED",
            "message": "Sync run dispatched in background. Track progress via /api/status.",
            "is_syncing": True
        }

    try:
        _execute_sync_worker(req)
        return runtime.last_sync_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/daemon/start")
def start_daemon(req: DaemonStartRequest = DaemonStartRequest()):
    """Start background sync daemon."""
    runtime.daemon_manager.start(interval=req.interval)
    return {
        "status": "started",
        "is_running": runtime.daemon_manager.is_running,
        "interval_seconds": runtime.daemon_manager.interval
    }


@router.post("/api/daemon/stop")
def stop_daemon():
    """Stop background sync daemon."""
    runtime.daemon_manager.stop()
    return {
        "status": "stopped",
        "is_running": runtime.daemon_manager.is_running
    }


@router.post("/api/state/reset")
def reset_sync_state():
    """Reset the sync state tracking file to start clean on next sync."""
    state_mgr = SyncStateManager()
    state_mgr.reset()
    logger.info("[STATE RESET] State reset via API.")
    return {"status": "SUCCESS", "message": "Sync state reset successfully. Next sync will perform a full pull."}
