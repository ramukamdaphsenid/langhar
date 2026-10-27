"""HTTP Client for communicating with Tally Prime's XML Server."""
import html
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple
import requests

from config.settings import settings
from src.tally.parser import parse_tally_vouchers_xml
from src.tally.queries import (
    build_company_info_query,
    build_vouchers_query
)
from src.utils.company_helper import verify_company_match
from src.utils.logger import logger


class TallyClient:
    """Client for Tally Prime XML HTTP Interface."""

    def __init__(self, host: Optional[str] = None, port: Optional[int] = None, timeout: Optional[int] = None, company: Optional[str] = None):
        self.host = host or settings.tally.host
        self.port = port or settings.tally.port
        self.timeout = timeout or settings.tally.timeout
        self.company = company
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
        """Return the company only when the XML interface reports one unambiguous company.

        The Company collection can contain every company loaded in Tally, not only the
        active one. Never infer the active company by looking for the requested target.
        """
        companies = self.get_loaded_companies()
        unique = {name.casefold(): name for name in companies if name.strip()}
        if len(unique) != 1:
            if len(unique) > 1:
                logger.warning(
                    "Tally XML reports multiple loaded companies; active company cannot be verified safely."
                )
            return None
        return next(iter(unique.values()))

    def check_connection(self) -> Tuple[bool, str]:
        """Tests connectivity with Tally Prime and checks the active company."""
        if not self.is_available(timeout=0.6):
            return (
                False,
                f"Could not connect to Tally Prime at {self.url}. "
                "Ensure Tally Prime is running and Server mode is enabled "
                f"(F1: Help -> Settings -> Connectivity -> Client/Server configuration -> Both/Server -> Port: {self.port})."
            )

        target_company = self.company
        try:
            active_company = self.get_active_company()
            if not active_company:
                return (
                    False,
                    "Tally is reachable, but its active company cannot be verified. "
                    "Keep only the intended company open in Tally or enable ODBC verification."
                )
            if target_company:
                is_match, _ = verify_company_match(active_company, target_company)
                if not is_match:
                    return (
                        False,
                        f"Company Mismatch: Tally reports '{active_company}', "
                        f"but the requested target is '{target_company}'. Open the target company in Tally."
                    )
                return True, f"Connected to Tally Prime at {self.url} (Company '{active_company}' verified)"
            return True, f"Connected to Tally Prime at {self.url} (Company '{active_company}' verified)"
        except Exception as e:
            return False, str(e)

    def fetch_vouchers(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        company: Optional[str] = None,
        voucher_types: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Query Tally Prime for matching voucher types and criteria.

        Args:
            from_date: Start date string formatted as YYYYMMDD (e.g. 20240401)
            to_date: End date string formatted as YYYYMMDD (e.g. 20240430)
            company: Specific target company name to query in Tally.
            voucher_types: Optional voucher type names to include.
        """
        target_company = company or self.company
        logger.info(
            f"Querying Tally Prime ({self.url}) for vouchers "
            f"[Company: {target_company or 'ACTIVE'}, Date: {from_date or 'ALL'} to {to_date or 'ALL'}]"
        )
        # Notice: We intentionally do NOT force <SVCURRENTCOMPANY> in voucher query static variables.
        # Tally Prime natively exports from its active company. Forcing an internal context switch
        # via static variables can trigger a Memory Access Violation (c0000005) in Tally's C++ core.
        xml_request = build_vouchers_query(
            from_date=from_date,
            to_date=to_date,
            company=None,
            voucher_types=voucher_types,
        )

        xml_response = self.send_xml_request(xml_request)
        header = re.search(r"<HEADER>(.*?)</HEADER>", xml_response, flags=re.IGNORECASE | re.DOTALL)
        if header and re.search(r"<STATUS>\s*0\s*</STATUS>", header.group(1), flags=re.IGNORECASE):
            detail = re.search(r"<(?:LINEERROR|DESC)>(.*?)</(?:LINEERROR|DESC)>", xml_response, flags=re.IGNORECASE | re.DOTALL)
            message = html.unescape(detail.group(1).strip()) if detail else "Tally rejected the voucher export request."
            raise RuntimeError(message)
        vouchers = parse_tally_vouchers_xml(xml_response, company_name=target_company)
        logger.info(f"Retrieved and parsed {len(vouchers)} voucher(s) from Tally Prime (Company: {target_company or 'Active'}).")
        return vouchers

    def fetch_sales_vouchers(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        company: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Backward-compatible alias; the export now includes every voucher type."""
        return self.fetch_vouchers(from_date, to_date, company)
