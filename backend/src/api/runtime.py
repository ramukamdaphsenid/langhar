"""Shared runtime state and daemon controller for the Langhar API."""
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from config.settings import settings
from src.sync.engine import SyncEngine
from src.utils.company_helper import load_local_company_profile, save_local_company_profile
from src.utils.logger import logger

# Concurrency & daemon controller
sync_lock = threading.Lock()
is_syncing: bool = False
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
        global is_syncing, last_sync_result
        logger.info(f"[DAEMON] Background sync worker started (interval: {self.interval}s)")
        engine = SyncEngine()
        while not self.stop_event.is_set():
            self.last_run_timestamp = datetime.now(timezone.utc).isoformat()
            self.next_run_epoch = time.time() + self.interval

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


_last_known_tally_company: Optional[str] = None
_last_known_company_match: Optional[bool] = None
_last_known_company_msg: Optional[str] = None


def _load_company_profile() -> Dict[str, Any]:
    return load_local_company_profile()


def _save_company_profile(data: Dict[str, Any]) -> None:
    save_local_company_profile(data)
