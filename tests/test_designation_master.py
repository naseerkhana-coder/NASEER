"""Unit and integration tests for Designation Master (MODULE-005)."""

from __future__ import annotations

import json
import sqlite3
import unittest

from company_master_service import ensure_company_master_schema, save_company
from department_master_service import ensure_department_master_schema, save_department_master
from designation_import_service import save_designation_import, validate_designation_import
from designation_master_service import (
    activate_designation_master,
    ai_validate_designation,
    approve_designation_master,
    deactivate_designation_master,
    designation_has_references,
    designation_report,
    ensure_designation_master_schema,
    export_designations_csv,
    get_designation_master,
    list_designations_master,
    save_designation_master,
    soft_delete_designation_master,
    user_can_designation_master,
    validate_designation_uniqueness,
)


def _seed_company(conn) -> int:
    return save_company(
        conn,
        {
            "legal_name": "Gamma Construction Private Limited",
            "company_name": "Gamma Construction",
            "country": "India",
            "status": "Active",
        },
        "tester",
    )


def _seed_department(conn, company_id: int) -> int:
    return save_department_master(
        conn,
        {
            "company_id": company_id,
            "department_code": "DEPT-ENG-01",
            "department_name": "Engineering",
            "status": "Active",
        },
        "tester",
    )


class DesignationMasterSchemaTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_designation_master_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_schema_has_module005_columns(self):
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(designations)").fetchall()}
        for col in (
            "designation_code",
            "designation_name",
            "designation_short_name",
            "company_id",
            "department_id",
            "grade_level",
            "workflow_role_default",
            "description",
            "status",
            "approval_status",
            "created_by",
            "modified_by",
            "is_deleted",
        ):
            self.assertIn(col, cols)


class DesignationMasterValidationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)
        ensure_department_master_schema(self.conn)
        ensure_designation_master_schema(self.conn)
        self.company_id = _seed_company(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_unique_code_per_company_and_global_name(self):
        form = {
            "company_id": self.company_id,
            "designation_code": "DG-PM-01",
            "designation_name": "Project Manager",
            "status": "Active",
        }
        save_designation_master(self.conn, form, "creator")
        self.conn.commit()
        with self.assertRaises(ValueError):
            validate_designation_uniqueness(
                self.conn,
                company_id=self.company_id,
                designation_code="DG-PM-01",
                designation_name="Other Title",
            )
        with self.assertRaises(ValueError):
            validate_designation_uniqueness(
                self.conn,
                company_id=self.company_id,
                designation_code="DG-PM-02",
                designation_name="Project Manager",
            )


class DesignationMasterCrudTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)
        ensure_department_master_schema(self.conn)
        ensure_designation_master_schema(self.conn)
        self.company_id = _seed_company(self.conn)
        self.department_id = _seed_department(self.conn, self.company_id)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def _sample_form(self, **overrides):
        data = {
            "company_id": self.company_id,
            "department_id": self.department_id,
            "designation_code": "DG-SE-01",
            "designation_name": "Site Engineer",
            "designation_short_name": "SE",
            "grade_level": "L3",
            "workflow_role_default": "Maker",
            "description": "Site engineering role",
            "status": "Active",
        }
        data.update(overrides)
        return data

    def test_create_update_workflow_and_pagination(self):
        did = save_designation_master(self.conn, self._sample_form(), "creator")
        self.conn.commit()
        row = get_designation_master(self.conn, did)
        self.assertIsNotNone(row)
        self.assertEqual(row["designation_name"], "Site Engineer")
        self.assertEqual(row["approval_status"], "Draft")

        save_designation_master(
            self.conn,
            self._sample_form(grade_level="L4"),
            "editor",
            did,
        )
        self.conn.commit()
        updated = get_designation_master(self.conn, did)
        self.assertEqual(updated["grade_level"], "L4")

        approve_designation_master(self.conn, did, "approver")
        self.conn.commit()

        deactivate_designation_master(self.conn, did, "admin")
        self.conn.commit()
        inactive = get_designation_master(self.conn, did)
        self.assertEqual(inactive["status"], "Inactive")

        activate_designation_master(self.conn, did, "admin")
        self.conn.commit()

        listing = list_designations_master(self.conn, search="Site Engineer", per_page=10)
        self.assertEqual(listing["total"], 1)

        soft_delete_designation_master(self.conn, did, "deleter")
        self.conn.commit()
        self.assertIsNone(get_designation_master(self.conn, did))

    def test_export_csv(self):
        save_designation_master(self.conn, self._sample_form(), "creator")
        self.conn.commit()
        csv_text = export_designations_csv(self.conn)
        self.assertIn("designation_code", csv_text)
        self.assertIn("Site Engineer", csv_text)

    def test_reference_guard_blocks_delete(self):
        self.conn.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                designation_id INTEGER
            )
            """
        )
        did = save_designation_master(self.conn, self._sample_form(), "creator")
        self.conn.commit()
        self.conn.execute("INSERT INTO users(designation_id) VALUES(?)", (did,))
        self.conn.commit()
        self.assertTrue(designation_has_references(self.conn, did))
        with self.assertRaises(ValueError):
            soft_delete_designation_master(self.conn, did, "deleter")


class DesignationMasterReportTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)
        ensure_department_master_schema(self.conn)
        ensure_designation_master_schema(self.conn)
        self.company_id = _seed_company(self.conn)
        save_designation_master(
            self.conn,
            {
                "company_id": self.company_id,
                "designation_code": "DG-A-01",
                "designation_name": "Active Role",
                "status": "Active",
            },
            "creator",
        )
        save_designation_master(
            self.conn,
            {
                "company_id": self.company_id,
                "designation_code": "DG-I-01",
                "designation_name": "Inactive Role",
                "status": "Inactive",
            },
            "creator",
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_active_inactive_reports(self):
        active = designation_report(self.conn, "active")
        self.assertEqual(len(active), 1)
        inactive = designation_report(self.conn, "inactive")
        self.assertEqual(len(inactive), 1)


class DesignationMasterImportTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)
        ensure_department_master_schema(self.conn)
        ensure_designation_master_schema(self.conn)
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
                "designation_code": "DG-IMP-01",
                "designation_name": "Import Designation",
                "workflow_role": "Checker",
                "status": "Active",
            }
        ]
        val = validate_designation_import(self.conn, rows)
        self.assertTrue(val["ok"], val.get("errors"))
        result = save_designation_import(self.conn, val["parsed_rows"], username="importer")
        self.assertEqual(result["imported"], 1)


class DesignationMasterPermissionTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        from user_permission_service import ensure_user_tab_permissions_schema

        ensure_user_tab_permissions_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_admin_and_granted_actions(self):
        self.assertTrue(user_can_designation_master(self.conn, 1, "view", is_admin=True))
        self.conn.execute(
            """
            INSERT INTO user_tab_permissions(
                user_id, department_slug, tab_key, endpoint, label, granted, action_flags, updated_at
            ) VALUES (?, '', '', 'designation_master', 'Designation Master', 1, ?, datetime('now'))
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
        self.assertTrue(user_can_designation_master(self.conn, 5, "view", is_admin=False))
        self.assertTrue(user_can_designation_master(self.conn, 5, "import", is_admin=False))
        self.assertFalse(user_can_designation_master(self.conn, 5, "approve", is_admin=False))


class DesignationMasterAiTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)
        ensure_designation_master_schema(self.conn)
        self.company_id = _seed_company(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_ai_validate_missing_fields(self):
        result = ai_validate_designation(
            self.conn,
            form={"company_id": self.company_id, "designation_code": "", "designation_name": ""},
        )
        self.assertIn("designation_name", result["missing"])


if __name__ == "__main__":
    unittest.main()
