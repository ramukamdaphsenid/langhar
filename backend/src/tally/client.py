"""HTTP Client for communicating with Tally Prime's XML Server."""
from typing import Any, Dict, List, Optional, Tuple
import requests

from config.settings import settings
from src.tally.parser import parse_tally_vouchers_xml, safe_str
from src.tally.queries import build_company_info_query, build_sales_vouchers_query
from src.utils.logger import logger


class TallyClient:
    """Client for Tally Prime XML HTTP Interface."""

    def __init__(self, host: Optional[str] = None, port: Optional[int] = None, timeout: Optional[int] = None):
        self.host = host or settings.tally.host
        self.port = port or settings.tally.port
        self.timeout = timeout or settings.tally.timeout
        self.company = settings.tally.company
        self.session = requests.Session()

    @property
    def url(self) -> str:
        """Normalized Tally XML server URL."""
        if self.host == settings.tally.host and self.port == settings.tally.port:
            return settings.tally.url
        base = self.host.rstrip("/")
        if not base.startswith("http://") and not base.startswith("https://"):
            base = f"http://{base}"
        return f"{base}:{self.port}"

    def send_xml_request(self, xml_payload: str) -> str:
        """Sends an XML request payload to Tally Prime via HTTP POST with connection pooling."""
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "Accept": "text/xml",
        }
        try:
            response = self.session.post(
                self.url,
                data=xml_payload.encode("utf-8"),
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            # Tally can return UTF-8, UTF-16, or ASCII encoded XML
            response.encoding = response.apparent_encoding or "utf-8"
            return response.text
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Could not connect to Tally Prime at {self.url}. "
                "Ensure Tally Prime is running and Server mode is enabled "
                "(F1: Help -> Settings -> Connectivity -> Client/Server configuration -> Both/Server -> Port: 9000)."
            )
        except requests.exceptions.Timeout:
            raise TimeoutError(f"Tally Prime at {self.url} timed out after {self.timeout} seconds.")
        except Exception as e:
            raise RuntimeError(f"Error querying Tally Prime: {e}")

    def check_connection(self) -> Tuple[bool, str]:
        """Tests connectivity with Tally Prime and checks the active company."""
        try:
            # First try sending a simple company info query
            query = build_company_info_query()
            resp = self.send_xml_request(query)
            if "ENVELOPE" in resp or "RESPONSE" in resp:
                company_hint = self.company if self.company else "Active Company in Tally"
                return True, f"Connected to Tally Prime at {self.url} (Target: {company_hint})"
            return True, f"Connected to Tally Prime at {self.url}"
        except Exception as e:
            return False, str(e)

    def fetch_sales_vouchers(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        from_alter_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Queries Tally Prime for Sales Vouchers matching the criteria.

        Args:
            from_date: Start date string formatted as YYYYMMDD (e.g. 20240401)
            to_date: End date string formatted as YYYYMMDD (e.g. 20240430)
            from_alter_id: Incremental sync Alter ID threshold ($AlterID > from_alter_id)
        """
        logger.info(
            f"Querying Tally Prime ({self.url}) for Sales Vouchers "
            f"[Date: {from_date or 'ALL'} to {to_date or 'ALL'}, AlterID > {from_alter_id or 0}]"
        )
        xml_request = build_sales_vouchers_query(
            from_date=from_date,
            to_date=to_date,
            from_alter_id=from_alter_id,
            company=self.company
        )

        xml_response = self.send_xml_request(xml_request)
        vouchers = parse_tally_vouchers_xml(xml_response)
        logger.info(f"Retrieved and parsed {len(vouchers)} sales voucher(s) from Tally Prime.")
        return vouchers
