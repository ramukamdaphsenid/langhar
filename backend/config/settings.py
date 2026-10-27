import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment variables from .env if present
BASE_DIR = Path(__file__).resolve().parent.parent
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


class AppSettings(BaseModel):
    """Root Application Settings aggregating all sub-configurations."""
    tally: TallySettings = Field(default_factory=TallySettings)
    base_dir: Path = BASE_DIR


# Global settings singleton
settings = AppSettings()
