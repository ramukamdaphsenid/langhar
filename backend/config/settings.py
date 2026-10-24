import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment variables from .env if present
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class TallySettings(BaseModel):
    """Configuration for Tally Prime connectivity."""
    host: str = Field(default_factory=lambda: os.getenv("TALLY_HOST", "http://localhost"))
    port: int = Field(default_factory=lambda: int(os.getenv("TALLY_PORT", "9000")))
    company: Optional[str] = Field(default_factory=lambda: os.getenv("TALLY_COMPANY") or None)
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


class FirebaseSettings(BaseModel):
    """Configuration for Firebase Firestore."""
    credentials_path: Path = Field(
        default_factory=lambda: BASE_DIR / os.getenv("FIREBASE_CREDENTIALS_PATH", "serviceAccountKey.json")
    )
    collection_name: str = Field(
        default_factory=lambda: os.getenv("FIREBASE_COLLECTION_NAME", "sales_vouchers")
    )


class SyncSettings(BaseModel):
    """Configuration for Sync Execution & State."""
    interval_seconds: int = Field(
        default_factory=lambda: int(os.getenv("SYNC_INTERVAL_SECONDS", "120"))
    )
    state_file: Path = Field(
        default_factory=lambda: BASE_DIR / os.getenv("SYNC_STATE_FILE", ".sync_state.json")
    )
    batch_size: int = Field(
        default_factory=lambda: int(os.getenv("BATCH_SIZE", "100"))
    )


class AppSettings(BaseModel):
    """Root Application Settings aggregating all sub-configurations."""
    tally: TallySettings = Field(default_factory=TallySettings)
    firebase: FirebaseSettings = Field(default_factory=FirebaseSettings)
    sync: SyncSettings = Field(default_factory=SyncSettings)
    base_dir: Path = BASE_DIR


# Global settings singleton
settings = AppSettings()
