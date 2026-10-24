"""Firebase Cloud Firestore Client for Sales Voucher Synchronization."""
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_batch import BaseWriteBatch

from config.settings import settings
from src.utils.logger import logger


class FirebaseClient:
    """Manages connection and batch synchronization to Firebase Cloud Firestore."""

    def __init__(self, credentials_path: Optional[Path] = None, collection_name: Optional[str] = None):
        self.credentials_path = credentials_path or settings.firebase.credentials_path
        self.collection_name = collection_name or settings.firebase.collection_name
        self._db = None
        self._app = None

    def initialize(self) -> None:
        """Initializes Firebase Admin SDK using the service account key."""
        if self._db is not None:
            return

        if not self.credentials_path.exists():
            raise FileNotFoundError(
                f"Firebase credentials file not found at: {self.credentials_path.resolve()}\n"
                "Please download your service account key from the Firebase Console:\n"
                "  Project Settings -> Service Accounts -> Generate new private key\n"
                f"and save it as '{self.credentials_path.name}' in the project root."
            )

        try:
            # Check if app is already initialized to avoid duplicate app errors
            if not firebase_admin._apps:
                cred = credentials.Certificate(str(self.credentials_path))
                self._app = firebase_admin.initialize_app(cred)
            else:
                self._app = firebase_admin.get_app()

            self._db = firestore.client()
            logger.debug(f"Firebase Firestore initialized successfully (collection: '{self.collection_name}')")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Firebase Admin SDK: {e}")

    @property
    def db(self):
        """Lazy getter for Firestore client."""
        if self._db is None:
            self.initialize()
        return self._db

    def check_connection(self) -> Tuple[bool, str]:
        """Tests connectivity and permissions against Firestore."""
        try:
            db = self.db
            # Attempt a minimal collection reference read
            col_ref = db.collection(self.collection_name)
            # Fetch at most 1 document to verify connectivity
            list(col_ref.limit(1).stream())
            return True, f"Successfully connected to Firestore (Target collection: '{self.collection_name}')"
        except FileNotFoundError as fnf:
            return False, str(fnf)
        except Exception as e:
            return False, f"Firestore connection test failed: {e}"

    def upsert_vouchers(
        self,
        vouchers: List[Dict[str, Any]],
        batch_size: int = 100,
        on_batch_success: Optional[Any] = None
    ) -> int:
        """Batch upserts normalized vouchers into Firestore.

        Idempotency:
            Uses `doc_id` (derived from Tally GUID or VoucherNumber) as document key.
            Uses `merge=True` so existing documents are updated without overwriting
            custom application fields.

        Args:
            vouchers: List of normalized voucher dictionaries.
            batch_size: Number of items per batch (capped at 450, Firestore limit is 500).
            on_batch_success: Optional callback `fn(chunk_vouchers, total_synced_so_far)` called
                              immediately after each batch is committed.
        """
        if not vouchers:
            return 0

        db = self.db
        col_ref = db.collection(self.collection_name)

        # Firestore limit is 500 writes per batch
        safe_batch_size = max(1, min(batch_size, 450))
        total_synced = 0

        # Chunk vouchers into batches
        for i in range(0, len(vouchers), safe_batch_size):
            chunk = vouchers[i:i + safe_batch_size]
            batch = db.batch()

            for voucher in chunk:
                doc_id = voucher.get("doc_id")
                if not doc_id:
                    continue

                doc_ref = col_ref.document(doc_id)
                # Clone data so we don't mutate input
                data = dict(voucher)
                # Attach server timestamp for auditing
                data["synced_at"] = firestore.SERVER_TIMESTAMP
                data["last_updated"] = datetime.now(timezone.utc).isoformat()

                batch.set(doc_ref, data, merge=True)

            batch.commit()
            total_synced += len(chunk)
            logger.info(f"Committed batch of {len(chunk)} voucher(s) to Firestore [{total_synced}/{len(vouchers)}]")

            if on_batch_success and callable(on_batch_success):
                try:
                    on_batch_success(chunk, total_synced)
                except Exception as cb_err:
                    logger.warning(f"Error in on_batch_success callback: {cb_err}")

        return total_synced

    def get_vouchers(self, limit: int = 50, start_after_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch paginated vouchers directly from Firestore."""
        db = self.db
        query = db.collection(self.collection_name).order_by("alter_id", direction=firestore.Query.DESCENDING)
        if start_after_id:
            start_doc = db.collection(self.collection_name).document(start_after_id).get()
            if start_doc.exists:
                query = query.start_after(start_doc)
        docs = query.limit(limit).stream()
        return [doc.to_dict() for doc in docs]

