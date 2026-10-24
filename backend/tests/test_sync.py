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
        self.assertIn("$$IsSales:$VoucherTypeName", query)

    def test_mock_xml_parsing(self):
        vouchers = parse_tally_vouchers_xml(self.mock_xml_content)
        self.assertEqual(len(vouchers), 2)

        # Inspect Voucher 1 (Local GST: CGST + SGST)
        v1 = vouchers[0]
        self.assertEqual(v1["voucher_number"], "INV-2024-001")
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

        # Inspect Voucher 2 (Interstate GST: IGST)
        v2 = vouchers[1]
        self.assertEqual(v2["voucher_number"], "INV-2024-002")
        self.assertEqual(v2["date"], "2024-04-16")
        self.assertEqual(v2["alter_id"], 10048)
        self.assertEqual(v2["party_name"], "Zenith Tech Labs Bangalore")
        self.assertEqual(v2["vehicle_number"], "KA-04-E-4590")
        self.assertEqual(v2["party"]["state"], "Karnataka")
        self.assertEqual(v2["total_amount"], 23600.00)
        self.assertEqual(v2["taxes"]["igst"], 3600.00)

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


if __name__ == "__main__":
    unittest.main()
