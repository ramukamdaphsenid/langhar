"""HTTP Client for communicating with Tally Prime's XML Server."""
import html
import re
from typing import Any, Dict, List, Optional, Tuple
import requests

from config.settings import settings
from src.tally.parser import parse_tally_vouchers_xml
from src.tally.queries import (
    build_active_company_query,
    build_company_info_query,
    build_sales_vouchers_query
)
from src.utils.company_helper import get_target_company_name, verify_company_match
from src.utils.logger import logger


class TallyClient:
    """Client for Tally Prime XML HTTP Interface."""

    def __init__(self, host: Optional[str] = None, port: Optional[int] = None, timeout: Optional[int] = None, company: Optional[str] = None):
        self.host = host or settings.tally.host
        self.port = port or settings.tally.port
        self.timeout = timeout or settings.tally.timeout
        self.company = company or settings.tally.company
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

    def is_available(self, timeout: float = 0.5) -> bool:
        """Fast non-blocking TCP socket check whether Tally XML HTTP server is reachable."""
        import socket
        from urllib.parse import urlparse

        try:
            parsed = urlparse(self.url)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or self.port or 9000
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                return sock.connect_ex((host, port)) == 0
        except Exception:
            return False

    def get_loaded_companies(self) -> List[str]:
        """Queries Tally Prime for loaded companies using native Company collection export."""
        if not self.is_available(timeout=0.6):
            return []
        try:
            query = build_company_info_query()
            resp = self.send_xml_request(query)
            matches = re.findall(r"<(?:COMPANYNAME|NAME)[^>]*>(.*?)</(?:COMPANYNAME|NAME)>", resp, re.IGNORECASE)
            attr_matches = re.findall(r'<COMPANY\s+NAME=["\']([^"\']+)["\']', resp, re.IGNORECASE)
            companies = []
            for m in (matches + attr_matches):
                name = html.unescape(m.strip())
                if name and not name.startswith("$$") and name != "0" and name not in companies:
                    companies.append(name)
            return companies
        except Exception as e:
            logger.debug(f"Company collection query failed: {e}")
            return []


    def get_active_company(self) -> Optional[str]:
        """Queries Tally Prime for the currently active/selected company name safely."""
        companies = self.get_loaded_companies()
        if not companies:
            return None
        target = self.company or get_target_company_name()
        if target:
            for comp in companies:
                is_match, _ = verify_company_match(comp, target)
                if is_match:
                    return comp
        return companies[0]

    def check_connection(self) -> Tuple[bool, str]:
        """Tests connectivity with Tally Prime and checks the active company."""
        if not self.is_available(timeout=0.6):
            return (
                False,
                f"Could not connect to Tally Prime at {self.url}. "
                "Ensure Tally Prime is running and Server mode is enabled "
                f"(F1: Help -> Settings -> Connectivity -> Client/Server configuration -> Both/Server -> Port: {self.port})."
            )

        target_company = self.company or get_target_company_name()
        try:
            active_company = self.get_active_company()
            if active_company:
                if target_company:
                    is_match, mismatch_reason = verify_company_match(active_company, target_company)
                    if not is_match:
                        return (
                            False,
                            f"Company Mismatch: Tally Prime is open on '{active_company}', "
                            f"but target company is '{target_company}'. Please switch company in Tally."
                        )
                    return True, f"Connected to Tally Prime at {self.url} (Active Company: '{active_company}' - Verified)"
                return True, f"Connected to Tally Prime at {self.url} (Active Company: '{active_company}')"

            company_hint = target_company or "Active Company in Tally"
            return True, f"Connected to Tally Prime at {self.url} (Target: {company_hint})"
        except Exception as e:
            return False, str(e)

    def fetch_sales_vouchers(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        from_alter_id: Optional[int] = None,
        company: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Queries Tally Prime for Sales Vouchers matching the criteria.

        Args:
            from_date: Start date string formatted as YYYYMMDD (e.g. 20240401)
            to_date: End date string formatted as YYYYMMDD (e.g. 20240430)
            from_alter_id: Incremental sync Alter ID threshold ($AlterID > from_alter_id)
            company: Specific target company name to query in Tally.
        """
        target_company = company or self.company or get_target_company_name()
        logger.info(
            f"Querying Tally Prime ({self.url}) for Sales Vouchers "
            f"[Company: {target_company or 'ACTIVE'}, Date: {from_date or 'ALL'} to {to_date or 'ALL'}, AlterID > {from_alter_id or 0}]"
        )
        # Notice: We intentionally do NOT force <SVCURRENTCOMPANY> in voucher query static variables.
        # Tally Prime natively exports from its active company. Forcing an internal context switch
        # via static variables can trigger a Memory Access Violation (c0000005) in Tally's C++ core.
        xml_request = build_sales_vouchers_query(
            from_date=from_date,
            to_date=to_date,
            from_alter_id=from_alter_id,
            company=None
        )

        xml_response = self.send_xml_request(xml_request)
        vouchers = parse_tally_vouchers_xml(xml_response, company_name=target_company)
        logger.info(f"Retrieved and parsed {len(vouchers)} sales voucher(s) from Tally Prime (Company: {target_company or 'Active'}).")
        return vouchers
