"""FastAPI REST API server for Tally to Firebase Sync UI."""
import asyncio
from collections import deque
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import threading
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field

from config.settings import settings
from src.firebase.client import FirebaseClient
from src.sync.engine import SyncEngine
from src.sync.state import SyncStateManager
from src.tally.client import TallyClient
from src.tally.odbc_client import TallyODBCClient
from src.tally.parser import parse_tally_vouchers_xml
from src.utils.logger import logger

# In-memory log capture buffer for UI live log streaming
log_buffer: deque = deque(maxlen=250)
log_buffer_lock = threading.Lock()

class BufferLogHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            with log_buffer_lock:
                log_buffer.append({
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "level": record.levelname,
                    "message": msg
                })
        except Exception:
            pass

# Attach buffer handler to logger
buffer_handler = BufferLogHandler()
buffer_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
logger.addHandler(buffer_handler)
logging.getLogger("uvicorn.error").addHandler(buffer_handler)

app = FastAPI(
    title="Langhar Enterprise Rice Platform - Tally Sync API",
    version="1.0.0",
    description="REST API controlling Langhar's Tally Prime to Firebase Firestore synchronization."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Concurrency & daemon controller
sync_lock = threading.Lock()
is_syncing = False
last_sync_result: Optional[Dict[str, Any]] = None

class DaemonState:
    def __init__(self):
        self.is_running = False
        self.interval = settings.sync.interval_seconds
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.last_run_timestamp: Optional[str] = None
        self.next_run_epoch: Optional[float] = None

    def worker(self):
        logger.info(f"[DAEMON] Background sync worker started (interval: {self.interval}s)")
        engine = SyncEngine()
        while not self.stop_event.is_set():
            self.last_run_timestamp = datetime.now(timezone.utc).isoformat()
            self.next_run_epoch = time.time() + self.interval

            global is_syncing, last_sync_result
            if sync_lock.acquire(blocking=False):
                try:
                    is_syncing = True
                    logger.info("[DAEMON] Running scheduled sync cycle...")
                    result = engine.run_sync()
                    last_sync_result = result
                    logger.info(f"[DAEMON] Cycle finished: {result.get('status')} - Synced {result.get('synced_count', 0)} vouchers.")
                except Exception as e:
                    logger.error(f"[DAEMON] Error during sync run: {e}")
                    last_sync_result = {"status": "FAILED", "error": str(e), "synced_count": 0}
                finally:
                    is_syncing = False
                    sync_lock.release()
            else:
                logger.warning("[DAEMON] Previous sync still active, skipping tick.")

            # Sleep in 1s increments to allow fast stop
            for _ in range(self.interval):
                if self.stop_event.is_set():
                    break
                time.sleep(1)

        self.is_running = False
        self.next_run_epoch = None
        logger.info("[DAEMON] Background sync worker stopped.")

    def start(self, interval: Optional[int] = None):
        if self.is_running:
            return
        if interval and interval > 0:
            self.interval = interval
        self.stop_event.clear()
        self.is_running = True
        self.thread = threading.Thread(target=self.worker, daemon=True)
        self.thread.start()

    def stop(self):
        if not self.is_running:
            return
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3)
        self.is_running = False

daemon_manager = DaemonState()


# Models
class SyncRequest(BaseModel):
    from_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD or YYYYMMDD)")
    to_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD or YYYYMMDD)")
    full: bool = Field(False, description="Full sync flag, ignores previous AlterID")

class DaemonStartRequest(BaseModel):
    interval: Optional[int] = Field(None, ge=5, le=86400, description="Interval in seconds")


