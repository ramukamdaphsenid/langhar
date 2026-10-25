"""Company profile settings endpoints: fetch, update and persist business profile."""
from fastapi import APIRouter
from src.api import runtime
from src.api.schemas import CompanyProfileModel
from src.firebase.client import FirebaseClient
from src.utils.logger import logger

router = APIRouter()


@router.get("/api/settings/company", response_model=CompanyProfileModel)
def get_company_profile():
    """Fetch persistent company profile from Firebase Firestore (with local config fallback)."""
    try:
        firebase = FirebaseClient()
        profile = firebase.get_company_profile()
        if profile and profile.get("company_name"):
            # Merge with local defaults in case some optional fields are absent
            local_defaults = runtime._load_company_profile()
            merged = {**local_defaults, **profile}
            runtime._save_company_profile(merged)
            return merged
        elif not profile:
            # Firestore is empty; auto-seed it from local configuration so Firestore is populated
            local_defaults = runtime._load_company_profile()
            if local_defaults.get("company_name"):
                try:
                    firebase.save_company_profile(local_defaults)
                    logger.info("[SETTINGS] Auto-seeded company profile to Firestore 'settings/company_profile'")
                except Exception as seed_err:
                    logger.debug(f"[SETTINGS] Could not auto-seed Firestore company profile: {seed_err}")
            return local_defaults
    except Exception as e:
        logger.warning(f"Error reading company profile from Firebase: {e}")

    return runtime._load_company_profile()


@router.post("/api/settings/company")
def update_company_profile(profile: CompanyProfileModel):
    """Update and persist business profile and invoice header details to local config and Firestore."""
    data = profile.model_dump()
    runtime._save_company_profile(data)

    firestore_ok = False
    firestore_err = None
    try:
        firebase = FirebaseClient()
        firebase.save_company_profile(data)
        firestore_ok = True
        logger.info(f"[SETTINGS] Company profile updated and saved to Firestore: {profile.company_name}")
    except Exception as e:
        firestore_err = str(e)
        logger.warning(f"[SETTINGS] Saved locally. Firestore write warning: {e}")

    if firestore_ok:
        return {
            "status": "SUCCESS",
            "message": "Company profile successfully saved and synced to Firebase Firestore.",
            "source": "firestore",
            "profile": data,
        }
    else:
        return {
            "status": "PARTIAL_SUCCESS",
            "message": f"Saved locally in server cache, but failed to write to Firebase Firestore: {firestore_err}",
            "source": "local",
            "profile": data,
        }
