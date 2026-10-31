"""Optional ODBC Client for Tally Prime.

Requires:
1. Tally Prime ODBC enabled (F1 -> Settings -> Connectivity -> Enable ODBC: Yes, Port: 9000).
2. Tally ODBC DSN configured in Windows 64-bit ODBC Data Sources (e.g. 'TallyODBC64_9000').
3. pyodbc installed in the python environment (`pip install pyodbc`).
"""
from typing import Optional, Tuple

from config.settings import settings
from src.utils.logger import logger


class TallyODBCClient:
    """Client for querying Tally Prime via Windows ODBC Driver."""

    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn or settings.tally.odbc_dsn

    def _get_connection(self):
        try:
            import pyodbc
        except ImportError:
            raise ImportError(
                "pyodbc is not installed. To use Tally ODBC, run: pip install pyodbc. "
                "Alternatively, use the native HTTP XML API (recommended) which requires no drivers."
            )
        # Connect using Windows DSN
        return pyodbc.connect(f"DSN={self.dsn};", autocommit=True)

    def is_available(self) -> bool:
        """Fast check whether Tally ODBC connection is available."""
        try:
            ok, _ = self.check_connection()
            return ok
        except Exception:
            return False

    def get_active_company(self) -> Optional[str]:
        """Queries active company name via ODBC."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT $$CurrentCompany FROM Company")
            row = cursor.fetchone()
            company_name = str(row[0]).strip() if row and row[0] else None
            cursor.close()
            conn.close()
            return company_name
        except Exception as e:
            logger.warning(f"Could not retrieve active company via ODBC: {e}")
            return None

    def check_connection(self) -> Tuple[bool, str]:
        """Tests connectivity with Tally Prime via ODBC."""
        try:
            company_name = self.get_active_company()
            if not company_name:
                return False, f"Connected to ODBC DSN '{self.dsn}', but could not verify Tally's active company."
            return True, f"Connected to Tally ODBC (DSN: {self.dsn}, Active Company: {company_name})"
        except Exception as e:
            return False, f"Tally ODBC Connection Error: {e}"
