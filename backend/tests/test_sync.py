"""Unit tests for Tally voucher parsing and state management."""
import unittest
from pathlib import Path

from src.sync.state import SyncStateManager
from src.tally.parser import parse_tally_vouchers_xml, parse_tally_date
from src.tally.queries import build_sales_vouchers_query


class TestTallySync(unittest.TestCase):

    def setUp(self):
        self.mock_xml_path = Path(__file__).parent / "mock_sales_vouchers.xml"
        with open(self.mock_xml_path, "r", encoding="utf-8") as f:
            self.mock_xml_content = f.read()

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
        query = build_sales_vouchers_query(
            from_date="20240401",
            to_date="20240430",
            from_alter_id=10045,
            company="My Company"
        )
        self.assertIn("<SVFROMDATE>20240401</SVFROMDATE>", query)
        self.assertIn("<SVTODATE>20240430</SVTODATE>", query)
        self.assertIn("<SVCURRENTCOMPANY>My Company</SVCURRENTCOMPANY>", query)
        self.assertIn("$AlterID &gt; 10045", query)
        self.assertIn('($VoucherTypeName = "RICE SALES") OR ($VoucherTypeName = "RICE SALES TAXABLE")', query)

    def test_mock_xml_parsing(self):
        vouchers = parse_tally_vouchers_xml(self.mock_xml_content)
        self.assertEqual(len(vouchers), 2)

        # Inspect Voucher 1 (RICE SALES, Local GST: CGST + SGST)
        v1 = vouchers[0]
        self.assertEqual(v1["voucher_number"], "INV-2024-001")
        self.assertEqual(v1["voucher_type"], "RICE SALES")
        self.assertEqual(v1["date"], "2024-04-15")
        self.assertEqual(v1["alter_id"], 10045)
        self.assertEqual(v1["party_name"], "Acme Industrial Solutions Pvt Ltd")
        self.assertEqual(v1["party"]["name"], "Acme Industrial Solutions Pvt Ltd")
        self.assertEqual(v1["party"]["gstin"], "27AABCA1234F1Z5")
        self.assertEqual(v1["vehicle_number"], "MH-12-RN-8821")
        self.assertEqual(v1["total_amount"], 11800.00)
        self.assertEqual(v1["taxes"]["cgst"], 900.00)
        self.assertEqual(v1["taxes"]["sgst"], 900.00)
        self.assertEqual(v1["taxes"]["igst"], 0.00)

        # Inspect Line items & inventory_entries alias
        self.assertEqual(len(v1["items"]), 1)
        self.assertEqual(len(v1["inventory_entries"]), 1)
        item = v1["items"][0]
        self.assertEqual(item["item_name"], "Heavy Duty Circuit Breaker 32A")
        self.assertEqual(item["quantity"], 10.0)
        self.assertEqual(item["rate"], 1000.0)
        self.assertEqual(item["unit"], "Nos")
        self.assertEqual(item["amount"], 10000.0)
        self.assertEqual(len(item["batches"]), 1)
        self.assertEqual(item["batches"][0]["batch_name"], "BATCH-APR-24")

        # Inspect Voucher 2 (RICE SALES TAXABLE, Interstate GST: IGST)
        v2 = vouchers[1]
        self.assertEqual(v2["voucher_number"], "INV-2024-002")
        self.assertEqual(v2["voucher_type"], "RICE SALES TAXABLE")
        self.assertEqual(v2["date"], "2024-04-16")
        self.assertEqual(v2["alter_id"], 10048)
        self.assertEqual(v2["party_name"], "Zenith Tech Labs Bangalore")
        self.assertEqual(v2["vehicle_number"], "KA-04-E-4590")
        self.assertEqual(v2["party"]["state"], "Karnataka")
        self.assertEqual(v2["total_amount"], 23600.00)
        self.assertEqual(v2["taxes"]["igst"], 3600.00)

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
              <GUID>rice-guid-1</GUID>
              <DATE>20240420</DATE>
            </VOUCHER>
          </COLLECTION></DATA></BODY>
        </ENVELOPE>"""
        vouchers = parse_tally_vouchers_xml(sample_xml)
        self.assertEqual(len(vouchers), 1)
        self.assertEqual(vouchers[0]["voucher_number"], "RICE-001")
        self.assertEqual(vouchers[0]["voucher_type"], "RICE SALES")

    def test_state_manager(self):
        temp_state_file = Path(__file__).parent / "temp_state.json"
        if temp_state_file.exists():
            temp_state_file.unlink()

        mgr = SyncStateManager(state_file=temp_state_file)
        self.assertEqual(mgr.get_last_alter_id(), 0)

        # Record a sync
        mgr.record_sync_success(new_alter_id=10048, count_synced=2)
        self.assertEqual(mgr.get_last_alter_id(), 10048)

        state = mgr.load_state()
        self.assertEqual(state["total_vouchers_synced"], 2)
        self.assertEqual(state["last_status"], "SUCCESS")

        # Cleanup
        if temp_state_file.exists():
            temp_state_file.unlink()

    def test_tally_is_available_when_port_closed(self):
        from src.tally.client import TallyClient
        # Port 59999 is guaranteed to not be running Tally
        client = TallyClient(host="127.0.0.1", port=59999)
        self.assertFalse(client.is_available(timeout=0.2))
        ok, msg = client.check_connection()
        self.assertFalse(ok)
        self.assertIn("Could not connect to Tally Prime", msg)

    def test_sample_vouchers_fallback_when_tally_offline(self):
        from api import get_sample_vouchers
        # Call sample vouchers (supports live Tally if online, or Firestore/mock fallback)
        res = get_sample_vouchers(limit=5)
        self.assertIn(res.get("source"), ("live", "firestore", "mock"))
        self.assertIsInstance(res.get("vouchers"), list)
        self.assertGreaterEqual(res.get("returned"), 0)

    def test_company_profile_get_and_save(self):
        from api import CompanyProfileModel, get_company_profile, update_company_profile
        test_payload = CompanyProfileModel(
            company_name="Test Enterprise Mill",
            tagline="Top Quality Rice",
            address="APMC Yard, Yard 5",
            gstin="29AABCL1234F1Z5"
        )
        save_res = update_company_profile(test_payload)
        self.assertIn(save_res.get("status"), ("SUCCESS", "PARTIAL_SUCCESS"))
        
        loaded = get_company_profile()
        self.assertEqual(loaded.get("company_name"), "Test Enterprise Mill")
        self.assertEqual(loaded.get("tagline"), "Top Quality Rice")

    def test_invoice_company_profile_does_not_select_tally_sync_company(self):
        from unittest.mock import patch
        from config.settings import settings
        from src.api.runtime import _save_company_profile
        from src.utils.company_helper import get_target_company_name

        with patch.object(settings.tally, "company", None):
            with patch("src.utils.company_helper.load_local_company_profile", return_value={
                "company_name": "Invoice Company"
            }):
                self.assertIsNone(get_target_company_name())

            with patch("src.api.runtime.save_local_company_profile") as save_profile:
                _save_company_profile({"company_name": "Invoice Company"})
                save_profile.assert_called_once_with({"company_name": "Invoice Company"})
                self.assertIsNone(settings.tally.company)

        with patch.object(settings.tally, "company", "Configured Tally Company"):
            self.assertEqual(get_target_company_name(), "Configured Tally Company")

    def test_firebase_client_thread_safe_initialization(self):
        import concurrent.futures
        from src.firebase.client import FirebaseClient

        def worker(i):
            client = FirebaseClient()
            client.initialize()
            return client.db is not None

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
            futures = [ex.submit(worker, i) for i in range(6)]
            results = [f.result() for f in futures]
            self.assertTrue(all(results))

    def test_company_normalization_and_matching(self):
        from src.utils.company_helper import normalize_company_name, verify_company_match

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

        ok, msg = verify_company_match("Sri Lakshmi Modern Rice Mill (from 1-Apr-2024)", "Sri Lakshmi Modern Rice Mill")
        self.assertTrue(ok)

        # Mismatch between totally different companies
        ok, msg = verify_company_match("ABC Agro Industries", "Sri Lakshmi Modern Rice Mill")
        self.assertFalse(ok)
        self.assertIn("does not match", msg)

    def test_vouchers_tagged_with_company_name(self):
        vouchers = parse_tally_vouchers_xml(self.mock_xml_content, company_name="Sri Lakshmi Modern Rice Mill")
        self.assertEqual(len(vouchers), 2)
        for v in vouchers:
            self.assertEqual(v["company_name"], "Sri Lakshmi Modern Rice Mill")

    def test_sync_engine_aborts_on_company_mismatch(self):
        from unittest.mock import MagicMock
        from src.sync.engine import SyncEngine

        mock_tally = MagicMock()
        # Simulate Tally being open on a different/wrong company
        mock_tally.get_active_company.return_value = "Competitor Rice Mill Ltd"
        mock_tally.fetch_sales_vouchers.return_value = []

        mock_firebase = MagicMock()
        mock_state = MagicMock()
        mock_state.get_last_alter_id.return_value = 100

        engine = SyncEngine(
            tally_client=mock_tally,
            firebase_client=mock_firebase,
            state_manager=mock_state,
            company="Sri Lakshmi Modern Rice Mill"
        )

        res = engine.run_sync()
        self.assertEqual(res["status"], "FAILED")
        self.assertIn("Security Guard", res["error"])
        self.assertIn("does NOT match", res["error"])
        # Ensure it NEVER queried vouchers or pushed anything to Firestore
        mock_tally.fetch_sales_vouchers.assert_not_called()
        mock_firebase.upsert_vouchers.assert_not_called()

    def test_state_manager_resets_alter_id_on_company_change(self):
        temp_state_file = Path(__file__).parent / "temp_company_state.json"
        if temp_state_file.exists():
            temp_state_file.unlink()

        try:
            mgr = SyncStateManager(state_file=temp_state_file)
            # Sync for Company A
            mgr.record_sync_success(new_alter_id=5000, count_synced=10, company_name="Company A")
            self.assertEqual(mgr.get_last_alter_id(company_name="Company A"), 5000)

            # Query for Company B -> must reset to 0 to prevent cross-company AlterID sequence corruption
            self.assertEqual(mgr.get_last_alter_id(company_name="Company B"), 0)
        finally:
            if temp_state_file.exists():
                temp_state_file.unlink()

    def test_deduplication_in_upsert_vouchers(self):
        from unittest.mock import MagicMock
        from src.firebase.client import FirebaseClient

        client = FirebaseClient()
        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_batch = MagicMock()
        mock_db.collection.return_value = mock_col
        mock_db.batch.return_value = mock_batch
        client._db = mock_db

        # Vouchers with duplicate invoice numbers, different alter_ids
        incoming = [
            {
                "doc_id": "doc_1",
                "voucher_number": "INV-101",
                "voucher_type": "RICE SALES",
                "company_name": "Test Mill",
                "date": "2024-04-01",
                "alter_id": 100
            },
            {
                "doc_id": "doc_1_newer",
                "voucher_number": "INV-101",
                "voucher_type": "RICE SALES",
                "company_name": "Test Mill",
                "date": "2024-04-01",
                "alter_id": 200
            },
            {
                "doc_id": "doc_2",
                "voucher_number": "INV-102",
                "voucher_type": "RICE SALES TAXABLE",
                "company_name": "Test Mill",
                "date": "2024-04-02",
                "alter_id": 150
            },
            {
                # Non-allowed voucher type should be discarded
                "doc_id": "doc_3",
                "voucher_number": "INV-103",
                "voucher_type": "BRAN SALES",
                "company_name": "Test Mill",
                "date": "2024-04-03",
                "alter_id": 160
            }
        ]

        count = client.upsert_vouchers(incoming)
        # Should only sync 2 unique valid vouchers (INV-101 with alter_id 200, and INV-102)
        self.assertEqual(count, 2)
        self.assertEqual(mock_batch.set.call_count, 2)

    def test_api_clear_and_cleanup_endpoints(self):
        from unittest.mock import patch, MagicMock
        from api import clear_firestore_data, cleanup_firestore_duplicates

        with patch("src.api.routers.firestore.FirebaseClient") as mock_fb_cls:
            mock_fb = MagicMock()
            mock_fb.clear_all_vouchers.return_value = 42
            mock_fb.cleanup_redundant_and_duplicate_vouchers.return_value = {
                "scanned": 100,
                "deleted_non_allowed": 10,
                "deleted_duplicates": 5,
                "total_deleted": 15,
                "remaining": 85
            }
            mock_fb_cls.return_value = mock_fb

            clear_res = clear_firestore_data()
            self.assertEqual(clear_res["status"], "SUCCESS")
            self.assertEqual(clear_res["deleted_count"], 42)

            cleanup_res = cleanup_firestore_duplicates()
            self.assertEqual(cleanup_res["status"], "SUCCESS")
            self.assertEqual(cleanup_res["details"]["total_deleted"], 15)


if __name__ == "__main__":
    unittest.main()
