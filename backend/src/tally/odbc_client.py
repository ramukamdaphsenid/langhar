"""Optional ODBC Client for Tally Prime.

Requires:
1. Tally Prime ODBC enabled (F1 -> Settings -> Connectivity -> Enable ODBC: Yes, Port: 9000).
2. Tally ODBC DSN configured in Windows 64-bit ODBC Data Sources (e.g. 'TallyODBC64_9000').
3. pyodbc installed in the python environment (`pip install pyodbc`).
"""
from typing import Any, Dict, List, Optional, Tuple

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

    def fetch_vouchers(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        company: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Queries all voucher types using SQL via ODBC.

        Note:
            Tally's ODBC interface does not expose nested line items or tax
            ledger entries via simple SQL. This method returns voucher-level
            summary data only — ``items``, ``ledger_entries``, and ``taxes``
            will always be empty. Use the XML HTTP client for full detail.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            try:
                where_clauses = []
                if from_date:
                    where_clauses.append(f"$Date >= '{from_date}'")
                if to_date:
                    where_clauses.append(f"$Date <= '{to_date}'")

                where_sql = " AND ".join(where_clauses)
                where_clause = f"WHERE {where_sql}" if where_sql else ""
                sql = f"""
                    SELECT $Guid, $MasterID, $VoucherNumber, $Date, $PartyLedgerName,
                           $PartyName, $StateName, $PartyGSTIN, $Amount, $Narration, $Reference,
                           $BasicShipVesselNo, $VoucherTypeName
                    FROM Voucher
                    {where_clause}
                """

                logger.info(f"Executing Tally ODBC query: {sql.strip()}")
                cursor.execute(sql)
                rows = cursor.fetchall()
            finally:
                cursor.close()
        finally:
            conn.close()

        import re

        vouchers = []
        for r in rows:
            guid = str(r[0] or "")
            master_id = int(r[1] or 0)
            voucher_number = str(r[2] or "")
            date_raw = str(r[3] or "")
            party_ledger = str(r[4] or "")
            party_name = str(r[5] or "") or party_ledger
            party_state = str(r[6] or "")
            gstin = str(r[7] or "")
            amount = abs(float(r[8] or 0.0))
            narration = str(r[9] or "")
            ref = str(r[10] or "")
            vehicle_no = str(r[11] or "").strip() if len(r) > 11 else ""
            voucher_type = str(r[12] or "Unknown").strip() if len(r) > 12 and r[12] else "Unknown"

            # Fallback regex on narration if vehicle_no empty
            if not vehicle_no and narration:
                veh_match = re.search(
                    r"(?i)(?:veh(?:icle)?(?:\s*no\.?|\s*number)?|truck(?:\s*no\.?|\s*number)?)\s*[:\-]?\s*([A-Z0-9 -]{6,16})",
                    narration
                )
                if veh_match:
                    vehicle_no = veh_match.group(1).strip()
                else:
                    plate_match = re.search(r"\b([A-Z]{2}[ -]?[0-9]{1,2}[ -]?[A-Z]{1,3}[ -]?[0-9]{4})\b", narration)
                    if plate_match:
                        vehicle_no = plate_match.group(1).strip()

            doc_id = f"tally_{guid.replace('-', '_')}" if guid else f"vch_{voucher_number}_{date_raw}"
            if not guid and master_id > 0:
                doc_id = f"tally_master_{master_id}"
            elif not guid:
                doc_id = f"vch_{voucher_type}_{voucher_number}_{date_raw}"

            vouchers.append({
                "doc_id": doc_id,
                "guid": guid,
                "master_id": master_id,
                "voucher_number": voucher_number,
                "voucher_type": voucher_type,
                "company_name": company or "",
                "date": date_raw,
                "vehicle_number": vehicle_no,
                "party_name": party_name,
                "party_ledger_name": party_ledger,
                "party_gstin": gstin,
                "state_name": party_state,
                "party": {
                    "ledger_name": party_ledger,
                    "name": party_name,
                    "state": party_state,
                    "gstin": gstin,
                },
                "total_amount": amount,
                "narration": narration,
                "reference": ref,
                "items": [],
                "inventory_entries": [],
                "ledger_entries": [],
                "taxes": {},
                "source": "tally_odbc",
            })

        return vouchers

    def fetch_sales_vouchers(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        company: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Backward-compatible alias; the query now includes all voucher types."""
        return self.fetch_vouchers(from_date, to_date, company)
