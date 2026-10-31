"""Static file & Single-Page Application (SPA) serving for the compiled Angular build."""
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from config.settings import settings
from src.utils.logger import logger

# Resolve the SPA static directory. Override via STATIC_DIR env var if needed.
# Defaults to backend/static (a locally compiled Angular output directory).
_static_dir_env = os.getenv("STATIC_DIR")
if _static_dir_env:
    static_dir = Path(_static_dir_env)
else:
    static_dir = settings.static_dir


def mount_spa(app: FastAPI) -> None:
    """Mounts the compiled Angular SPA, registered last so API routes take precedence."""
    if static_dir.exists() and (static_dir / "index.html").exists():
        logger.info(f"[SPA] Serving compiled frontend UI from {static_dir}")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_frontend(full_path: str):
            # Don't intercept API endpoints or OpenAPI docs
            if full_path.startswith("api/") or full_path in ("docs", "openapi.json", "redoc"):
                raise HTTPException(status_code=404, detail="Not Found")

            target_file = static_dir / full_path
            if full_path and target_file.is_file():
                return FileResponse(target_file)

            # Fallback to index.html for Angular client-side routing
            return FileResponse(static_dir / "index.html")
