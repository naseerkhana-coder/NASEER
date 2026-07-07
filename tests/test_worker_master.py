"""Unit and integration tests for Worker Master (MODULE-015)."""

from __future__ import annotations

import sqlite3
import unittest

from worker_import_service import save_worker_import, validate_worker_import
from worker_master_service import (
    activate_worker_master,
    ai_validate_worker,
    approve_worker_master,
    deactivate_worker_master,
    ensure_demo_company_workers,
    ensure_worker_master_schema,
    export_workers_csv,
    generate_worker_master_code,
    get_face_template_reference,
    get_worker_master,
    list_workers_for_project,
    list_workers_master,
    register_face_template,
    save_worker_master,
    soft_delete_worker_master,
    user_can_worker_master,
    validate_worker_for_attendance,
    validate_worker_uniqueness,
    worker_has_transactions,
    worker_report,
)


def _sample_form(**overrides):
    form = {
        "worker_code": "WRK901",
        "worker_name": "Ramesh Kumar",
        "worker_type": "Company Worker",
        "trade": "Brick Work",
        "skill": "Skilled",
        "mobile": "9876543210",
        "status": "Active",
        "salary_type": "Daily",
        "salary_amount": "800",
        "joining_date": "2026-01-01",
    }
    form.update(overrides)
    return form


class WorkerMasterSchemaTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_worker_master_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_schema_has_module015_columns(self):
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(workers)").fetchall()}
        for col in (
            "worker_code",
            "trade",
            "skill",
            "company_id",
            "allow_multi_project",
            "attendance_mode",
            "face_template_ref",
            "approval_status",
            "is_deleted",
        ):
            self.assertIn(col, cols)

    def test_child_tables_exist(self):
        tables = {
            row[0]
            for row in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        self.assertIn("worker_project_assignments", tables)
        self.assertIn("worker_emergency_contacts", tables)
        self.assertIn("worker_face_templates", tables)


class WorkerMasterValidationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_worker_master_schema(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_unique_worker_code(self):
        save_worker_master(self.conn, _sample_form(), "creator")
        self.conn.commit()
        with self.assertRaises(ValueError):
            validate_worker_uniqueness(self.conn, worker_code="WRK901")

    def test_trade_required(self):
        with self.assertRaises(ValueError):
            save_worker_master(
                self.conn,
                {
                    "worker_code": "WRK902",
                    "worker_name": "No Trade",
                    "worker_type": "Company Worker",
                    "status": "Active",
                },
                "tester",
            )

    def test_subcontractor_required_for_sub_type(self):
        with self.assertRaises(ValueError):
            save_worker_master(
                self.conn,
                _sample_form(worker_type="Subcontractor Worker", worker_code="WRK903"),
                "tester",
            )


class WorkerMasterCrudTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_worker_master_schema(self.conn)
        self.conn.execute(
            "CREATE TABLE projects(id INTEGER PRIMARY KEY, project_code TEXT, project_name TEXT)"
        )
        self.conn.execute(
            "INSERT INTO projects(id, project_code, project_name) VALUES(1,'PRJ1','Site Alpha')"
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_save_list_get(self):
        wid = save_worker_master(
            self.conn,
            _sample_form(project_id="1", assignment_start_date="2026-01-01"),
            "creator",
        )
        self.conn.commit()
        row = get_worker_master(self.conn, wid)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["worker_code"], "WRK901")
        self.assertEqual(row["trade"], "Brick Work")
        self.assertEqual(row["worker_type"], "Company Worker")
        listing = list_workers_master(self.conn, search="Ramesh")
        self.assertEqual(listing["total"], 1)

    def test_project_assignment_history(self):
        wid = save_worker_master(
            self.conn,
            _sample_form(project_id="1", assignment_start_date="2026-01-01"),
            "creator",
        )
        self.conn.commit()
        row = get_worker_master(self.conn, wid)
        assert row is not None
        self.assertTrue(len(row.get("project_assignments") or []) >= 1)

    def test_soft_delete_without_refs(self):
        wid = save_worker_master(self.conn, _sample_form(), "creator")
        self.conn.commit()
        soft_delete_worker_master(self.conn, wid, "admin")
        self.conn.commit()
        row = get_worker_master(self.conn, wid)
        self.assertIsNone(row)

    def test_activate_deactivate(self):
        wid = save_worker_master(self.conn, _sample_form(), "creator")
        self.conn.commit()
        approve_worker_master(self.conn, wid, "approver")
        deactivate_worker_master(self.conn, wid, "admin")
        activate_worker_master(self.conn, wid, "admin")
        row = get_worker_master(self.conn, wid)
        assert row is not None
        self.assertEqual(row["status"], "Active")

    def test_generate_code(self):
        code = generate_worker_master_code(self.conn, "Company Worker")
        self.assertTrue(code.startswith("WRK"))


class WorkerMasterIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_worker_master_schema(self.conn)
        self.conn.execute(
            "CREATE TABLE projects(id INTEGER PRIMARY KEY, project_code TEXT, project_name TEXT)"
        )
        self.conn.execute(
            "INSERT INTO projects(id, project_code, project_name) VALUES(1,'PRJ1','Site Alpha')"
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_face_template_storage(self):
        wid = save_worker_master(self.conn, _sample_form(), "creator")
        self.conn.commit()
        result = register_face_template(
            self.conn,
            wid,
            "uploads/workers/face_test.bin",
            {"registered_by": "tester", "device_info": "Android V1"},
        )
        self.assertTrue(result["ok"])
        ref = get_face_template_reference(self.conn, wid)
        self.assertEqual(ref, "uploads/workers/face_test.bin")

    def test_validate_for_attendance(self):
        wid = save_worker_master(
            self.conn,
            _sample_form(project_id="1", assignment_start_date="2026-01-01"),
            "creator",
        )
        self.conn.commit()
        check = validate_worker_for_attendance(self.conn, wid)
        self.assertTrue(check["ok"])
        self.assertEqual(check["worker_code"], "WRK901")

    def test_list_workers_for_project(self):
        wid = save_worker_master(
            self.conn,
            _sample_form(project_id="1", assignment_start_date="2026-01-01"),
            "creator",
        )
        self.conn.commit()
        items = list_workers_for_project(self.conn, 1)
        self.assertEqual(len(items), 1)
        self.assertEqual(int(items[0]["id"]), wid)

    def test_ai_validate_duplicate_mobile(self):
        save_worker_master(self.conn, _sample_form(), "creator")
        self.conn.commit()
        result = ai_validate_worker(
            self.conn,
            form={"worker_name": "Another", "mobile": "9876543210", "trade": "Brick Work"},
        )
        self.assertFalse(result["ok"])

    def test_import(self):
        rows = [
            {
                "_row_num": 2,
                "worker_code": "WRK777",
                "worker_name": "Import Worker",
                "worker_type": "Company Worker",
                "trade": "Brick Work",
                "status": "Active",
            }
        ]
        val = validate_worker_import(self.conn, rows)
        self.assertTrue(val["ok"])
        result = save_worker_import(self.conn, val["parsed_rows"], username="importer")
        self.assertEqual(result["imported"], 1)

    def test_export_and_report(self):
        save_worker_master(self.conn, _sample_form(), "creator")
        self.conn.commit()
        csv_text = export_workers_csv(self.conn)
        self.assertIn("WRK901", csv_text)
        report = worker_report(self.conn, "register")
        self.assertEqual(len(report), 1)

    def test_worker_has_transactions_attendance(self):
        wid = save_worker_master(self.conn, _sample_form(), "creator")
        self.conn.commit()
        self.conn.execute(
            "CREATE TABLE attendance(id INTEGER PRIMARY KEY, worker_id INTEGER, worker_source TEXT)"
        )
        self.conn.execute(
            "INSERT INTO attendance(worker_id, worker_source) VALUES(?, 'worker')",
            (wid,),
        )
        blockers = worker_has_transactions(self.conn, wid)
        self.assertIn("attendance", blockers)

    def test_permissions_admin(self):
        self.assertTrue(user_can_worker_master(self.conn, None, "view", is_admin=True))


class DemoCompanyWorkersTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_worker_master_schema(self.conn)
        self.conn.execute(
            "CREATE TABLE projects(id INTEGER PRIMARY KEY, project_name TEXT, status TEXT)"
        )
        self.conn.execute(
            "INSERT INTO projects(id, project_name, status) VALUES(1, 'Demo Project', 'Active')"
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_ensure_demo_company_workers_creates_w001_w003(self):
        ensure_demo_company_workers(self.conn)
        self.conn.commit()
        rows = self.conn.execute(
            "SELECT worker_code, worker_name, worker_category FROM workers ORDER BY worker_code"
        ).fetchall()
        codes = [row["worker_code"] for row in rows]
        self.assertEqual(codes, ["W001", "W002", "W003"])
        self.assertEqual(rows[0]["worker_category"], "Company Staff")


if __name__ == "__main__":
    unittest.main()
