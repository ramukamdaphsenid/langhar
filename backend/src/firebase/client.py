"""Firebase Cloud Firestore Client for Sales Voucher Synchronization."""
from datetime import datetime, timezone
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional, Tuple

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_batch import BaseWriteBatch

from config.settings import settings
from src.tally.parser import is_allowed_voucher_type
from src.utils.logger import logger

_init_lock = threading.Lock()
_cached_app = None
_cached_db = None


class FirebaseClient:
    """Manages connection and batch synchronization to Firebase Cloud Firestore."""

    def __init__(self, credentials_path: Optional[Path] = None, collection_name: Optional[str] = None):
        self.credentials_path = credentials_path or settings.firebase.credentials_path
        self.collection_name = collection_name or settings.firebase.collection_name
        self._db = _cached_db
        self._app = _cached_app

    def initialize(self) -> None:
        """Initializes Firebase Admin SDK using the service account key (thread-safe singleton)."""
        global _cached_app, _cached_db
        if self._db is not None:
            return

        with _init_lock:
            if _cached_db is not None:
                self._app = _cached_app
                self._db = _cached_db
                return

            if not self.credentials_path.exists():
                raise FileNotFoundError(
                    f"Firebase credentials file not found at: {self.credentials_path.resolve()}\n"
                    "Please download your service account key from the Firebase Console:\n"
                    "  Project Settings -> Service Accounts -> Generate new private key\n"
                    f"and save it as '{self.credentials_path.name}' in the project root."
                )

            try:
                # Safely get existing app or initialize if not already registered
                try:
                    self._app = firebase_admin.get_app()
                except ValueError:
                    cred = credentials.Certificate(str(self.credentials_path))
                    self._app = firebase_admin.initialize_app(cred)

                self._db = firestore.client(app=self._app)
                _cached_app = self._app
                _cached_db = self._db
                logger.debug(f"Firebase Firestore initialized successfully (collection: '{self.collection_name}')")
            except Exception as e:
                logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
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
        valid_vouchers = [
            v for v in vouchers
            if is_allowed_voucher_type(v.get("voucher_type"))
        ]
        if not valid_vouchers:
            logger.info("No RICE SALES or RICE SALES TAXABLE vouchers to upsert.")
            return 0

        # In-memory deduplication: if multiple vouchers have the same business key
        # (company_name, voucher_type, voucher_number, date) or same doc_id, retain the one with highest alter_id
        deduped_map: Dict[str, Dict[str, Any]] = {}
        for v in valid_vouchers:
            doc_id = v.get("doc_id")
            if not doc_id:
                continue
            comp = str(v.get("company_name") or "").strip().lower()
            v_type = str(v.get("voucher_type") or "").strip().upper()
            v_num = str(v.get("voucher_number") or "").strip().lower()
            v_date = str(v.get("date") or "").strip()
            key = f"{comp}::{v_type}::{v_num}::{v_date}" if v_num else doc_id

            if key not in deduped_map:
                deduped_map[key] = v
            else:
                existing_alter = int(deduped_map[key].get("alter_id") or 0)
                new_alter = int(v.get("alter_id") or 0)
                if new_alter >= existing_alter:
                    deduped_map[key] = v

        valid_vouchers = list(deduped_map.values())

        db = self.db
        col_ref = db.collection(self.collection_name)

        # Firestore limit is 500 writes per batch
        safe_batch_size = max(1, min(batch_size, 450))
        total_synced = 0

        # Chunk vouchers into batches
        for i in range(0, len(valid_vouchers), safe_batch_size):
            chunk = valid_vouchers[i:i + safe_batch_size]
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
                # Ensure company_name is explicitly persisted
                if "company_name" not in data or not data["company_name"]:
                    data["company_name"] = voucher.get("company_name") or ""

                batch.set(doc_ref, data, merge=True)

            batch.commit()
            total_synced += len(chunk)
            logger.info(f"Committed batch of {len(chunk)} voucher(s) to Firestore [{total_synced}/{len(valid_vouchers)}]")

            if on_batch_success and callable(on_batch_success):
                try:
                    on_batch_success(chunk, total_synced)
                except Exception as cb_err:
                    logger.warning(f"Error in on_batch_success callback: {cb_err}")

        return total_synced

    def get_vouchers(
        self,
        limit: Optional[int] = None,
        start_after_id: Optional[str] = None,
        company_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch vouchers directly from Firestore, filtered for allowed rice sales types and optional company."""
        db = self.db
        col_ref = db.collection(self.collection_name)

        try:
            query = col_ref.order_by("alter_id", direction=firestore.Query.DESCENDING)
            if start_after_id:
                start_doc = col_ref.document(start_after_id).get()
                if start_doc.exists:
                    query = query.start_after(start_doc)
            if limit and limit > 0:
                docs = query.limit(limit * 2).stream()
            else:
                docs = query.stream()
        except Exception as query_err:
            logger.warning(f"Ordered query on Firestore collection failed ({query_err}). Using unordered stream fallback.")
            if limit and limit > 0:
                docs = col_ref.limit(limit * 2).stream()
            else:
                docs = col_ref.stream()

        from src.utils.company_helper import verify_company_match

        results: List[Dict[str, Any]] = []
        seen_keys = set()

        for doc in docs:
            d = doc.to_dict()
            if "doc_id" not in d or not d["doc_id"]:
                d["doc_id"] = doc.id
            if is_allowed_voucher_type(d.get("voucher_type")):
                # If company_name filter provided and doc has company_name, ensure it matches
                doc_comp = d.get("company_name")
                if company_name and doc_comp:
                    is_m, _ = verify_company_match(doc_comp, company_name)
                    if not is_m:
                        continue

                # Deduplicate on the fly by (company, voucher_type, voucher_number, date) or doc_id
                v_num = str(d.get("voucher_number") or "").strip().lower()
                c_name = str(d.get("company_name") or "").strip().lower()
                v_date = str(d.get("date") or "").strip()
                v_type = str(d.get("voucher_type") or "").strip().upper()
                dedup_key = f"{c_name}::{v_type}::{v_num}::{v_date}" if v_num else doc.id
                if dedup_key in seen_keys:
                    continue
                seen_keys.add(dedup_key)

                results.append(d)
                if limit and len(results) >= limit:
                    break

        # Ensure vouchers are sorted by date/alter_id descending (newest first)
        results.sort(
            key=lambda x: (
                str(x.get("date") or ""),
                int(x.get("alter_id") or 0)
            ),
            reverse=True
        )

        return results

    def cleanup_redundant_and_duplicate_vouchers(self, company_name: Optional[str] = None) -> Dict[str, Any]:
        """Scans Firestore collection, deletes non-allowed voucher types and duplicate documents,
        keeping only the latest/richest document for each invoice.
        """
        db = self.db
        col_ref = db.collection(self.collection_name)

        docs = list(col_ref.stream())
        total_scanned = len(docs)

        docs_to_delete: List[str] = []
        valid_groups: Dict[str, List[Dict[str, Any]]] = {}

        for doc in docs:
            d = doc.to_dict()
            doc_id = doc.id
            v_type = str(d.get("voucher_type", "")).strip().upper()
            v_num = str(d.get("voucher_number", "")).strip()
            v_comp = str(d.get("company_name", "")).strip()
            v_date = str(d.get("date", "")).strip()

            # 1. Non-allowed voucher types or orphaned/empty records
            if not v_num or not is_allowed_voucher_type(v_type):
                docs_to_delete.append(doc_id)
                continue

            # Optional company filter if caller specified
            if company_name and v_comp:
                from src.utils.company_helper import verify_company_match
                is_m, _ = verify_company_match(v_comp, company_name)
                if not is_m:
                    continue

            # Group valid vouchers by composite business key
            group_key = f"{v_comp.lower()}::{v_type}::{v_num.lower()}::{v_date}"
            if group_key not in valid_groups:
                valid_groups[group_key] = []
            valid_groups[group_key].append({
                "doc_id": doc_id,
                "alter_id": int(d.get("alter_id") or 0),
                "has_items": bool(d.get("items")),
                "last_updated": str(d.get("last_updated") or ""),
                "synced_at": str(d.get("synced_at") or ""),
            })

        count_non_allowed = len(docs_to_delete)

        # 2. Identify duplicates in valid groups (keep best, delete the rest)
        count_dupes = 0
        for group_key, group_items in valid_groups.items():
            if len(group_items) > 1:
                # Sort: prefer documents with items, then highest alter_id, then newest last_updated
                group_items.sort(
                    key=lambda x: (
                        1 if x["has_items"] else 0,
                        x["alter_id"],
                        x["last_updated"],
                        x["synced_at"]
                    ),
                    reverse=True
                )
                # Keep group_items[0], mark all others for deletion
                for dup in group_items[1:]:
                    docs_to_delete.append(dup["doc_id"])
                    count_dupes += 1

        # 3. Batch delete documents to remove
        total_deleted = 0
        batch_size = 400
        for i in range(0, len(docs_to_delete), batch_size):
            chunk = docs_to_delete[i:i + batch_size]
            batch = db.batch()
            for did in chunk:
                batch.delete(col_ref.document(did))
            batch.commit()
            total_deleted += len(chunk)
            logger.info(f"Deleted batch of {len(chunk)} redundant voucher(s) from Firestore [{total_deleted}/{len(docs_to_delete)}]")

        remaining = total_scanned - total_deleted
        logger.info(
            f"Firestore cleanup finished: scanned {total_scanned}, deleted {total_deleted} "
            f"({count_non_allowed} non-allowed/orphaned, {count_dupes} duplicates), {remaining} clean vouchers remaining."
        )

        return {
            "scanned": total_scanned,
            "deleted_non_allowed": count_non_allowed,
            "deleted_duplicates": count_dupes,
            "total_deleted": total_deleted,
            "remaining": remaining,
        }

    def clear_all_vouchers(self, company_name: Optional[str] = None) -> int:
        """Deletes all vouchers in the Firestore collection (or for the given company if filtered)."""
        db = self.db
        col_ref = db.collection(self.collection_name)
        docs = list(col_ref.stream())

        from src.utils.company_helper import verify_company_match

        docs_to_delete = []
        for doc in docs:
            if company_name:
                doc_comp = doc.to_dict().get("company_name")
                if doc_comp:
                    is_m, _ = verify_company_match(doc_comp, company_name)
                    if not is_m:
                        continue
            docs_to_delete.append(doc.id)

        total_deleted = 0
        batch_size = 400
        for i in range(0, len(docs_to_delete), batch_size):
            chunk = docs_to_delete[i:i + batch_size]
            batch = db.batch()
            for did in chunk:
                batch.delete(col_ref.document(did))
            batch.commit()
            total_deleted += len(chunk)

        logger.info(f"Successfully cleared {total_deleted} voucher document(s) from Firestore collection '{self.collection_name}'.")
        return total_deleted

    def get_company_profile(self) -> Optional[Dict[str, Any]]:
        """Fetch the persistent company profile from Firestore 'settings' collection."""
        try:
            db = self.db
            doc = db.collection("settings").document("company_profile").get()
            if doc.exists:
                data = doc.to_dict()
                logger.info("Loaded company profile from Firestore 'settings/company_profile'")
                return data
            return None
        except Exception as e:
            logger.warning(f"Failed to fetch company profile from Firestore: {e}")
            return None

    def save_company_profile(self, profile: Dict[str, Any]) -> bool:
        """Persist company profile to Firestore 'settings' collection."""
        try:
            db = self.db
            data = dict(profile)
            data["updated_at"] = datetime.now(timezone.utc).isoformat()
            db.collection("settings").document("company_profile").set(data, merge=True)
            logger.info("Company profile successfully saved to Firestore 'settings/company_profile'")
            return True
        except Exception as e:
            logger.error(f"Failed to save company profile to Firestore: {e}")
            raise


