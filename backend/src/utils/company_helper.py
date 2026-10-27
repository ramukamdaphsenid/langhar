"""Company identity and matching helpers for active Tally operations."""
from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

DEFAULT_COMPANY_PROFILE: Dict[str, Any] = {
    "company_name": "Sri Lakshmi Modern Rice Mill",
    "tagline": "",
    "address": "878 , MGR Road, Rattinamangalam, Arni - 632301",
    "state": "",
    "gstin": "33AEWFS6320P1Z9",
    "pan": "",
    "phone": "+91 98947 04173",
    "email": "langhar@gmail.com",
}

def normalize_company_name(name: Optional[str]) -> str:
    """Normalizes company names for robust comparison.

    - Lowercases & strips whitespace
    - Collapses internal whitespace
    - Strips known Tally financial-year/date suffixes like ' (from 1-Apr-2024)' or ' (2024 - 2025)'
    """
    if not name:
        return ""
    s = str(name).strip().lower()
    # Remove financial year or date suffixes in parentheses e.g. " (2024 - 2025)" or " (from 1-apr-2024)"
    s = re.sub(
        r"\s*\((?:from\s+)?(?:\d{1,2}-[a-z]{3}-)?\d{4}(?:\s*-\s*\d{2,4})?\)\s*$",
        "",
        s,
        flags=re.IGNORECASE,
    )
    # Collapse multiple spaces into one
    s = re.sub(r"\s+", " ", s).strip()
    return s


def verify_company_match(active_company: Optional[str], target_company: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Verify that the active Tally company matches the company targeted by an operation.

    Returns:
        (is_match: bool, error_or_warning_message: Optional[str])
    """
    if not target_company or not target_company.strip():
        return False, "No target company was provided for Tally verification."

    if not active_company or not active_company.strip():
        return False, f"Could not determine active company in Tally Prime (Expected: '{target_company}')."

    norm_active = normalize_company_name(active_company)
    norm_target = normalize_company_name(target_company)

    if norm_active == norm_target:
        return True, None

    return False, (
        f"Active company in Tally ('{active_company}') does not match "
        f"target company ('{target_company}')."
    )
