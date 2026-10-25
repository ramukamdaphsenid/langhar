"""Persistent local state management for incremental Tally synchronization."""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from config.settings import settings
from src.utils.logger import logger


class SyncStateManager:
    """Manages reading and writing `.sync_state.json` to maintain incremental sync state.

    An in-memory cache (``_cache``) is populated on first read and kept in sync
    with every write, so multiple accessors within a single sync cycle do not
    incur repeated disk I/O.
    """

    _DEFAULT_STATE: Dict[str, Any] = {
        "last_alter_id": 0,
        "last_sync_timestamp": None,
        "total_vouchers_synced": 0,
        "last_status": "NEVER_RUN",
        "last_error": None,
        "synced_company_name": None,
    }

    def __init__(self, state_file: Optional[Path] = None):
        self.state_file = state_file or settings.sync.state_file
        self._cache: Optional[Dict[str, Any]] = None

    def load_state(self) -> Dict[str, Any]:
        """Loads sync state dictionary, using in-memory cache when available."""
        if self._cache is not None:
            return self._cache

        if not self.state_file.exists() or self.state_file.is_dir():
            if self.state_file.is_dir():
                logger.warning(f"State file path '{self.state_file}' is a directory instead of a file. Using default in-memory state.")
            self._cache = dict(self._DEFAULT_STATE)
            return self._cache

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                self._cache = json.load(f)
        except Exception as e:
            logger.warning(f"Could not read state file ({e}). Starting with clean state.")
            self._cache = {
                **self._DEFAULT_STATE,
                "last_status": "STATE_READ_ERROR",
                "last_error": str(e),
            }
        return self._cache

    def save_state(self, state: Dict[str, Any]) -> None:
        """Persists sync state dictionary to disk and updates in-memory cache."""
        self._cache = state
        if self.state_file.is_dir():
            logger.error(f"Cannot persist state: {self.state_file} is a directory.")
            return

        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to persist state file to {self.state_file}: {e}")

    def get_last_alter_id(self, company_name: Optional[str] = None) -> int:
        """Retrieves the highest AlterID synchronized so far, guarded by target company."""
        state = self.load_state()
        recorded_comp = state.get("synced_company_name")
        if company_name and recorded_comp:
            from src.utils.company_helper import verify_company_match
            is_match, _ = verify_company_match(recorded_comp, company_name)
            if not is_match:
                logger.warning(
                    f"[STATE] AlterID state was recorded for company '{recorded_comp}', "
                    f"but requested company is '{company_name}'. Resetting AlterID to 0 to prevent cross-company sequence corruption."
                )
                return 0
        return int(state.get("last_alter_id", 0))

    def record_sync_success(self, new_alter_id: int, count_synced: int, company_name: Optional[str] = None) -> None:
        """Updates state upon successful voucher sync."""
        state = self.load_state()
        state["last_alter_id"] = max(state.get("last_alter_id", 0), new_alter_id)
        state["last_sync_timestamp"] = datetime.now(timezone.utc).isoformat()
        state["total_vouchers_synced"] = state.get("total_vouchers_synced", 0) + count_synced
        state["last_status"] = "SUCCESS"
        state["last_error"] = None
        if company_name:
            state["synced_company_name"] = company_name
        self.save_state(state)

    def record_sync_failure(self, error_message: str) -> None:
        """Updates state upon sync failure."""
        state = self.load_state()
        state["last_sync_timestamp"] = datetime.now(timezone.utc).isoformat()
        state["last_status"] = "FAILED"
        state["last_error"] = error_message
        self.save_state(state)

    def reset(self) -> None:
        """Resets the state file and in-memory cache to trigger a clean full re-sync."""
        self._cache = None
        if self.state_file.exists():
            self.state_file.unlink()
        logger.info("Sync state has been reset to defaults.")
