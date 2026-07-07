"""Unit tests for Enterprise Dashboard (MODULE-008)."""

from __future__ import annotations

import json
import sqlite3
import unittest

from dashboard_widget_registry import DashboardWidgetRegistry, WidgetSpec
from enterprise_dashboard_service import (
    ensure_enterprise_dashboard_schema,
    get_dashboard_layout,
    get_widget_data,
    list_available_widgets,
    register_v1_widgets,
    reset_dashboard_layout,
    save_dashboard_layout,
    save_widget_preferences,
    user_can_enterprise_dashboard,
    build_user_scope,
)


def _memory_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def _base_schema(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            role TEXT,
            designation_id INTEGER,
            department_id INTEGER
        )
        """
    )
    conn.execute("INSERT INTO users(id, username, role) VALUES(1, 'tester', 'Administrator')")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_tab_permissions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            department_slug TEXT,
            tab_key TEXT,
            endpoint TEXT,
            granted INTEGER,
            action_flags TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO user_tab_permissions(user_id, department_slug, tab_key, endpoint, granted, action_flags)
        VALUES(1, 'administration', 'enterprise_dashboard', 'enterprise_dashboard', 1, ?)
        """,
        (json.dumps({"view": True, "edit": True, "create": False, "delete": False, "export": False, "import": False, "approve": False, "reject": False}),),
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS projects(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT,
            status TEXT
        )
        """
    )
    conn.execute("INSERT INTO projects(project_name, status) VALUES('Site A', 'Active')")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS approval_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id TEXT,
            record_table TEXT,
            record_id INTEGER,
            workflow_status TEXT,
            created_at TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO approval_requests(module_id, record_table, record_id, workflow_status, created_at)
        VALUES('purchase_request', 'purchase_requests', 1, 'Pending Checker', '2026-07-06 10:00:00')
        """
    )


class EnterpriseDashboardRegistryTests(unittest.TestCase):
    def setUp(self):
        DashboardWidgetRegistry.clear()
        register_v1_widgets()

    def tearDown(self):
        DashboardWidgetRegistry.clear()
        register_v1_widgets()

    def test_v1_widget_registration(self):
        keys = DashboardWidgetRegistry.all_keys()
        self.assertIn("approval_summary", keys)
        self.assertIn("quick_actions", keys)
        self.assertGreaterEqual(len(keys), 20)

    def test_duplicate_registration_raises(self):
        with self.assertRaises(ValueError):
            DashboardWidgetRegistry.register(
                WidgetSpec("approval_summary", "Dup", "test"),
                lambda db, scope: {},
            )


class EnterpriseDashboardServiceTests(unittest.TestCase):
    def setUp(self):
        self.db = _memory_db()
        _base_schema(self.db)
        ensure_enterprise_dashboard_schema(self.db)
        self.db.commit()
        self.scope = build_user_scope(self.db, 1, {"role": "Administrator", "user_id": 1})

    def test_permissions_admin_bypass(self):
        self.assertTrue(user_can_enterprise_dashboard(self.db, 1, "view", is_admin=True))
        self.assertTrue(user_can_enterprise_dashboard(self.db, 1, "configure", is_admin=True))

    def test_permissions_tab_endpoint(self):
        self.assertTrue(user_can_enterprise_dashboard(self.db, 1, "view", is_admin=False))
        self.assertTrue(user_can_enterprise_dashboard(self.db, 1, "configure", is_admin=False))

    def test_list_available_widgets(self):
        widgets = list_available_widgets(self.db, self.scope)
        self.assertTrue(any(w["key"] == "active_projects" for w in widgets))

    def test_widget_data_active_projects(self):
        data = get_widget_data(self.db, "active_projects", self.scope)
        self.assertFalse(data.get("empty"))
        self.assertEqual(data.get("count"), 1)

    def test_widget_data_missing_table_empty_state(self):
        data = get_widget_data(self.db, "fleet_status", self.scope)
        self.assertTrue(data.get("empty"))

    def test_layout_save_and_load(self):
        layout = {
            "version": 1,
            "columns": 12,
            "widgets": [{"key": "approval_summary", "x": 0, "y": 0, "w": 3, "h": 2}],
        }
        save_dashboard_layout(self.db, 1, layout, "tester")
        self.db.commit()
        loaded = get_dashboard_layout(self.db, 1, self.scope)
        self.assertEqual(loaded["source"], "user")
        self.assertEqual(loaded["layout"]["widgets"][0]["key"], "approval_summary")

    def test_layout_reset(self):
        layout = {"version": 1, "columns": 12, "widgets": [{"key": "notifications", "x": 0, "y": 0, "w": 4, "h": 2}]}
        save_dashboard_layout(self.db, 1, layout, "tester")
        self.db.commit()
        reset_dashboard_layout(self.db, 1, "tester")
        self.db.commit()
        loaded = get_dashboard_layout(self.db, 1, self.scope)
        self.assertEqual(loaded["source"], "default")

    def test_widget_preferences(self):
        prefs = save_widget_preferences(
            self.db,
            1,
            {"favorites": ["notifications"], "widgets": {"notifications": {"favorite": True, "visible": True}}},
            "tester",
        )
        self.db.commit()
        self.assertIn("notifications", prefs["favorites"])


if __name__ == "__main__":
    unittest.main()
