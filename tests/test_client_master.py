"""Unit and integration tests for Client Master (MODULE-011)."""

from __future__ import annotations

import json
import sqlite3
import unittest

from client_import_service import save_client_import, validate_client_import
from client_master_service import (
    activate_client_master,
    ai_validate_client,
    approve_client_master,
    client_has_active_projects,
    client_report,
    deactivate_client_master,
    ensure_client_master_schema,
    export_clients_csv,
    generate_client_code,
    get_client_master,
    list_client_contacts,
    list_clients_master,
    save_client_master,
    soft_delete_client_master,
    user_can_client_master,
    validate_client_uniqueness,
)


def _sample_form(**overrides):
    form = {
        "client_name": "Metro Infrastructure Ltd",
        "legal_name": "Metro Infrastructure Private Limited",
        "company_name": "Metro Infrastructure",
        "client_type": "Corporate",
        "industry": "Infrastructure",
        "gst_number": "29ABCDE1234F1Z5",
        "pan_number": "ABCDE1234F",
        "email": "billing@metroinfra.in",
        "mobile": "9876543210",
        "billing_address": "12 MG Road, Bengaluru",
        "city": "Bengaluru",
        "state": "Karnataka",
        "pin_code": "560001",
        "status": "Active",
        "contact_name[]": ["Rajesh Kumar"],
        "contact_email[]": ["rajesh@metroinfra.in"],
        "contact_mobile[]": ["9876543210"],
        "contact_primary_index": "0",
        "address_line1[]": ["12 MG Road"],
        "address_type[]": ["Billing"],
        "address_city[]": ["Bengaluru"],
        "address_state[]": ["Karnataka"],
        "address_pin_code[]": ["560001"],
        "address_primary_index": "0",
    }
    form.update(overrides)
    return form


class ClientMasterSchemaTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_client_master_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_schema_has_module011_columns(self):
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(clients)").fetchall()}
        for col in (
            "client_code",
            "client_name",
            "legal_name",
            "client_type",
            "gst_number",
            "pan_number",
            "billing_address",
            "bank_name",
            "company_id",
            "approval_status",
            "created_by",
            "is_deleted",
        ):
            self.assertIn(col, cols)

    def test_child_tables_exist(self):
        tables = {
            row[0]
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        self.assertIn("client_contacts", tables)
        self.assertIn("client_addresses", tables)
        self.assertIn("client_bank_details", tables)


class ClientMasterValidationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_client_master_schema(self.conn)
        self.conn.execute(
            """
            CREATE TABLE projects(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT,
                client_id INTEGER,
                status TEXT
            )
            """
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_unique_client_code_and_gst(self):
        save_client_master(self.conn, _sample_form(client_code="CLT201"), "creator")
        self.conn.commit()
        with self.assertRaises(ValueError):
            validate_client_uniqueness(
                self.conn,
                client_code="CLT201",
                gst_number="29ABCDE1234F1Z5",
            )
        with self.assertRaises(ValueError):
            validate_client_uniqueness(
                self.conn,
                client_code="CLT202",
                gst_number="29ABCDE1234F1Z5",
            )

    def test_generate_client_code_sequence(self):
        code1 = generate_client_code(self.conn)
        save_client_master(self.conn, _sample_form(client_code=code1), "creator")
        self.conn.commit()
        code2 = generate_client_code(self.conn)
        self.assertNotEqual(code1, code2)


class ClientMasterCrudTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_client_master_schema(self.conn)
        self.conn.execute(
            """
            CREATE TABLE projects(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT,
                client_id INTEGER,
                status TEXT
            )
            """
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_save_list_get_with_contacts_and_addresses(self):
        cid = save_client_master(self.conn, _sample_form(client_code="CLT301"), "creator")
        self.conn.commit()
        row = get_client_master(self.conn, cid)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["client_name"], "Metro Infrastructure Ltd")
        self.assertEqual(len(row["contacts"]), 1)
        self.assertEqual(len(row["addresses"]), 1)
        listing = list_clients_master(self.conn, search="Metro")
        self.assertEqual(listing["total"], 1)

    def test_lifecycle_and_soft_delete_blocked_by_active_project(self):
        cid = save_client_master(self.conn, _sample_form(client_code="CLT302"), "creator")
        self.conn.commit()
        approve_client_master(self.conn, cid, "approver")
        deactivate_client_master(self.conn, cid, "admin")
        activate_client_master(self.conn, cid, "admin")
        self.conn.commit()
        self.conn.execute(
            "INSERT INTO projects(project_name, client_id, status) VALUES(?,?,?)",
            ("Highway Phase 1", cid, "Active"),
        )
        self.conn.commit()
        self.assertTrue(client_has_active_projects(self.conn, cid))
        with self.assertRaises(ValueError):
            soft_delete_client_master(self.conn, cid, "deleter")
        self.conn.execute("UPDATE projects SET status='Completed' WHERE client_id=?", (cid,))
        self.conn.commit()
        soft_delete_client_master(self.conn, cid, "deleter")
        self.conn.commit()
        self.assertIsNone(get_client_master(self.conn, cid))


class ClientMasterImportTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_client_master_schema(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_import_validate_and_save(self):
        rows = [
            {
                "_row_num": 2,
                "client_code": "CLT401",
                "client_name": "Import Client A",
                "gst_number": "29AAAAA1111A1Z5",
                "status": "Active",
            }
        ]
        val = validate_client_import(self.conn, rows)
        self.assertTrue(val["ok"])
        result = save_client_import(self.conn, val["parsed_rows"], username="importer", filename="test.xlsx")
        self.conn.commit()
        self.assertEqual(result["imported"], 1)
        listing = list_clients_master(self.conn, search="Import Client")
        self.assertEqual(listing["total"], 1)


class ClientMasterPermissionTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_client_master_schema(self.conn)
        self.conn.execute(
            """
            CREATE TABLE user_tab_permissions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                endpoint TEXT,
                tab_label TEXT,
                granted INTEGER,
                action_flags TEXT,
                created_at TEXT
            )
            """
        )
        flags = json.dumps(
            {
                "view": True,
                "create": True,
                "edit": True,
                "delete": False,
                "import": True,
                "export": True,
                "approve": False,
                "activate": True,
                "deactivate": True,
                "search": True,
                "filter": True,
            }
        )
        self.conn.execute(
            "INSERT INTO user_tab_permissions(user_id, endpoint, tab_label, granted, action_flags, created_at) "
            "VALUES (?, 'client_master', 'Client Master', 1, ?, datetime('now'))",
            (5, flags),
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_permission_endpoint_client_master(self):
        self.assertTrue(user_can_client_master(self.conn, 1, "view", is_admin=True))
        self.assertTrue(user_can_client_master(self.conn, 5, "view", is_admin=False))
        self.assertTrue(user_can_client_master(self.conn, 5, "import", is_admin=False))
        self.assertFalse(user_can_client_master(self.conn, 5, "approve", is_admin=False))


class ClientMasterReportTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_client_master_schema(self.conn)
        save_client_master(
            self.conn,
            _sample_form(client_code="CLT501", status="Active"),
            "creator",
        )
        save_client_master(
            self.conn,
            _sample_form(
                client_code="CLT502",
                client_name="Inactive Client",
                gst_number="29BBBBB2222B2Z5",
                pan_number="BBBBB2222B",
                status="Inactive",
            ),
            "creator",
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_reports_and_export(self):
        active = client_report(self.conn, "active")
        self.assertEqual(len(active), 1)
        contacts = client_report(self.conn, "contacts")
        self.assertGreaterEqual(len(contacts), 1)
        csv_text = export_clients_csv(self.conn)
        self.assertIn("CLT501", csv_text)

    def test_ai_validate(self):
        result = ai_validate_client(
            self.conn,
            form={"client_name": "Test", "gst_number": "INVALID"},
        )
        self.assertIn("issues", result)
        self.assertIn("missing", result)


if __name__ == "__main__":
    unittest.main()
