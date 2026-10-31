"""Unit tests for Tally voucher parsing and API behavior."""
import unittest
from pathlib import Path

from src.tally.parser import parse_tally_vouchers_xml, parse_tally_date
from src.tally.queries import build_vouchers_query


class TestTallyApi(unittest.TestCase):

    def test_parse_date(self):
        self.assertEqual(parse_tally_date("20240415"), "2024-04-15")
        self.assertEqual(parse_tally_date("20251231"), "2025-12-31")
        self.assertIsNone(parse_tally_date(""))

    def test_parse_quantity_dual_units(self):
        from src.tally.parser import parse_tally_quantity, safe_float
        # Dual unit "25.00 QTL = 100 BAG" should pick 100 BAG
        q, u = parse_tally_quantity("25.00 QTL = 100 BAG")
        self.assertEqual(q, 100.0)
        self.assertEqual(u, "BAG")
        self.assertEqual(safe_float("25.00 QTL = 100 BAG"), 100.0)

        # Leading = sign
        q, u = parse_tally_quantity("= 25.00 QTL = 100 BAG")
        self.assertEqual(q, 100.0)
        self.assertEqual(u, "BAG")

        # Reversed order: 100 BAG = 25.00 QTL
        q, u = parse_tally_quantity("100 BAG = 25.00 QTL")
        self.assertEqual(q, 100.0)
        self.assertEqual(u, "BAG")

        # BAGS / BGS variations
        q, u = parse_tally_quantity("25.00 QTL = 100 BAGS")
        self.assertEqual(q, 100.0)
        self.assertEqual(u, "BAGS")

        q, u = parse_tally_quantity("25.00 QNTL = 100 BGS")
        self.assertEqual(q, 100.0)
        self.assertEqual(u, "BGS")

        # Single unit unchanged
        q, u = parse_tally_quantity("10 Nos")
        self.assertEqual(q, 10.0)
        self.assertEqual(u, "Nos")

    def test_query_generation(self):
        query = build_vouchers_query(
            from_date="20240401",
            to_date="20240430",
            company="My Company"
        )
        self.assertIn("<SVFROMDATE>20240401</SVFROMDATE>", query)
        self.assertIn("<SVTODATE>20240430</SVTODATE>", query)
        self.assertNotIn("<SVCURRENTCOMPANY>My Company</SVCURRENTCOMPANY>", query)
        self.assertNotIn("ALTERID", query)
        self.assertNotIn("<FILTER>FilterByVoucherType</FILTER>", query)
        self.assertIn("ALLINVENTORYENTRIES.LIST.STOCKITEMNAME", query)
        self.assertIn("ALLLEDGERENTRIES.LIST.LEDGERNAME", query)
        self.assertNotIn("ALLINVENTORYENTRIES.LIST</FETCH>", query)
        self.assertNotIn("EFFECTIVEDATE", query)
        self.assertNotIn("MASTERID", query)

    def test_voucher_screen_query_filters_types_and_fetches_only_screen_fields(self):
        query = build_vouchers_query(voucher_types=("RICE SALES", "RICE SALES TAXABLE"))
        self.assertIn("<FILTER>FilterByVoucherType</FILTER>", query)
        self.assertIn('$$IsEqual:$VoucherTypeName:"RICE SALES"', query)
        self.assertIn('$$IsEqual:$VoucherTypeName:"RICE SALES TAXABLE"', query)
        self.assertIn("ALLINVENTORYENTRIES.LIST.BATCHALLOCATIONS.LIST.BATCHNAME", query)
        self.assertNotIn("EWAYBILLDETAILS.LIST</FETCH>", query)

    def test_non_rice_sales_vouchers_filtered_out(self):
        sample_xml = """<ENVELOPE>
          <BODY><DATA><COLLECTION>
            <VOUCHER VCHTYPE="Receipt">
              <VOUCHERNUMBER>RCT-001</VOUCHERNUMBER>
              <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
            </VOUCHER>
            <VOUCHER VCHTYPE="Sales">
              <VOUCHERNUMBER>INV-999</VOUCHERNUMBER>
              <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
            </VOUCHER>
            <VOUCHER VCHTYPE="RICE SALES">
              <VOUCHERNUMBER>RICE-001</VOUCHERNUMBER>
              <VOUCHERTYPENAME>RICE SALES</VOUCHERTYPENAME>
              <ALTERID>12345</ALTERID>
              <GUID>rice-guid-1</GUID>
              <DATE>20240420</DATE>
            </VOUCHER>
          </COLLECTION></DATA></BODY>
        </ENVELOPE>"""
        vouchers = parse_tally_vouchers_xml(sample_xml)
        self.assertEqual(len(vouchers), 3)
        self.assertEqual(
            [voucher["voucher_type"] for voucher in vouchers],
            ["Receipt", "Sales", "RICE SALES"]
        )
        self.assertNotIn("alter_id", vouchers[2])


    def test_tally_is_available_when_port_closed(self):
        from src.tally.client import TallyClient
        # Port 59999 is guaranteed to not be running Tally
        client = TallyClient(host="127.0.0.1", port=59999)
        self.assertFalse(client.is_available(timeout=0.2))
        ok, msg = client.check_connection()
        self.assertFalse(ok)
        self.assertIn("Could not connect to Tally Prime", msg)

    def test_vouchers_reports_unavailable_tally_without_cache_fallback(self):
        from fastapi import HTTPException
        from unittest.mock import patch
        from api import get_vouchers

        with patch("src.api.routers.vouchers.TallyClient") as tally_client:
            tally_client.return_value.is_available.return_value = False
            with self.assertRaises(HTTPException) as raised:
                get_vouchers()

        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("Tally Prime is not reachable", raised.exception.detail)

    def test_vouchers_are_fetched_without_company_identity_verification(self):
        from unittest.mock import patch
        from api import get_vouchers

        voucher = {"guid": "voucher-guid", "voucher_number": "INV-1"}
        with patch("src.api.routers.vouchers.TallyClient") as tally_client:
            client = tally_client.return_value
            client.is_available.return_value = True
            client.fetch_vouchers.return_value = [voucher]

            result = get_vouchers()

        tally_client.assert_called_once_with()
        client.fetch_vouchers.assert_called_once_with(
            voucher_types=("RICE SALES", "RICE SALES TAXABLE"),
        )
        self.assertEqual(result["source"], "live")
        self.assertEqual(result["total"], 1)
        self.assertNotIn("returned", result)
        self.assertEqual(result["vouchers"], [voucher])

    def test_voucher_endpoint_has_no_server_side_search_or_pagination(self):
        from api import app

        parameters = app.openapi()["paths"]["/api/vouchers"]["get"].get("parameters", [])
        self.assertEqual(parameters, [])

    def test_only_voucher_company_and_health_routes_are_exposed(self):
        from api import app

        paths = set(app.openapi()["paths"])
        self.assertIn("/api/vouchers", paths)
        self.assertIn("/api/company/active", paths)
        self.assertIn("/api/settings/company", paths)
        self.assertIn("get", app.openapi()["paths"]["/api/settings/company"])
        self.assertNotIn("post", app.openapi()["paths"]["/api/settings/company"])
        self.assertNotIn("/api/sync", paths)
        self.assertNotIn("/api/status", paths)
        self.assertNotIn("/api/data/clear", paths)

    def test_company_profile_reads_matching_json_and_falls_back_to_python_defaults(self):
        import json
        import tempfile
        from unittest.mock import patch
        from api import get_company_profile
        from src.api.schemas import CompanyProfileModel

        company_id = "a" * 64
        active_company = {
            "company_id": company_id,
            "company_name": "TEST ENTERPRISE MILL (2026 - 2027)",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            profile_path = config_dir / "company_profile.json"
            profile_path.write_text(json.dumps({
                "company_name": "Test Enterprise Mill",
                "tagline": "Top Quality Rice",
                "address": "APMC Yard, Yard 5",
                "gstin": "29AABCL1234F1Z5",
            }), encoding="utf-8")

            with patch("config.settings.settings.base_dir", Path(temp_dir)), \
                    patch("src.api.routers.company.require_active_company", return_value=active_company):
                loaded = get_company_profile(company_id=company_id)
                self.assertEqual(loaded["tagline"], "Top Quality Rice")

                profile_path.write_text(json.dumps({"company_name": "Other Mill", "address": "Other Road"}), encoding="utf-8")
                fallback = get_company_profile(company_id=company_id)

        self.assertEqual(loaded["company_name"], "Test Enterprise Mill")
        self.assertEqual(loaded["address"], "APMC Yard, Yard 5")
        self.assertEqual(fallback["company_name"], "TEST ENTERPRISE MILL (2026 - 2027)")
        self.assertEqual(fallback["address"], CompanyProfileModel().address)

    def test_company_normalization_and_matching(self):
        from src.utils.company_helper import verify_company_match

        # Exact match
        ok, msg = verify_company_match("Sri Lakshmi Modern Rice Mill", "Sri Lakshmi Modern Rice Mill")
        self.assertTrue(ok)
        self.assertIsNone(msg)

        # Case-insensitive match
        ok, msg = verify_company_match("SRI LAKSHMI MODERN RICE MILL", "sri lakshmi modern rice mill")
        self.assertTrue(ok)

        # Match with Tally Prime date/financial year suffix
        ok, msg = verify_company_match("Sri Lakshmi Modern Rice Mill (2024-2025)", "Sri Lakshmi Modern Rice Mill")
        self.assertTrue(ok)

        ok, msg = verify_company_match("Sri Lakshmi Modern Rice Mill (2026 - 2027)", "Sri Lakshmi Modern Rice Mill")
        self.assertTrue(ok)

        ok, msg = verify_company_match("Sri Lakshmi Modern Rice Mill (from 1-Apr-2024)", "Sri Lakshmi Modern Rice Mill")
        self.assertTrue(ok)

        # Mismatch between totally different companies
        ok, msg = verify_company_match("ABC Agro Industries", "Sri Lakshmi Modern Rice Mill")
        self.assertFalse(ok)
        self.assertIn("does not match", msg)

        ok, _ = verify_company_match("Acme Pvt Ltd", "Acme")
        self.assertFalse(ok, "Company names must not pass safety checks by substring alone")

    def test_parsed_voucher_uses_canonical_party_shape(self):
        xml = """<ENVELOPE><BODY><DATA><COLLECTION><VOUCHER VCHTYPE="RICE SALES">
          <VOUCHERNUMBER>INV-001</VOUCHERNUMBER><VOUCHERTYPENAME>RICE SALES</VOUCHERTYPENAME>
          <DATE>20240415</DATE><GUID>test-guid</GUID>
          <PARTYLEDGERNAME>Customer Ledger</PARTYLEDGERNAME><PARTYNAME>Customer</PARTYNAME>
          <PARTYGSTIN>GSTIN-1</PARTYGSTIN><STATENAME>Karnataka</STATENAME>
        </VOUCHER></COLLECTION></DATA></BODY></ENVELOPE>"""
        vouchers = parse_tally_vouchers_xml(xml)
        self.assertEqual(len(vouchers), 1)
        self.assertEqual(vouchers[0]["party"]["name"], "Customer")
        self.assertEqual(vouchers[0]["party"]["ledger_name"], "Customer Ledger")
        self.assertEqual(vouchers[0]["party"]["gstin"], "GSTIN-1")
        self.assertEqual(vouchers[0]["party"]["state"], "Karnataka")
        self.assertNotIn("company_name", vouchers[0])
        self.assertNotIn("party_name", vouchers[0])
        self.assertNotIn("party_gstin", vouchers[0])
        self.assertNotIn("items", vouchers[0])
        self.assertNotIn("source", vouchers[0])






    def test_active_company_context_uses_current_tally_company(self):
        from unittest.mock import patch
        from src.utils.active_company import company_id_for_name, get_active_company_context

        with patch("config.settings.settings.tally.use_odbc", False), \
                patch("src.utils.active_company.TallyClient") as tally_client:
            tally_client.return_value.is_available.return_value = True
            tally_client.return_value.get_active_company.return_value = "Test Mill"
            context = get_active_company_context()

        self.assertEqual(context["active_company"], {
            "company_id": company_id_for_name("Test Mill"),
            "company_name": "Test Mill",
        })
        self.assertTrue(context["tally_online"])

    def test_active_company_ids_are_case_and_whitespace_insensitive(self):
        from src.utils.active_company import company_id_for_name

        self.assertEqual(
            company_id_for_name("Acme   Mill"),
            company_id_for_name(" ACME MILL ")
        )
        self.assertNotEqual(
            company_id_for_name("Acme Mill"),
            company_id_for_name("Acme Mill (2025)")
        )




if __name__ == "__main__":
    unittest.main()
