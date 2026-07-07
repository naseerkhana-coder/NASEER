"""Unit and integration tests for Project Master (MODULE-016)."""

from __future__ import annotations

import sqlite3
import unittest

from branch_master_service import ensure_branch_master_schema, save_branch_master
from client_master_service import ensure_client_master_schema, save_client_master
from company_master_service import ensure_company_master_schema, save_company
from department_master_service import ensure_department_master_schema, save_department_master
from designation_master_service import ensure_designation_master_schema, save_designation_master
from employee_master_service import ensure_employee_master_schema
from project_import_service import save_project_import, validate_project_import
from project_master_service import (
    PROJECT_LIFECYCLE_STATUSES,
    activate_project_master,
    approve_project_master,
    deactivate_project_master,
    ensure_project_master_schema,
    export_projects_csv,
    generate_project_code,
    get_project_dashboard_summary,
    get_project_master,
    list_projects_for_module,
    list_projects_master,
    project_has_transactions,
    project_health_check,
    project_report,
    risk_flags,
    save_project_master,
    soft_delete_project_master,
    user_can_project_master,
    validate_project_uniqueness,
)


def _sample_form(**overrides):
    form = {
        "project_code": "PR901",
        "project_name": "Test Highway Package",
        "short_name": "Highway Pkg",
        "project_type": "Road",
        "client_id": "1",
        "company_id": "1",
        "branch_id": "1",
        "project_manager_id": "1",
        "project_engineer_id": "1",
        "project_value": "1000000",
        "revised_project_value": "1100000",
        "currency": "INR",
        "start_date": "2026-04-01",
        "planned_completion_date": "2027-03-31",
        "project_status": "Execution",
        "priority": "High",
        "city": "Chennai",
        "state": "Tamil Nadu",
        "latitude": "13.0827",
        "longitude": "80.2707",
        "status": "Active",
    }
    form.update(overrides)
    return form


def _seed_masters(conn):
    ensure_company_master_schema(conn)
    ensure_branch_master_schema(conn)
    ensure_client_master_schema(conn)
    ensure_employee_master_schema(conn)
    ensure_department_master_schema(conn)
    ensure_designation_master_schema(conn)
    ensure_project_master_schema(conn)
    company_id = save_company(
        conn,
        {
            "company_code": "CMP901",
            "company_name": "Test Construction Co",
            "legal_name": "Test Construction Co",
            "country": "India",
            "status": "Active",
        },
        "tester",
    )
    branch_id = save_branch_master(
        conn,
        {
            "branch_code": "BR901",
            "branch_name": "HQ Branch",
            "company_id": str(company_id),
            "country": "India",
            "status": "Active",
        },
        "tester",
    )
    client_id = save_client_master(
        conn,
        {
            "client_code": "CLT901",
            "client_name": "Test Client Ltd",
            "legal_name": "Test Client Ltd",
            "company_name": "Test Client",
            "status": "Active",
        },
        "tester",
    )
    dept_id = save_department_master(
        conn,
        {
            "department_code": "DEPT901",
            "department_name": "Projects",
            "company_id": str(company_id),
            "status": "Active",
        },
        "tester",
    )
    desig_id = save_designation_master(
        conn,
        {
            "designation_code": "DSG901",
            "designation_name": "Project Manager",
            "company_id": str(company_id),
            "status": "Active",
        },
        "tester",
    )
    from employee_master_service import save_employee_master

    staff_id = save_employee_master(
        conn,
        {
            "employee_code": "EMP901",
            "first_name": "Raj",
            "last_name": "Kumar",
            "staff_name": "Raj Kumar",
            "company_id": str(company_id),
            "branch_id": str(branch_id),
            "department_id": str(dept_id),
            "designation_id": str(desig_id),
            "mobile": "9876543210",
            "joining_date": "2026-01-01",
            "status": "Active",
        },
        "tester",
    )
    conn.commit()
    return company_id, branch_id, client_id, staff_id


class ProjectMasterSchemaTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_project_master_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_schema_has_module016_columns(self):
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(projects)").fetchall()}
        for col in (
            "project_code",
            "short_name",
            "company_id",
            "branch_id",
            "project_manager_id",
            "project_engineer_id",
            "project_value",
            "project_status",
            "latitude",
            "longitude",
            "is_deleted",
        ):
            self.assertIn(col, cols)

    def test_project_team_table_exists(self):
        tables = {
            row[0]
            for row in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        self.assertIn("project_team", tables)


class ProjectMasterCrudTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.company_id, self.branch_id, self.client_id, self.staff_id = _seed_masters(self.conn)

    def _form(self, **overrides):
        base = _sample_form(
            client_id=str(self.client_id),
            company_id=str(self.company_id),
            branch_id=str(self.branch_id),
            project_manager_id=str(self.staff_id),
            project_engineer_id=str(self.staff_id),
        )
        base.update(overrides)
        return base

    def tearDown(self):
        self.conn.close()

    def test_create_and_get_project(self):
        pid = save_project_master(self.conn, self._form(), "creator")
        self.conn.commit()
        project = get_project_master(self.conn, pid)
        self.assertIsNotNone(project)
        self.assertEqual(project["project_code"], "PR901")
        self.assertEqual(project["client_id"], self.client_id)
        self.assertEqual(project["project_manager_id"], self.staff_id)
        self.assertEqual(project["dashboard"]["project_id"], pid)

    def test_unique_project_code(self):
        save_project_master(self.conn, self._form(), "creator")
        self.conn.commit()
        with self.assertRaises(ValueError):
            validate_project_uniqueness(self.conn, project_code="PR901")

    def test_generate_project_code(self):
        code = generate_project_code(self.conn, "Metro Bridge")
        self.assertTrue(code.startswith("MB") or code.startswith("ME"))

    def test_soft_delete_blocked_with_worker_reference(self):
        pid = save_project_master(self.conn, self._form(), "creator")
        self.conn.execute(
            "CREATE TABLE workers(id INTEGER PRIMARY KEY, project_id INTEGER)"
        )
        self.conn.execute("INSERT INTO workers(project_id) VALUES(?)", (pid,))
        self.conn.commit()
        self.assertTrue(project_has_transactions(self.conn, pid))
        with self.assertRaises(ValueError):
            soft_delete_project_master(self.conn, pid, "deleter")

    def test_list_projects_for_module(self):
        save_project_master(self.conn, self._form(), "creator")
        self.conn.commit()
        items = list_projects_for_module(self.conn, {"status": "Active"})
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["project_code"], "PR901")

    def test_activate_deactivate(self):
        pid = save_project_master(self.conn, self._form(), "creator")
        self.conn.commit()
        deactivate_project_master(self.conn, pid, "admin")
        project = get_project_master(self.conn, pid)
        self.assertEqual(project["status"], "Inactive")
        activate_project_master(self.conn, pid, "admin")
        project = get_project_master(self.conn, pid)
        self.assertEqual(project["status"], "Active")

    def test_approve_project(self):
        pid = save_project_master(self.conn, self._form(), "creator")
        self.conn.commit()
        approve_project_master(self.conn, pid, "approver")
        project = get_project_master(self.conn, pid)
        self.assertEqual(project["approval_status"], "Approved")

    def test_export_csv(self):
        save_project_master(self.conn, self._form(), "creator")
        self.conn.commit()
        csv_text = export_projects_csv(self.conn)
        self.assertIn("PR901", csv_text)
        self.assertIn("Test Highway Package", csv_text)

    def test_reports(self):
        save_project_master(self.conn, self._form(), "creator")
        self.conn.commit()
        summary = project_report(self.conn, "summary")
        self.assertEqual(len(summary), 1)
        status_rows = project_report(self.conn, "status")
        self.assertTrue(any(r.get("project_status") == "Execution" for r in status_rows))

    def test_ai_stubs(self):
        pid = save_project_master(self.conn, self._form(), "creator")
        self.conn.commit()
        health = project_health_check(self.conn, pid)
        self.assertIn("ok", health)
        flags = risk_flags(self.conn, pid)
        self.assertIsInstance(flags, list)
        dash = get_project_dashboard_summary(self.conn, pid)
        self.assertFalse(dash.get("has_transactions"))


class ProjectMasterImportTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.company_id, self.branch_id, self.client_id, self.staff_id = _seed_masters(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_import_validate_and_save(self):
        rows = [
            {
                "_row_num": 2,
                "project_code": "PR902",
                "project_name": "Imported Project",
                "client_code": "CLT901",
                "company_code": "CMP901",
                "branch_code": "BR901",
                "project_manager_code": "EMP901",
                "project_value": "2000000",
                "project_status": "Planning",
                "status": "Active",
            }
        ]
        val = validate_project_import(self.conn, rows)
        self.assertTrue(val.get("ok"))
        result = save_project_import(self.conn, val["parsed_rows"], username="importer")
        self.conn.commit()
        self.assertEqual(result.get("imported"), 1)
        listing = list_projects_master(self.conn, search="Imported")
        self.assertEqual(listing["total"], 1)


class ProjectMasterPermissionTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_project_master_schema(self.conn)
        self.conn.execute(
            """
            CREATE TABLE user_tab_permissions(
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                endpoint TEXT,
                granted INTEGER,
                action_flags TEXT
            )
            """
        )

    def tearDown(self):
        self.conn.close()

    def test_user_can_denied_without_permission(self):
        self.assertFalse(user_can_project_master(self.conn, 1, "view", is_admin=False))

    def test_admin_always_allowed(self):
        self.assertTrue(user_can_project_master(self.conn, None, "view", is_admin=True))


if __name__ == "__main__":
    unittest.main()
