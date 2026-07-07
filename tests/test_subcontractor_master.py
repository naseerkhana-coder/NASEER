"""Unit and integration tests for Subcontractor Master (MODULE-013)."""

from __future__ import annotations

import sqlite3
import unittest

from subcontractor_import_service import save_subcontractor_import, validate_subcontractor_import
from subcontractor_master_service import (
    activate_subcontractor_master,
    ai_validate_subcontractor,
    approve_subcontractor_master,
    deactivate_subcontractor_master,
    ensure_subcontractor_master_schema,
    export_subcontractors_csv,
    generate_subcontractor_master_code,
    get_subcontractor_master,
    list_subcontractors_master,
    save_subcontractor_master,
    soft_delete_subcontractor_master,
    subcontractor_has_transactions,
    subcontractor_report,
    user_can_subcontractor_master,
    validate_labour_license,
    validate_subcontractor_uniqueness,
)


def _base_form(**overrides):
    form = {
        "subcontractor_code": "SC901",
        "subcontractor_name": "Alpha Civil Contractors",
        "trade_categories[]": ["Concrete"],
        "gst_number": "22AAAAA0000A1Z5",
        "status": "Active",
        "retention_percent": "5",
        "security_deposit": "50000",
    }
    form.update(overrides)
    return form


class SubcontractorMasterSchemaTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_subcontractor_master_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_schema_has_module013_columns(self):
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(subcontractors)").fetchall()}
        for col in (
            "subcontractor_code",
            "classification",
            "trade_categories",
            "retention_percent",
            "security_deposit",
            "insurance_policy_no",
            "labour_license_no",
            "approval_status",
            "is_approved",
            "is_blacklisted",
            "is_deleted",
        ):
            self.assertIn(col, cols)

    def test_child_tables_exist(self):
        tables = {
            row[0]
            for row in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        self.assertIn("subcontractor_contacts", tables)
        self.assertIn("subcontractor_addresses", tables)
        self.assertIn("subcontractor_bank_accounts", tables)
        self.assertIn("subcontractor_trades", tables)


class SubcontractorMasterValidationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_subcontractor_master_schema(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_unique_code_and_gst(self):
        save_subcontractor_master(self.conn, _base_form(), "creator")
        self.conn.commit()
        with self.assertRaises(ValueError):
            validate_subcontractor_uniqueness(
                self.conn, subcontractor_code="SC901", gst_number=""
            )
        with self.assertRaises(ValueError):
            validate_subcontractor_uniqueness(
                self.conn, subcontractor_code="SC902", gst_number="22AAAAA0000A1Z5"
            )

    def test_trade_required(self):
        with self.assertRaises(ValueError):
            save_subcontractor_master(
                self.conn,
                {
                    "subcontractor_code": "SC902",
                    "subcontractor_name": "No Trade Co",
                    "status": "Active",
                },
                "tester",
            )

    def test_labour_license_validation(self):
        validate_labour_license("LL-MAH-12345")
        with self.assertRaises(ValueError):
            validate_labour_license("x")


class SubcontractorMasterCrudTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_subcontractor_master_schema(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_save_list_get(self):
        sid = save_subcontractor_master(
            self.conn,
            _base_form(
                phone="9876543210",
                email="alpha@example.com",
                labour_license_no="LL-001",
                labour_license_expiry="2027-01-01",
            ),
            "creator",
        )
        self.conn.commit()
        row = get_subcontractor_master(self.conn, sid)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["subcontractor_code"], "SC901")
        self.assertEqual(float(row["retention_percent"]), 5.0)
        self.assertIn("Concrete", row["trade_categories_list"])
        listing = list_subcontractors_master(self.conn, search="Alpha")
        self.assertEqual(listing["total"], 1)

    def test_auto_code_generation(self):
        code = generate_subcontractor_master_code(self.conn, "Beta Builders")
        self.assertTrue(code.startswith("BE") or code.startswith("BB") or len(code) >= 5)

    def test_soft_delete_blocked_by_worker(self):
        sid = save_subcontractor_master(self.conn, _base_form(subcontractor_code="SC903"), "creator")
        self.conn.execute(
            """
            CREATE TABLE workers(id INTEGER PRIMARY KEY, subcontractor_id INTEGER, worker_name TEXT)
            """
        )
        self.conn.execute("INSERT INTO workers(subcontractor_id, worker_name) VALUES(?,?)", (sid, "W1"))
        self.conn.commit()
        self.assertTrue(subcontractor_has_transactions(self.conn, sid))
        with self.assertRaises(ValueError):
            soft_delete_subcontractor_master(self.conn, sid, "admin")

    def test_activate_deactivate_approve(self):
        sid = save_subcontractor_master(
            self.conn, _base_form(subcontractor_code="SC904", status="Inactive"), "creator"
        )
        self.conn.commit()
        activate_subcontractor_master(self.conn, sid, "admin")
        approve_subcontractor_master(self.conn, sid, "admin")
        deactivate_subcontractor_master(self.conn, sid, "admin")
        row = get_subcontractor_master(self.conn, sid)
        assert row is not None
        self.assertEqual(row["status"], "Inactive")
        self.assertEqual(row["approval_status"], "Approved")


class SubcontractorImportTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_subcontractor_master_schema(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_import_row(self):
        rows = [
            {
                "_row_num": 2,
                "subcontractor_code": "SC801",
                "subcontractor_name": "Import Sub Co",
                "trade_categories": "Concrete,Brick Work",
                "status": "Active",
            }
        ]
        val = validate_subcontractor_import(self.conn, rows)
        self.assertTrue(val.get("ok"), val.get("errors"))
        result = save_subcontractor_import(self.conn, val["parsed_rows"], username="importer")
        self.conn.commit()
        self.assertEqual(result["imported"], 1)


class SubcontractorReportTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_subcontractor_master_schema(self.conn)
        save_subcontractor_master(
            self.conn,
            _base_form(subcontractor_code="SC701", retention_percent="10", security_deposit="25000"),
            "creator",
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_reports(self):
        active = subcontractor_report(self.conn, "active")
        self.assertEqual(len(active), 1)
        retention = subcontractor_report(self.conn, "retention_summary")
        self.assertGreaterEqual(float(retention[0]["retention_percent"]), 10.0)
        deposit = subcontractor_report(self.conn, "security_deposit_summary")
        self.assertGreaterEqual(float(deposit[0]["security_deposit"]), 25000.0)

    def test_export_csv(self):
        csv_text = export_subcontractors_csv(self.conn)
        self.assertIn("subcontractor_code", csv_text)
        self.assertIn("SC701", csv_text)


class SubcontractorAiTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_subcontractor_master_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_ai_validate_graceful(self):
        result = ai_validate_subcontractor(
            self.conn,
            form={"subcontractor_name": "Test Co", "trade_categories[]": ["Concrete"]},
        )
        self.assertIn("ok", result)
        self.assertIn("ai_enriched", result)


class SubcontractorPermissionTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_subcontractor_master_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_admin_has_access(self):
        self.assertTrue(user_can_subcontractor_master(self.conn, None, "view", is_admin=True))


if __name__ == "__main__":
    unittest.main()
