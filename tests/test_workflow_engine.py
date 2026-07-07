"""Unit and integration tests for Workflow Engine (MODULE-007)."""

from __future__ import annotations

import sqlite3
import unittest

from designation_master_service import ensure_designation_master_schema
from workflow_engine_import_service import save_workflow_import, validate_workflow_import
from workflow_engine_service import (
    MODULE_007_SEEDS,
    activate_workflow_engine,
    deactivate_workflow_engine,
    ensure_workflow_engine_schema,
    get_workflow_engine,
    list_workflows_engine,
    save_workflow_engine,
    seed_workflow_engine,
    soft_delete_workflow_engine,
    sync_engine_to_workflow_master,
    validate_workflow_stages,
    workflow_has_usage,
    workflow_engine_report,
    ai_workflow_insights,
)
from workflow_service import (
    DEFAULT_WORKFLOW_MODE,
    create_approval_request,
    seed_designations,
    seed_workflow_master,
)


def _ensure_base_schema(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS workflow_master(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_name TEXT NOT NULL,
            module_id TEXT UNIQUE NOT NULL,
            workflow_role_mapping TEXT,
            maker_designation_id INTEGER,
            checker_designation_id INTEGER,
            approver_designation_id INTEGER,
            workflow_mode TEXT,
            status TEXT DEFAULT 'Active'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            designation_id INTEGER,
            status TEXT DEFAULT 'Active',
            role TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS approval_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id TEXT,
            record_id INTEGER,
            record_table TEXT,
            current_stage TEXT,
            workflow_status TEXT,
            maker_user_id INTEGER,
            checker_user_id INTEGER,
            approver_user_id INTEGER,
            maker_action_at TEXT,
            checker_action_at TEXT,
            approver_action_at TEXT,
            rejection_reason TEXT,
            checker_comment TEXT,
            approver_comment TEXT,
            created_by TEXT,
            created_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS approval_audit(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            approval_request_id INTEGER,
            module_id TEXT,
            record_id INTEGER,
            record_table TEXT,
            action TEXT,
            actor_user_id INTEGER,
            actor_username TEXT,
            remarks TEXT,
            created_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            notification_type TEXT,
            module_id TEXT,
            record_id INTEGER,
            record_table TEXT,
            is_read INTEGER DEFAULT 0,
            created_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS petty_cash(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            approval_status TEXT
        )
        """
    )
    ensure_designation_master_schema(conn)


def _designation_ids(conn):
    seed_designations(conn)
    rows = conn.execute("SELECT id, designation_name FROM designations").fetchall()
    return {r["designation_name"]: r["id"] for r in rows}


class WorkflowEngineSchemaTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _ensure_base_schema(self.conn)
        ensure_workflow_engine_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_schema_tables_exist(self):
        tables = {
            r[0]
            for r in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        for name in ("workflows", "workflow_stages", "workflow_rules", "workflow_assignments"):
            self.assertIn(name, tables)


class WorkflowEngineValidationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _ensure_base_schema(self.conn)
        ensure_workflow_engine_schema(self.conn)
        self.desigs = _designation_ids(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_max_three_stages(self):
        stages = [
            {"stage_type": "Maker", "designation_id": self.desigs["Site Engineer"]},
            {"stage_type": "Checker", "designation_id": self.desigs["Accounts Manager"]},
            {"stage_type": "Approver", "designation_id": self.desigs["Managing Director"]},
            {"stage_type": "Checker", "designation_id": self.desigs["Store Manager"]},
        ]
        with self.assertRaises(ValueError):
            validate_workflow_stages(stages, DEFAULT_WORKFLOW_MODE)

    def test_checker_cannot_equal_maker(self):
        maker = self.desigs["Site Engineer"]
        stages = [
            {"stage_type": "Maker", "designation_id": maker},
            {"stage_type": "Checker", "designation_id": maker},
            {"stage_type": "Approver", "designation_id": self.desigs["Managing Director"]},
        ]
        with self.assertRaises(ValueError):
            validate_workflow_stages(stages, DEFAULT_WORKFLOW_MODE)

    def test_save_and_sync_workflow_master(self):
        form = {
            "workflow_code": "WF-TEST",
            "workflow_name": "Test Workflow",
            "module_id": "test_module",
            "module_name": "Test Module",
            "workflow_mode": DEFAULT_WORKFLOW_MODE,
            "status": "Active",
            "maker_designation_id": str(self.desigs["Site Engineer"]),
            "checker_designation_id": str(self.desigs["Accounts Manager"]),
            "approver_designation_id": str(self.desigs["Managing Director"]),
        }
        wf_id = save_workflow_engine(self.conn, form, "tester")
        sync_engine_to_workflow_master(self.conn, wf_id)
        row = self.conn.execute(
            "SELECT * FROM workflow_master WHERE module_id='test_module'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["maker_designation_id"], self.desigs["Site Engineer"])


class WorkflowEngineSeedTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _ensure_base_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_seed_creates_module007_workflows(self):
        seed_workflow_master(self.conn)
        seed_workflow_engine(self.conn)
        count = self.conn.execute(
            "SELECT COUNT(*) FROM workflows WHERE COALESCE(is_deleted,0)=0"
        ).fetchone()[0]
        self.assertGreaterEqual(count, len(MODULE_007_SEEDS))
        for seed in MODULE_007_SEEDS:
            row = self.conn.execute(
                "SELECT id FROM workflows WHERE module_id=?", (seed["module_id"],)
            ).fetchone()
            self.assertIsNotNone(row, msg=f"Missing seed {seed['module_id']}")


class WorkflowEngineUsageTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _ensure_base_schema(self.conn)
        ensure_workflow_engine_schema(self.conn)
        self.desigs = _designation_ids(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_cannot_delete_used_workflow(self):
        form = {
            "workflow_code": "WF-PC",
            "workflow_name": "Petty Cash",
            "module_id": "petty_cash",
            "module_name": "Petty Cash",
            "workflow_mode": DEFAULT_WORKFLOW_MODE,
            "maker_designation_id": str(self.desigs["Site Engineer"]),
            "checker_designation_id": str(self.desigs["Accounts Manager"]),
            "approver_designation_id": str(self.desigs["Managing Director"]),
        }
        wf_id = save_workflow_engine(self.conn, form, "tester")
        self.conn.execute("INSERT INTO petty_cash(approval_status) VALUES('Pending Checker')")
        rid = self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        create_approval_request(self.conn, "petty_cash", rid, "petty_cash", "maker1", 1)
        self.assertTrue(workflow_has_usage(self.conn, wf_id))
        with self.assertRaises(ValueError):
            soft_delete_workflow_engine(self.conn, wf_id, "tester")

    def test_activate_deactivate(self):
        form = {
            "workflow_code": "WF-X",
            "workflow_name": "X",
            "module_id": "x_module",
            "module_name": "X",
            "workflow_mode": "maker_only",
            "maker_designation_id": str(self.desigs["Site Engineer"]),
        }
        wf_id = save_workflow_engine(self.conn, form, "tester")
        deactivate_workflow_engine(self.conn, wf_id, "tester")
        wf = get_workflow_engine(self.conn, wf_id)
        self.assertEqual(wf["status"], "Inactive")
        activate_workflow_engine(self.conn, wf_id, "tester")
        wf = get_workflow_engine(self.conn, wf_id)
        self.assertEqual(wf["status"], "Active")


class WorkflowEngineImportTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _ensure_base_schema(self.conn)
        ensure_workflow_engine_schema(self.conn)
        _designation_ids(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_import_validation(self):
        rows = [
            {
                "workflow_code": "WF-IMP",
                "workflow_name": "Import Test",
                "module_id": "import_test",
                "module_name": "Import Test",
                "workflow_mode": "full",
                "maker_designation": "Site Engineer",
                "checker_designation": "Accounts Manager",
                "approver_designation": "Managing Director",
            }
        ]
        val = validate_workflow_import(self.conn, rows)
        self.assertTrue(val["ok"])
        result = save_workflow_import(self.conn, val["parsed_rows"], "tester")
        self.assertEqual(result["imported"], 1)
        listing = list_workflows_engine(self.conn, search="Import Test")
        self.assertEqual(listing["total"], 1)


class WorkflowEngineReportTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _ensure_base_schema(self.conn)
        ensure_workflow_engine_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_ai_insights_fallback(self):
        insights = ai_workflow_insights(self.conn)
        self.assertEqual(insights["source"], "rules_engine")
        self.assertIn("summary", insights)

    def test_status_summary_report(self):
        self.conn.execute(
            "INSERT INTO approval_requests(module_id, record_id, record_table, workflow_status, created_at) "
            "VALUES('petty_cash', 1, 'petty_cash', 'pending_checker', '2026-01-01')"
        )
        rows = workflow_engine_report(self.conn, "status_summary")
        self.assertTrue(any(r["workflow_status"] == "pending_checker" for r in rows))


if __name__ == "__main__":
    unittest.main()
