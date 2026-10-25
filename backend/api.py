"""FastAPI REST API server for Tally to Firebase Sync UI."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from config.settings import settings
from src.api import runtime
from src.api.routers import company, firestore, spa, sync, system, vouchers
from src.api.routers.company import get_company_profile, update_company_profile
from src.api.routers.firestore import clear_firestore_data, cleanup_firestore_duplicates
from src.api.routers.vouchers import get_sample_vouchers
from src.api.schemas import CompanyProfileModel, DaemonStartRequest, SyncRequest
from src.firebase.client import FirebaseClient
from src.utils.logger import logger

__all__ = [
    "app",
    "SyncRequest",
    "DaemonStartRequest",
    "CompanyProfileModel",
    "get_sample_vouchers",
    "get_company_profile",
    "update_company_profile",
    "clear_firestore_data",
    "cleanup_firestore_duplicates",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Eagerly initialize connections on application start."""
    try:
        fb = FirebaseClient()
        fb.initialize()
        # Eagerly sync company profile from Firestore to local cache on startup
        profile = fb.get_company_profile()
        if profile and profile.get("company_name"):
            runtime._save_company_profile(profile)
            logger.info(f"[STARTUP] Company profile loaded from Firebase Firestore: {profile.get('company_name')}")
    except Exception as e:
        logger.warning(f"[STARTUP] Could not eagerly pre-fetch company profile from Firebase: {e}")
    yield
    try:
        runtime.daemon_manager.stop()
    except Exception:
        pass


app = FastAPI(
    title="Langhar Enterprise Rice Platform - Tally Sync API",
    version="1.0.0",
    description="REST API controlling Langhar's Tally Prime to Firebase Firestore synchronization.",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


app.include_router(system.router)
app.include_router(sync.router)
app.include_router(firestore.router)
app.include_router(company.router)
app.include_router(vouchers.router)
spa.mount_spa(app)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
