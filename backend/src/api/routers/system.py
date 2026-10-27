"""System health endpoint."""
from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/health")
def api_health():
    """Simple API health check."""
    return {"status": "ok", "service": "langhar-tally-vouchers", "timestamp": datetime.now(timezone.utc).isoformat()}
