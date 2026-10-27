"""Resolve the company currently active in Tally without a local company registry."""
import hashlib
from typing import Any, Dict, Optional

from config.settings import settings
from src.tally.client import TallyClient
from src.tally.odbc_client import TallyODBCClient


def company_id_for_name(company_name: str) -> str:
    normalized = " ".join(company_name.casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_active_company_context() -> Dict[str, Any]:
    tally = TallyClient()
    xml_online = tally.is_available()
    verifier = TallyODBCClient() if settings.tally.use_odbc else tally
    verifier_online = verifier.is_available() if settings.tally.use_odbc else xml_online
    active_company = verifier.get_active_company() if xml_online and verifier_online else None

    return {
        "active_company": (
            {
                "company_id": company_id_for_name(active_company),
                "company_name": active_company,
            }
            if active_company
            else None
        ),
        "tally_online": bool(xml_online and verifier_online),
    }


def require_active_company(expected_company_id: Optional[str] = None) -> Dict[str, str]:
    context = get_active_company_context()
    active_company = context["active_company"]
    if not active_company:
        raise RuntimeError(
            "Could not verify the active Tally company. Keep one company active or enable Tally ODBC verification."
        )
    if expected_company_id and expected_company_id != active_company["company_id"]:
        raise RuntimeError("The active Tally company changed. Refresh and try again.")
    return active_company
