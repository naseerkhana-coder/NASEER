"""Dashboard theme resolution and tenant persistence."""
import sqlite3
import unittest

from dashboard_prefs_service import (
    DEFAULT_DASHBOARD_THEME,
    resolve_dashboard_theme,
    resolve_effective_dashboard_theme,
    save_dashboard_preferences,
)
from super_admin_service import (
    ensure_super_admin_schema,
    get_customer_by_id,
    save_customer,
    save_customer_tenant_settings,
)
from user_context_service import ensure_user_context_schema


def _memory_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            password TEXT,
            role TEXT,
            customer_id INTEGER
        )
        """
    )
    ensure_super_admin_schema(conn)
    ensure_user_context_schema(conn)
    conn.commit()
    return conn


class DashboardThemeTest(unittest.TestCase):
    def test_company_default_is_command_centre(self):
        db = _memory_db()
        customer_id = save_customer(
            db,
            {
                "customer_code": "THM001",
                "company_name": "Theme Co",
                "country": "India",
                "plan": "Standard",
                "status": "Active",
            },
        )
        db.commit()
        resolved = resolve_dashboard_theme(db, user_id=99, customer_id=customer_id)
        self.assertEqual(resolved["effective"], DEFAULT_DASHBOARD_THEME)
        self.assertEqual(resolved["source"], "company")
        self.assertEqual(resolved["template"], "dashboard.html")

    def test_user_override_beats_company_default(self):
        db = _memory_db()
        customer_id = save_customer(
            db,
            {
                "customer_code": "THM002",
                "company_name": "Override Co",
                "country": "India",
                "plan": "Standard",
                "status": "Active",
            },
        )
        save_customer_tenant_settings(
            db,
            customer_id,
            {"company_name": "Override Co", "dashboard_theme": "command-centre"},
        )
        db.execute(
            "INSERT INTO users(id, username, password, role, customer_id) VALUES(1,'u','p','Admin',?)",
            (customer_id,),
        )
        save_dashboard_preferences(db, 1, dashboard_layout_theme="executive")
        db.commit()
        resolved = resolve_dashboard_theme(db, user_id=1, customer_id=customer_id)
        self.assertEqual(resolved["effective"], "executive")
        self.assertEqual(resolved["source"], "user")
        self.assertEqual(resolved["template"], "dashboard_theme_executive.html")

    def test_placeholder_theme_falls_back_with_notice(self):
        effective, notice = resolve_effective_dashboard_theme("kpi")
        self.assertEqual(effective, DEFAULT_DASHBOARD_THEME)
        self.assertIn("coming soon", (notice or "").lower())

    def test_tenant_dashboard_theme_persists(self):
        db = _memory_db()
        customer_id = save_customer(
            db,
            {
                "customer_code": "THM003",
                "company_name": "Persist Co",
                "country": "India",
                "plan": "Standard",
                "status": "Active",
            },
        )
        save_customer_tenant_settings(
            db,
            customer_id,
            {"company_name": "Persist Co", "dashboard_theme": "compact"},
        )
        db.commit()
        row = dict(get_customer_by_id(db, customer_id))
        self.assertEqual(row["dashboard_theme"], "compact")
        resolved = resolve_dashboard_theme(db, user_id=None, customer_id=customer_id)
        self.assertEqual(resolved["effective"], "compact")
        self.assertEqual(resolved["template"], "dashboard_theme_compact.html")


if __name__ == "__main__":
    unittest.main()