@app.get("/api/health")
def api_health():
    """Simple API health check."""
    return {"status": "ok", "service": "tally-firebase-sync-api", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/status")
def get_status():
    """Fetch current synchronization status, state, daemon state, and configuration."""
    state_mgr = SyncStateManager()
    state = state_mgr.load_state()

    # Calculate countdown
    next_countdown = None
    if daemon_manager.is_running and daemon_manager.next_run_epoch:
        rem = int(daemon_manager.next_run_epoch - time.time())
        next_countdown = max(0, rem)

    tally_target = f"ODBC DSN: {settings.tally.odbc_dsn}" if settings.tally.use_odbc else f"{settings.tally.url} (XML API)"

    return {
        "is_syncing": is_syncing,
        "state": {
            "last_alter_id": state.get("last_alter_id", 0),
            "last_sync_timestamp": state.get("last_sync_timestamp"),
            "total_vouchers_synced": state.get("total_vouchers_synced", 0),
            "last_status": state.get("last_status", "NEVER_RUN"),
            "last_error": state.get("last_error"),
            "state_file": str(state_mgr.state_file.resolve()),
        },
        "daemon": {
            "is_running": daemon_manager.is_running,
            "interval_seconds": daemon_manager.interval,
            "last_run": daemon_manager.last_run_timestamp,
            "next_countdown_seconds": next_countdown,
        },
        "last_sync_result": last_sync_result,
        "config": {
            "tally_url": settings.tally.url,
            "tally_target": tally_target,
            "tally_company": settings.tally.company or "Current Active Company",
            "tally_use_odbc": settings.tally.use_odbc,
            "firebase_collection": settings.firebase.collection_name,
            "credentials_path": str(settings.firebase.credentials_path),
            "credentials_exists": settings.firebase.credentials_path.exists(),
        }
    }


@app.get("/api/check")
def check_connections():
    """Perform live diagnostic health check for Tally and Firebase."""
    # 1. Tally check
    if settings.tally.use_odbc:
        tally = TallyODBCClient()
        target = f"ODBC DSN: {settings.tally.odbc_dsn}"
    else:
        tally = TallyClient()
        target = f"{tally.url} (XML API)"

    tally_ok, tally_msg = tally.check_connection()

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


def _execute_sync_worker(req: SyncRequest):
    global is_syncing, last_sync_result
    try:
        is_syncing = True
        logger.info(f"[MANUAL SYNC] Initiated (from_date={req.from_date}, to_date={req.to_date}, full={req.full})")
        engine = SyncEngine()
        result = engine.run_sync(from_date=req.from_date, to_date=req.to_date, full_resync=req.full)
        last_sync_result = result
        logger.info(f"[MANUAL SYNC] Completed: {result.get('status')} - Synced {result.get('synced_count', 0)}")
    except Exception as e:
        logger.error(f"[MANUAL SYNC] Execution failed: {e}")
        last_sync_result = {"status": "FAILED", "error": str(e), "synced_count": 0}
    finally:
        is_syncing = False
        sync_lock.release()

@app.post("/api/sync")
def trigger_sync(req: SyncRequest = SyncRequest(), background_tasks: BackgroundTasks = None, async_run: bool = False):
    """Trigger an immediate synchronization run (sync or async non-blocking)."""
    global is_syncing, last_sync_result

    if not sync_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A synchronization run is already actively in progress.")

    if async_run and background_tasks:
        is_syncing = True
        background_tasks.add_task(_execute_sync_worker, req)
        return {
            "status": "ACCEPTED",
            "message": "Sync run dispatched in background. Track progress via /api/status and /api/logs.",
            "is_syncing": True
        }

    try:
        _execute_sync_worker(req)
        return last_sync_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/api/daemon/start")
def start_daemon(req: DaemonStartRequest = DaemonStartRequest()):
    """Start background sync daemon."""
    daemon_manager.start(interval=req.interval)
    return {
        "status": "started",
        "is_running": daemon_manager.is_running,
        "interval_seconds": daemon_manager.interval
    }


@app.post("/api/daemon/stop")
def stop_daemon():
    """Stop background sync daemon."""
    daemon_manager.stop()
    return {
        "status": "stopped",
        "is_running": daemon_manager.is_running
    }


@app.post("/api/state/reset")
def reset_sync_state():
    """Reset the sync state tracking file to start clean on next sync."""
    state_mgr = SyncStateManager()
    state_mgr.reset()
    logger.info("[STATE RESET] State reset via API.")
    return {"status": "SUCCESS", "message": "Sync state reset successfully. Next sync will perform a full pull."}


@app.get("/api/vouchers/sample")
def get_sample_vouchers(limit: int = 50, search: Optional[str] = None, source_pref: Optional[str] = None):
    """Retrieve vouchers for preview (from live Tally, Firestore, or mock dataset)."""
    vouchers: List[Dict[str, Any]] = []
    source = "live"

    # 1. If firestore source requested or Tally not directly queryable
    if source_pref == "firestore":
        try:
            fb = FirebaseClient()
            vouchers = fb.get_vouchers(limit=limit)
            source = "firestore"
        except Exception as fb_err:
            logger.warning(f"Failed to fetch vouchers from Firestore: {fb_err}")

    # 2. Try querying Tally if not resolved
    if not vouchers and source != "firestore":
        try:
            if settings.tally.use_odbc:
                tally = TallyODBCClient()
            else:
                tally = TallyClient()
            vouchers = tally.fetch_sales_vouchers()
        except Exception as e:
            # 3. Try Firestore fallback before mock
            try:
                fb = FirebaseClient()
                vouchers = fb.get_vouchers(limit=limit)
                source = "firestore"
            except Exception:
                source = "mock"
                logger.info(f"Could not connect to live Tally ({e}) or Firestore. Reading from mock test file...")
                mock_file = Path("tests/mock_sales_vouchers.xml")
                if mock_file.exists():
                    with open(mock_file, "r", encoding="utf-8") as f:
                        vouchers = parse_tally_vouchers_xml(f.read())
                else:
                    vouchers = []

    # Optional search filtering
    if search:
        s = search.lower()
        vouchers = [
            v for v in vouchers
            if s in str(v.get("voucher_number", "")).lower()
            or s in str(v.get("party_name", "")).lower()
            or s in str(v.get("party", {}).get("name", "")).lower()
            or s in str(v.get("vehicle_number", "")).lower()
            or s in str(v.get("party_gstin", "")).lower()
            or s in str(v.get("guid", "")).lower()
        ]

    total_count = len(vouchers)
    paginated = vouchers[:limit]

    return {
        "source": source,
        "total": total_count,
        "returned": len(paginated),
        "vouchers": paginated
    }


@app.get("/api/logs")
def get_logs(limit: int = 100):
    """Fetch recent execution logs captured in the memory ring buffer."""
    with log_buffer_lock:
        items = list(log_buffer)
    return {
        "count": len(items),
        "logs": items[-limit:]
    }


# ==============================================================================
# Static File & Single-Page Application (SPA) Serving
# Enables running frontend and backend inside a single unified container
# ==============================================================================
static_dir = Path(__file__).resolve().parent / "static"

if static_dir.exists() and (static_dir / "index.html").exists():
    logger.info(f"[SPA] Serving compiled frontend UI from {static_dir}")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        # Don't intercept API endpoints or OpenAPI docs
        if full_path.startswith("api/") or full_path in ("docs", "openapi.json", "redoc"):
            raise HTTPException(status_code=404, detail="Not Found")

        target_file = static_dir / full_path
        if full_path and target_file.is_file():
            return FileResponse(target_file)

        # Fallback to index.html for Angular client-side routing
        return FileResponse(static_dir / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
