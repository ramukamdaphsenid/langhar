import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field

_BACKEND_DIR = Path(__file__).resolve().parent.parent
if getattr(sys, "frozen", False):
    _LOCAL_APP_DATA = Path(
        os.getenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
    )
    BASE_DIR = _LOCAL_APP_DATA / "Langhar"
else:
    BASE_DIR = _BACKEND_DIR

load_dotenv(BASE_DIR / ".env")

class TallySettings(BaseModel):
    """Configuration for Tally Prime connectivity."""
    host: str = Field(default_factory=lambda: os.getenv("TALLY_HOST", "http://localhost"))
    port: int = Field(default_factory=lambda: int(os.getenv("TALLY_PORT", "9000")))
    timeout: int = Field(default_factory=lambda: int(os.getenv("TALLY_TIMEOUT", "30")))
    use_odbc: bool = Field(default_factory=lambda: os.getenv("TALLY_USE_ODBC", "false").lower() in ("true", "1", "yes"))
    odbc_dsn: str = Field(default_factory=lambda: os.getenv("TALLY_ODBC_DSN", "TallyODBC64_9000"))

    @property
    def url(self) -> str:
        """Normalized URL for Tally XML server endpoint."""
        base = self.host.rstrip("/")
        if not base.startswith("http://") and not base.startswith("https://"):
            base = f"http://{base}"
        return f"{base}:{self.port}"


class ServerSettings(BaseModel):
    """Local web server configuration for the packaged application."""
    host: str = Field(default_factory=lambda: os.getenv("APP_HOST", "127.0.0.1"))
    port: int = Field(
        default_factory=lambda: int(os.getenv("APP_PORT", "8000")),
        ge=1,
        le=65535,
    )


class AppSettings(BaseModel):
    """Root Application Settings aggregating all sub-configurations."""
    tally: TallySettings = Field(default_factory=TallySettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    base_dir: Path = BASE_DIR

    @property
    def static_dir(self) -> Path:
        """Resolve bundled frontend assets or the local development build."""
        if getattr(sys, "frozen", False):
            bundle_dir = Path(getattr(sys, "_MEIPASS"))
            return bundle_dir / "data" / "static"
        return self.base_dir / "static"


# Global settings singleton
settings = AppSettings()
