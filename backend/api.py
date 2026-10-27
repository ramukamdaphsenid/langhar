"""FastAPI REST API for live Tally vouchers and company information."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from src.api.routers import company, spa, system, vouchers
from src.api.routers.company import get_company_profile
from src.api.routers.vouchers import get_vouchers
from src.api.schemas import CompanyProfileModel

__all__ = [
    "app",
    "CompanyProfileModel",
    "get_vouchers",
    "get_company_profile",
]


app = FastAPI(
    title="Langhar Tally Vouchers",
    version="1.0.0",
    description="Live Tally voucher retrieval and company document information.",
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
app.include_router(company.router)
app.include_router(vouchers.router)
spa.mount_spa(app)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
