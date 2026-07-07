"""Unit and integration tests for Branch Master (MODULE-002)."""

from __future__ import annotations

import json
import sqlite3
import unittest

from branch_import_service import save_branch_import, validate_branch_import
from branch_master_service import (
    activate_branch_master,
    ai_validate_branch,
    approve_branch_master,
    branch_allows_transactions,
    branch_has_transactions,
    branch_report,
    deactivate_branch_master,
    ensure_branch_master_schema,
    export_branches_csv,
    get_branch_master,
    list_branches_master,
    reject_branch_master,
    save_branch_master,
    soft_delete_branch_master,
    user_can_branch_master,
    validate_branch_contact,
    validate_branch_uniqueness,
    validate_pin_code,
)
from company_master_service import ensure_company_master_schema, save_company
from user_permission_service import ensure_user_tab_permissions_schema


def _seed_company(conn) -> int:
    return save_company(
        conn,
        {
            "legal_name": "Gamma Infra Private Limited",
            "company_name": "Gamma Infra",
            "country": "India",
            "status": "Active",
            "email": "gamma@example.com",
        },
        "tester",
    )


class BranchMasterSchemaTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_branch_master_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_schema_has_module002_columns(self):
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(company_branches)").fetchall()}
        for col in (
            "company_id",
            "branch_code",
            "branch_name",
            "branch_type",
            "gst_number",
            "pan_number",
            "address_line1",
            "address_line2",
            "country",
            "state_region",
            "district",
            "city",
            "postal_code",
            "latitude",
            "longitude",
            "phone",
            "email",
            "branch_manager",
            "opening_date",
            "closing_date",
            "working_hours",
            "currency",
            "timezone",
            "status",
            "created_by",
            "modified_by",
            "created_at",
            "modified_at",
            "approval_status",
            "is_deleted",
        ):
            self.assertIn(col, cols)


class BranchMasterValidationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)
        ensure_branch_master_schema(self.conn)
        self.company_id = _seed_company(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_pin_and_contact_validation(self):
        validate_pin_code("400001", country="India")
        validate_branch_contact(email="branch@example.com", phone="+91 9876543210")
        with self.assertRaises(ValueError):
            validate_pin_code("12345", country="India")
        with self.assertRaises(ValueError):
            validate_branch_contact(email="bad-email")

    def test_unique_branch_code_per_company(self):
        form = {
            "company_id": self.company_id,
            "branch_code": "BR-001",
            "branch_name": "Mumbai Office",
            "country": "India",
            "status": "Active",
        }
        save_branch_master(self.conn, form, "creator")
        self.conn.commit()
        with self.assertRaises(ValueError):
            validate_branch_uniqueness(
                self.conn,
                company_id=self.company_id,
                branch_code="BR-001",
            )


class BranchMasterCrudTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)
        ensure_branch_master_schema(self.conn)
        self.company_id = _seed_company(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def _sample_form(self, **overrides):
        data = {
            "company_id": self.company_id,
            "branch_code": "BR-MUM-01",
            "branch_name": "Mumbai Branch",
            "branch_type": "Regional Office",
            "country": "India",
            "city": "Mumbai",
            "state_region": "Maharashtra",
            "postal_code": "400001",
            "phone": "+91 9876543210",
            "email": "mumbai@gamma.example.com",
            "currency": "INR",
            "timezone": "Asia/Kolkata",
            "status": "Active",
        }
        data.update(overrides)
        return data

    def test_create_update_workflow_and_pagination(self):
        bid = save_branch_master(self.conn, self._sample_form(), "creator")
        self.conn.commit()
        row = get_branch_master(self.conn, bid)
        self.assertIsNotNone(row)
        self.assertEqual(row["branch_name"], "Mumbai Branch")
        self.assertEqual(row["approval_status"], "Draft")

        save_branch_master(
            self.conn,
            self._sample_form(city="Navi Mumbai"),
            "editor",
            bid,
        )
        self.conn.commit()
        updated = get_branch_master(self.conn, bid)
        self.assertEqual(updated["city"], "Navi Mumbai")

        approve_branch_master(self.conn, bid, "approver")
        self.conn.commit()
        self.assertTrue(branch_allows_transactions(self.conn, bid))

        reject_branch_master(self.conn, bid, "approver", "Incomplete docs")
        self.conn.commit()
        self.assertFalse(branch_allows_transactions(self.conn, bid))

        approve_branch_master(self.conn, bid, "approver")
        self.conn.commit()

        deactivate_branch_master(self.conn, bid, "admin")
        self.conn.commit()
        self.assertFalse(branch_allows_transactions(self.conn, bid))

        activate_branch_master(self.conn, bid, "admin")
        self.conn.commit()
        self.assertTrue(branch_allows_transactions(self.conn, bid))

        listing = list_branches_master(self.conn, search="Mumbai", per_page=10)
        self.assertEqual(listing["total"], 1)

        soft_delete_branch_master(self.conn, bid, "deleter")
        self.conn.commit()
        self.assertIsNone(get_branch_master(self.conn, bid))
        deleted = get_branch_master(self.conn, bid, include_deleted=True)
        self.assertEqual(deleted["is_deleted"], 1)

    def test_auto_branch_code_when_blank(self):
        bid = save_branch_master(
            self.conn,
            self._sample_form(branch_code=""),
            "creator",
        )
        self.conn.commit()
        row = get_branch_master(self.conn, bid)
        self.assertTrue(row["branch_code"].startswith(f"BR-{self.company_id}-"))

    def test_export_csv(self):
        save_branch_master(self.conn, self._sample_form(), "creator")
        self.conn.commit()
        csv_text = export_branches_csv(self.conn)
        self.assertIn("branch_code", csv_text)
        self.assertIn("Mumbai Branch", csv_text)

    def test_transaction_guard_blocks_delete(self):
        self.conn.execute(
            """
            CREATE TABLE projects (
                id INTEGER PRIMARY KEY,
                branch_id INTEGER,
                name TEXT
            )
            """
        )
        bid = save_branch_master(self.conn, self._sample_form(), "creator")
        self.conn.commit()
        self.conn.execute("INSERT INTO projects(branch_id, name) VALUES(?, 'Site A')", (bid,))
        self.conn.commit()
        self.assertTrue(branch_has_transactions(self.conn, bid))
        with self.assertRaises(ValueError):
            soft_delete_branch_master(self.conn, bid, "deleter")


class BranchMasterReportTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)
        ensure_branch_master_schema(self.conn)
        self.company_id = _seed_company(self.conn)
        save_branch_master(
            self.conn,
            {
                "company_id": self.company_id,
                "branch_code": "BR-ACT-01",
                "branch_name": "Active Site",
                "country": "India",
                "status": "Active",
            },
            "creator",
        )
        save_branch_master(
            self.conn,
            {
                "company_id": self.company_id,
                "branch_code": "BR-INA-01",
                "branch_name": "Closed Site",
                "country": "India",
                "status": "Inactive",
            },
            "creator",
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_active_inactive_and_company_wise_reports(self):
        active = branch_report(self.conn, "active")
        self.assertEqual(len(active), 1)
        inactive = branch_report(self.conn, "inactive")
        self.assertEqual(len(inactive), 1)
        grouped = branch_report(self.conn, "company_wise")
        self.assertIsInstance(grouped, dict)
        self.assertEqual(grouped["company_count"], 1)
        self.assertEqual(grouped["branch_count"], 2)
        self.assertEqual(len(grouped["companies"][0]["branches"]), 2)


class BranchMasterImportTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)
        ensure_branch_master_schema(self.conn)
        self.company_id = _seed_company(self.conn)
        self.conn.commit()
        co = self.conn.execute("SELECT company_code FROM companies WHERE id=?", (self.company_id,)).fetchone()
        self.company_code = co[0]

    def tearDown(self):
        self.conn.close()

    def test_import_validate_and_save(self):
        rows = [
            {
                "_row_num": 2,
                "company_code": self.company_code,
                "branch_code": "BR-IMP-01",
                "branch_name": "Import Branch",
                "country": "India",
                "status": "Active",
                "email": "import-branch@example.com",
            }
        ]
        val = validate_branch_import(self.conn, rows)
        self.assertTrue(val["ok"], val.get("errors"))
        result = save_branch_import(self.conn, val["parsed_rows"], username="importer")
        self.assertEqual(result["imported"], 1)
        listing = list_branches_master(self.conn, search="Import Branch")
        self.assertEqual(listing["total"], 1)


class BranchMasterPermissionTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_user_tab_permissions_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_admin_bypass_and_granted_actions(self):
        self.assertTrue(user_can_branch_master(self.conn, 99, "view", is_admin=True))
        self.conn.execute(
            """
            INSERT INTO user_tab_permissions(
                user_id, department_slug, tab_key, endpoint, label, granted, action_flags, updated_at
            ) VALUES (?, '', '', 'branch_master', 'Branch Master', 1, ?, datetime('now'))
            """,
            (
                7,
                json.dumps(
                    {
                        "view": True,
                        "create": True,
                        "edit": False,
                        "delete": False,
                        "import": False,
                        "export": True,
                        "approve": False,
                    }
                ),
            ),
        )
        self.assertTrue(user_can_branch_master(self.conn, 7, "view", is_admin=False))
        self.assertTrue(user_can_branch_master(self.conn, 7, "create", is_admin=False))
        self.assertFalse(user_can_branch_master(self.conn, 7, "edit", is_admin=False))
        self.assertTrue(user_can_branch_master(self.conn, 7, "export", is_admin=False))
        self.assertFalse(user_can_branch_master(self.conn, 7, "approve", is_admin=False))


class BranchMasterAiValidationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)
        ensure_branch_master_schema(self.conn)
        self.company_id = _seed_company(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_ai_validate_detects_missing_and_duplicates(self):
        bid = save_branch_master(
            self.conn,
            {
                "company_id": self.company_id,
                "branch_code": "BR-AI-01",
                "branch_name": "AI Branch",
                "country": "India",
                "status": "Active",
            },
            "creator",
        )
        self.conn.commit()
        result = ai_validate_branch(
            self.conn,
            form={
                "company_id": self.company_id,
                "branch_code": "BR-AI-01",
                "branch_name": "",
                "country": "India",
            },
            branch_id=None,
        )
        self.assertIn("branch_name", result["missing"])
        dup = ai_validate_branch(
            self.conn,
            form={
                "company_id": self.company_id,
                "branch_code": "BR-AI-01",
                "branch_name": "Duplicate",
                "country": "India",
            },
        )
        self.assertTrue(dup["duplicates"])
        complete = ai_validate_branch(self.conn, branch_id=bid)
        self.assertTrue(complete.get("address_consistent") or complete.get("suggestions"))


if __name__ == "__main__":
    unittest.main()
