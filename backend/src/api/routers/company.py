"""Active Tally company and document-profile endpoints."""
import json
from json import JSONDecodeError

from fastapi import APIRouter, HTTPException
from src.api.schemas import CompanyProfileModel
from config.settings import settings
from src.utils.active_company import get_active_company_context, require_active_company
from src.utils.company_helper import normalize_company_name
from src.utils.logger import logger

router = APIRouter()


def _require_active_company(company_id: str = None):
    try:
        return require_active_company(company_id)
    except RuntimeError as error:
        status_code = 409 if company_id and "changed" in str(error).lower() else 503
        raise HTTPException(status_code=status_code, detail=str(error))


@router.get("/api/company/active")
def get_active_company():
    """Return the company currently active in Tally, without a local registry."""
    try:
        return get_active_company_context()
    except Exception as error:
        logger.warning(f"Could not determine the active Tally company: {error}")
        return {"active_company": None, "tally_online": False}


@router.get("/api/settings/company", response_model=CompanyProfileModel)
def get_company_profile(company_id: str = None):
    """Read the configured document profile for the active Tally company."""
    company = _require_active_company(company_id)
    profile_path = settings.base_dir / "config" / "company_profile.json"
    profile = {}

    try:
        configured_profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        configured_profile = None
    except (OSError, JSONDecodeError) as error:
        logger.warning(f"Could not read company profile configuration: {error}")
        configured_profile = None

    if configured_profile and normalize_company_name(configured_profile.get("company_name")) == normalize_company_name(company["company_name"]):
        profile = configured_profile

    return {
        **CompanyProfileModel().model_dump(),
        **profile,
        "company_name": profile.get("company_name", company["company_name"]),
    }
