"""Company profile and company matching helper utilities.

Guarantees that Tally synchronization strictly targets the correct company
and prevents accidental synchronization of foreign/wrong company datasets.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Dict, Optional, Tuple

from config.settings import settings
from src.utils.logger import logger

COMPANY_PROFILE_FILE = Path(__file__).resolve().parent.parent.parent / "config" / "company_profile.json"

DEFAULT_COMPANY_PROFILE: Dict[str, Any] = {
    "company_name": "Sri Lakshmi Modern Rice Mill",
    "tagline": "Premium Rice Millers & Wholesalers",
    "address": "12, Main Road, Bengaluru 560001",
    "state": "Karnataka (State Code: 29)",
    "gstin": "29AABCL1234F1Z5",
    "pan": "AABCL1234F",
    "phone": "+91 98765 43210",
    "email": "billing@langhar.com",
    "bank_name": "State Bank of India",
    "bank_account_number": "39120491823",
    "bank_ifsc": "SBIN0001234",
    "bank_branch": "Main Branch, Bengaluru",
    "terms": "1. Goods once sold will not be taken back. 2. Subject to Bengaluru jurisdiction.",
}


def load_local_company_profile() -> Dict[str, Any]:
    """Loads local company profile cache from disk."""
    if COMPANY_PROFILE_FILE.exists():
        try:
            with open(COMPANY_PROFILE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {**DEFAULT_COMPANY_PROFILE, **data}
        except Exception as e:
            logger.warning(f"Failed to read company_profile.json ({e}). Using default profile.")
    return dict(DEFAULT_COMPANY_PROFILE)


def save_local_company_profile(data: Dict[str, Any]) -> None:
    """Safely saves company profile cache to disk."""
    COMPANY_PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = COMPANY_PROFILE_FILE.with_suffix(".tmp")
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        temp_file.replace(COMPANY_PROFILE_FILE)
    except Exception:
        # Fallback for Docker single-file bind mounts where os.replace raises [Errno 16] Device or resource busy
        try:
            with open(COMPANY_PROFILE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as write_err:
            logger.warning(f"Failed to write company_profile.json ({write_err})")
        finally:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass



def get_target_company_name() -> Optional[str]:
    """Resolves an explicitly configured Tally target company.

    The saved company profile is used for invoice generation and must not
    determine which company Tally sync reads from.
    """
    if settings.tally.company and settings.tally.company.strip():
        return settings.tally.company.strip()

    return None


def normalize_company_name(name: Optional[str]) -> str:
    """Normalizes company names for robust comparison.

    - Lowercases & strips whitespace
    - Collapses internal whitespace
    - Strips common Tally Prime window suffixes like ' (from 1-Apr-2024)' or ' (2024-25)'
    """
    if not name:
        return ""
    s = str(name).strip().lower()
    # Remove financial year or date suffixes in parentheses e.g. " (2024-2025)" or " (from 1-apr-2024)"
    s = re.sub(r"\s*\((?:from\s+)?(?:\d{1,2}-[a-z]{3}-)?\d{4}(?:-\d{2,4})?\)\s*$", "", s, flags=re.IGNORECASE)
    # Remove any generic trailing parenthetical info
    s = re.sub(r"\s*\([^)]*\)$", "", s)
    # Collapse multiple spaces into one
    s = re.sub(r"\s+", " ", s).strip()
    return s


def verify_company_match(active_company: Optional[str], target_company: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Verifies whether the active company in Tally matches the target configured company.

    Returns:
        (is_match: bool, error_or_warning_message: Optional[str])
    """
    if not target_company or not target_company.strip():
        # No target company configured; any active company is permissible
        return True, None

    if not active_company or not active_company.strip():
        return False, f"Could not determine active company in Tally Prime (Expected: '{target_company}')."

    norm_active = normalize_company_name(active_company)
    norm_target = normalize_company_name(target_company)

    if norm_active == norm_target:
        return True, None

    # Check substring containment if one is prefix of the other (e.g. "Sri Lakshmi Modern Rice Mill" in "Sri Lakshmi Modern Rice Mill Pvt Ltd")
    if norm_target in norm_active or norm_active in norm_target:
        return True, None

    return False, (
        f"Active company in Tally ('{active_company}') does not match "
        f"target company ('{target_company}')."
    )
