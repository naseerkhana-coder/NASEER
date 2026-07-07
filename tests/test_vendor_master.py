"""Unit and integration tests for Vendor Master (MODULE-012)."""

from __future__ import annotations

import sqlite3
import unittest

from store_service import ensure_store_schema, save_vendor
from vendor_import_service import save_vendor_import, validate_vendor_import
from vendor_master_service import (
    activate_vendor_master,
    ai_validate_vendor,
    approve_vendor_master,
    deactivate_vendor_master,
    ensure_vendor_master_schema,
    export_vendors_csv,
    get_vendor_master,
    list_vendors_master,
    save_vendor_master,
    soft_delete_vendor_master,
    user_can_vendor_master,
    validate_vendor_uniqueness,
    vendor_has_transactions,
    vendor_report,
)


class VendorMasterSchemaTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_vendor_master_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_schema_has_module012_columns(self):
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(vendors)").fetchall()}
        for col in (
            "status",
            "approval_status",
            "msme_number",
            "cin_number",
            "payment_terms",
            "credit_limit",
            "rating",
            "is_approved",
            "is_blacklisted",
            "is_deleted",
            "created_by",
            "modified_by",
        ):
            self.assertIn(col, cols)

    def test_child_tables_exist(self):
        tables = {
            row[0]
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        self.assertIn("vendor_contacts", tables)
        self.assertIn("vendor_addresses", tables)
        self.assertIn("vendor_bank_accounts", tables)


class VendorMasterValidationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_vendor_master_schema(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_unique_code_and_gstin(self):
        form = {
            "vendor_code": "VEN201",
            "vendor_name": "Alpha Supplies",
            "gstin": "22AAAAA0000A1Z5",
            "status": "Active",
        }
        save_vendor_master(self.conn, form, "creator")
        self.conn.commit()
        with self.assertRaises(ValueError):
            validate_vendor_uniqueness(
                self.conn,
                vendor_code="VEN201",
                gstin="",
            )
        with self.assertRaises(ValueError):
            validate_vendor_uniqueness(
                self.conn,
                vendor_code="VEN202",
                gstin="22AAAAA0000A1Z5",
            )

    def test_invalid_gst_rejected(self):
        with self.assertRaises(ValueError):
            save_vendor_master(
                self.conn,
                {
                    "vendor_code": "VEN203",
                    "vendor_name": "Bad GST Co",
                    "gstin": "INVALID",
                    "status": "Active",
                },
                "tester",
            )


class VendorMasterCrudTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_vendor_master_schema(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_save_list_get_vendor(self):
        vid = save_vendor_master(
            self.conn,
            {
                "vendor_code": "VEN301",
                "vendor_name": "Beta Traders",
                "phone": "9876543210",
                "email": "beta@example.com",
                "address": "Plot 12",
                "city": "Pune",
                "state": "Maharashtra",
                "pincode": "411001",
                "payment_terms": "Net 30",
                "credit_limit": "100000",
                "rating": "4.5",
                "status": "Active",
                "vendor_types[]": ["Supplier"],
            },
            "creator",
        )
        self.conn.commit()
        row = get_vendor_master(self.conn, vid)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["code"], "VEN301")
        self.assertEqual(row["payment_terms"], "Net 30")
        self.assertEqual(float(row["credit_limit"]), 100000.0)
        self.assertTrue(row["contacts"])
        self.assertTrue(row["addresses"])

    def test_activate_deactivate(self):
        vid = save_vendor_master(
            self.conn,
            {"vendor_code": "VEN302", "vendor_name": "Gamma Corp", "status": "Active"},
            "creator",
        )
        self.conn.commit()
        deactivate_vendor_master(self.conn, vid, "admin")
        self.conn.commit()
        row = get_vendor_master(self.conn, vid)
        assert row is not None
        self.assertEqual(row["status"], "Inactive")
        activate_vendor_master(self.conn, vid, "admin")
        self.conn.commit()
        row = get_vendor_master(self.conn, vid)
        assert row is not None
        self.assertEqual(row["status"], "Active")

    def test_approve_vendor(self):
        vid = save_vendor_master(
            self.conn,
            {"vendor_code": "VEN303", "vendor_name": "Delta Services", "status": "Active"},
            "creator",
        )
        self.conn.commit()
        approve_vendor_master(self.conn, vid, "approver")
        self.conn.commit()
        row = get_vendor_master(self.conn, vid)
        assert row is not None
        self.assertEqual(row["approval_status"], "Approved")
        self.assertEqual(int(row["is_approved"]), 1)

    def test_soft_delete_blocked_with_po(self):
        ensure_store_schema(self.conn)
        vid = save_vendor_master(
            self.conn,
            {"vendor_code": "VEN304", "vendor_name": "PO Linked Vendor", "status": "Active"},
            "creator",
        )
        self.conn.execute(
            "INSERT INTO purchase_orders(po_number, vendor_id, order_date, approval_status) VALUES(?,?,?,?)",
            ("PO-TEST-001", vid, "2026-01-01", "Approved"),
        )
        self.conn.commit()
        self.assertTrue(vendor_has_transactions(self.conn, vid))
        with self.assertRaises(ValueError):
            soft_delete_vendor_master(self.conn, vid, "admin")

    def test_search_listing(self):
        save_vendor_master(
            self.conn,
            {"vendor_code": "VEN305", "vendor_name": "Searchable Vendor", "city": "Chennai", "status": "Active"},
            "creator",
        )
        self.conn.commit()
        listing = list_vendors_master(self.conn, search="Searchable")
        self.assertEqual(listing["total"], 1)
        self.assertEqual(listing["items"][0]["name"], "Searchable Vendor")


class VendorMasterImportTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_vendor_master_schema(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_import_rows(self):
        rows = [
            {
                "_row_num": 2,
                "vendor_code": "VEN401",
                "vendor_name": "Import Vendor A",
                "gstin": "",
                "status": "Active",
            },
            {
                "_row_num": 3,
                "vendor_code": "VEN402",
                "vendor_name": "Import Vendor B",
                "status": "Active",
            },
        ]
        val = validate_vendor_import(self.conn, rows)
        self.assertTrue(val["ok"])
        result = save_vendor_import(self.conn, val["parsed_rows"], username="importer")
        self.conn.commit()
        self.assertEqual(result["imported"], 2)
        listing = list_vendors_master(self.conn, per_page=100)
        self.assertEqual(listing["total"], 2)


class VendorMasterExportReportTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_vendor_master_schema(self.conn)
        save_vendor_master(
            self.conn,
            {"vendor_code": "VEN501", "vendor_name": "Report Vendor", "rating": "3", "status": "Active"},
            "creator",
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_csv_export(self):
        csv_text = export_vendors_csv(self.conn)
        self.assertIn("VEN501", csv_text)
        self.assertIn("Report Vendor", csv_text)

    def test_active_report(self):
        rows = vendor_report(self.conn, "active")
        self.assertEqual(len(rows), 1)


class VendorMasterAiTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_vendor_master_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_ai_validate_missing_name(self):
        result = ai_validate_vendor(self.conn, form={"vendor_code": "VEN601"})
        self.assertFalse(result["ok"])
        self.assertTrue(result["issues"])


class VendorMasterPermissionTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_vendor_master_schema(self.conn)
        from user_permission_service import ensure_user_tab_permissions_schema

        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT)"
        )
        self.conn.execute("INSERT INTO users(id, username) VALUES(5, 'tester')")
        ensure_user_tab_permissions_schema(self.conn)
        self.conn.execute(
            """
            INSERT INTO user_tab_permissions(
                user_id, department_slug, tab_key, endpoint, granted, action_flags
            ) VALUES(?,?,?,?,?,?)
            """,
            (5, "settings", "vendor_master", "vendor_master", 1, '{"view":true,"create":true,"edit":false}'),
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_user_permission_check(self):
        self.assertTrue(user_can_vendor_master(self.conn, 5, "view"))
        self.assertTrue(user_can_vendor_master(self.conn, 5, "create"))
        self.assertFalse(user_can_vendor_master(self.conn, 5, "edit"))
        self.assertTrue(user_can_vendor_master(self.conn, 5, "view", is_admin=True))


class VendorLegacyCompatTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_vendor_master_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_legacy_save_vendor_still_works(self):
        class _Form:
            def get(self, key, default=None):
                data = {
                    "code": "VEN701",
                    "name": "Legacy Vendor",
                    "is_active": "1",
                    "vendor_type": "Supplier",
                }
                return data.get(key, default)

            def getlist(self, key):
                if key in ("vendor_types[]", "vendor_types"):
                    return ["Supplier"]
                return []

        vid = save_vendor(self.conn, _Form(), None)
        self.conn.commit()
        row = get_vendor_master(self.conn, vid)
        assert row is not None
        self.assertEqual(row["name"], "Legacy Vendor")


if __name__ == "__main__":
    unittest.main()
