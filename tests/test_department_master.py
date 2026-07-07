"""Unit and integration tests for Department Master (MODULE-003)."""

from __future__ import annotations

import json
import sqlite3
import unittest

from company_master_service import ensure_company_master_schema, save_company
from department_import_service import save_department_import, validate_department_import
from department_master_service import (
    activate_department_master,
    ai_validate_department,
    approve_department_master,
    deactivate_department_master,
    department_has_employees,
    department_report,
    ensure_department_master_schema,
    export_departments_csv,
    get_department_master,
    list_departments_master,
    save_department_master,
    soft_delete_department_master,
    user_can_department_master,
    validate_department_uniqueness,
)


def _seed_company(conn) -> int:
    return save_company(
        conn,
        {
            "legal_name": "Delta Construction Private Limited",
            "company_name": "Delta Construction",
            "country": "India",
            "status": "Active",
        },
        "tester",
    )


class DepartmentMasterSchemaTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_department_master_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_schema_has_module003_columns(self):
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(departments)").fetchall()}
        for col in (
            "department_code",
            "department_name",
            "department_short_name",
            "company_id",
            "branch_id",
            "department_head",
            "description",
            "status",
            "created_by",
            "modified_by",
            "created_at",
            "modified_at",
            "approval_status",
            "is_deleted",
        ):
            self.assertIn(col, cols)


class DepartmentMasterValidationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)
        ensure_department_master_schema(self.conn)
        self.company_id = _seed_company(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_unique_code_and_name_per_company(self):
        form = {
            "company_id": self.company_id,
            "department_code": "DEPT-HR-01",
            "department_name": "Human Resources",
            "status": "Active",
        }
        save_department_master(self.conn, form, "creator")
        self.conn.commit()
        with self.assertRaises(ValueError):
            validate_department_uniqueness(
                self.conn,
                company_id=self.company_id,
                department_code="DEPT-HR-01",
                department_name="Other Name",
            )
        with self.assertRaises(ValueError):
            validate_department_uniqueness(
                self.conn,
                company_id=self.company_id,
                department_code="DEPT-HR-02",
                department_name="Human Resources",
            )


class DepartmentMasterCrudTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)
        ensure_department_master_schema(self.conn)
        self.company_id = _seed_company(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def _sample_form(self, **overrides):
        data = {
            "company_id": self.company_id,
            "department_code": "DEPT-ACC-01",
            "department_name": "Accounts",
            "department_short_name": "ACC",
            "department_head": "Finance Manager",
            "description": "Accounts and finance",
            "status": "Active",
        }
        data.update(overrides)
        return data

    def test_create_update_workflow_and_pagination(self):
        did = save_department_master(self.conn, self._sample_form(), "creator")
        self.conn.commit()
        row = get_department_master(self.conn, did)
        self.assertIsNotNone(row)
        self.assertEqual(row["department_name"], "Accounts")
        self.assertEqual(row["approval_status"], "Draft")

        save_department_master(
            self.conn,
            self._sample_form(department_head="Chief Accountant"),
            "editor",
            did,
        )
        self.conn.commit()
        updated = get_department_master(self.conn, did)
        self.assertEqual(updated["department_head"], "Chief Accountant")

        approve_department_master(self.conn, did, "approver")
        self.conn.commit()

        deactivate_department_master(self.conn, did, "admin")
        self.conn.commit()
        inactive = get_department_master(self.conn, did)
        self.assertEqual(inactive["status"], "Inactive")

        activate_department_master(self.conn, did, "admin")
        self.conn.commit()

        listing = list_departments_master(self.conn, search="Accounts", per_page=10)
        self.assertEqual(listing["total"], 1)

        soft_delete_department_master(self.conn, did, "deleter")
        self.conn.commit()
        self.assertIsNone(get_department_master(self.conn, did))

    def test_export_csv(self):
        save_department_master(self.conn, self._sample_form(), "creator")
        self.conn.commit()
        csv_text = export_departments_csv(self.conn)
        self.assertIn("department_code", csv_text)
        self.assertIn("Accounts", csv_text)

    def test_employee_guard_blocks_delete(self):
        self.conn.execute(
            """
            CREATE TABLE staff (
                id INTEGER PRIMARY KEY,
                department TEXT,
                staff_name TEXT
            )
            """
        )
        did = save_department_master(self.conn, self._sample_form(), "creator")
        self.conn.commit()
        self.conn.execute(
            "INSERT INTO staff(department, staff_name) VALUES(?, 'Employee One')",
            ("Accounts",),
        )
        self.conn.commit()
        self.assertTrue(department_has_employees(self.conn, did))
        with self.assertRaises(ValueError):
            soft_delete_department_master(self.conn, did, "deleter")


class DepartmentMasterReportTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)
        ensure_department_master_schema(self.conn)
        self.company_id = _seed_company(self.conn)
        save_department_master(
            self.conn,
            {
                "company_id": self.company_id,
                "department_code": "DEPT-A-01",
                "department_name": "Active Dept",
                "status": "Active",
            },
            "creator",
        )
        save_department_master(
            self.conn,
            {
                "company_id": self.company_id,
                "department_code": "DEPT-I-01",
                "department_name": "Inactive Dept",
                "status": "Inactive",
            },
            "creator",
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_active_inactive_reports(self):
        active = department_report(self.conn, "active")
        self.assertEqual(len(active), 1)
        inactive = department_report(self.conn, "inactive")
        self.assertEqual(len(inactive), 1)


class DepartmentMasterImportTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)
        ensure_department_master_schema(self.conn)
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
                "department_code": "DEPT-IMP-01",
                "department_name": "Import Department",
                "status": "Active",
            }
        ]
        val = validate_department_import(self.conn, rows)
        self.assertTrue(val["ok"], val.get("errors"))
        result = save_department_import(self.conn, val["parsed_rows"], username="importer")
        self.assertEqual(result["imported"], 1)


class DepartmentMasterPermissionTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        from user_permission_service import ensure_user_tab_permissions_schema

        ensure_user_tab_permissions_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_admin_and_granted_actions(self):
        self.assertTrue(user_can_department_master(self.conn, 1, "view", is_admin=True))
        self.conn.execute(
            """
            INSERT INTO user_tab_permissions(
                user_id, department_slug, tab_key, endpoint, label, granted, action_flags, updated_at
            ) VALUES (?, '', '', 'department_master', 'Department Master', 1, ?, datetime('now'))
            """,
            (
                5,
                json.dumps(
                    {
                        "view": True,
                        "create": True,
                        "edit": True,
                        "delete": False,
                        "import": True,
                        "export": True,
                        "approve": False,
                    }
                ),
            ),
        )
        self.assertTrue(user_can_department_master(self.conn, 5, "view", is_admin=False))
        self.assertTrue(user_can_department_master(self.conn, 5, "import", is_admin=False))
        self.assertFalse(user_can_department_master(self.conn, 5, "approve", is_admin=False))


class DepartmentMasterAiTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)
        ensure_department_master_schema(self.conn)
        self.company_id = _seed_company(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_ai_validate_missing_fields(self):
        result = ai_validate_department(
            self.conn,
            form={"company_id": self.company_id, "department_code": "", "department_name": ""},
        )
        self.assertIn("department_code", result["missing"])
        self.assertIn("department_name", result["missing"])


if __name__ == "__main__":
    unittest.main()
