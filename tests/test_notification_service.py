"""Unit and integration tests for Notification Center (MODULE-022)."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from notification_service import (
    NOTIFICATION_TYPES,
    ensure_notification_schema,
    get_dashboard_metrics,
    get_notification,
    get_unread_count,
    get_user_notification_preferences,
    get_user_notifications,
    mark_all_as_read,
    mark_as_read,
    notify_user,
    retry_failed_notification,
    schedule_notification,
    send_email,
    send_in_app,
    send_notification,
    send_sms,
    set_user_notification_preferences,
    user_can_notification_center,
)


def _base_users_schema(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            email TEXT,
            mobile TEXT,
            company_id INTEGER,
            branch_id INTEGER,
            role TEXT,
            status TEXT DEFAULT 'Active'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS permissions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            permission_code TEXT,
            permission_name TEXT,
            module_name TEXT,
            menu_name TEXT,
            screen_name TEXT,
            action TEXT,
            description TEXT,
            status TEXT DEFAULT 'Active',
            is_deleted INTEGER DEFAULT 0
        )
        """
    )
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
        "INSERT INTO users(id, username, email, mobile, company_id, branch_id) VALUES (1,'alice','alice@test.com','9000000001',1,1)"
    )
    conn.execute(
        "INSERT INTO users(id, username, email, mobile, company_id, branch_id) VALUES (2,'bob','bob@test.com','9000000002',1,2)"
    )
    conn.execute(
        """
        INSERT INTO user_tab_permissions(user_id, endpoint, granted, action_flags)
        VALUES (1, 'notification_center', 1, ?)
        """,
        (json.dumps({"view": True, "create": True, "edit": True, "delete": False}),),
    )


class NotificationSchemaTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _base_users_schema(self.conn)
        ensure_notification_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_tables_created(self):
        tables = {
            r[0]
            for r in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        for name in (
            "notifications",
            "notification_templates",
            "notification_channels",
            "notification_preferences",
            "notification_logs",
        ):
            self.assertIn(name, tables)

    def test_default_channels_seeded(self):
        count = self.conn.execute("SELECT COUNT(*) FROM notification_channels").fetchone()[0]
        self.assertGreaterEqual(count, 3)

    def test_default_templates_seeded(self):
        count = self.conn.execute("SELECT COUNT(*) FROM notification_templates").fetchone()[0]
        self.assertGreaterEqual(count, 1)

    def test_notification_columns_extended(self):
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(notifications)").fetchall()}
        for col in ("uuid", "priority", "title", "channel", "status", "ai_metadata"):
            self.assertIn(col, cols)


class NotificationServiceTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _base_users_schema(self.conn)
        ensure_notification_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_send_notification_in_app(self):
        result = send_notification(
            self.conn,
            {
                "user_id": 1,
                "message": "Task assigned to you",
                "notification_type": "Task Assigned",
                "title": "New task",
                "module": "tasks",
                "priority": "Normal",
                "channel": "in_app",
            },
        )
        self.assertTrue(result.get("ok"))
        nid = result["notification_id"]
        row = self.conn.execute("SELECT * FROM notifications WHERE id=?", (nid,)).fetchone()
        self.assertEqual(row["status"], "Sent")
        self.assertEqual(row["user_id"], 1)
        logs = self.conn.execute(
            "SELECT COUNT(*) FROM notification_logs WHERE notification_id=?", (nid,)
        ).fetchone()[0]
        self.assertGreaterEqual(logs, 1)

    def test_notify_user_wrapper(self):
        result = notify_user(
            self.conn,
            1,
            "Payment received",
            "Payment Received",
            title="Invoice paid",
            module="finance",
        )
        self.assertTrue(result.get("ok"))

    def test_mark_as_read(self):
        result = send_notification(
            self.conn,
            {
                "user_id": 1,
                "message": "Unread",
                "notification_type": "Custom Notification",
            },
        )
        nid = result["notification_id"]
        mark_as_read(self.conn, 1, nid)
        row = self.conn.execute("SELECT is_read, read_status FROM notifications WHERE id=?", (nid,)).fetchone()
        self.assertEqual(row["is_read"], 1)
        self.assertEqual(row["read_status"], "read")

    def test_mark_as_read_denies_other_user(self):
        result = send_notification(
            self.conn,
            {"user_id": 1, "message": "Private", "notification_type": "Custom Notification"},
        )
        with self.assertRaises(PermissionError):
            mark_as_read(self.conn, 2, result["notification_id"])

    def test_mark_all_as_read(self):
        for _ in range(3):
            notify_user(self.conn, 1, "msg", "Custom Notification")
        mark_all_as_read(self.conn, 1)
        self.assertEqual(get_unread_count(self.conn, 1), 0)

    def test_preferences_round_trip(self):
        prefs = set_user_notification_preferences(
            self.conn,
            1,
            {
                "email_enabled": False,
                "sms_enabled": True,
                "quiet_hours_start": "22:00",
                "quiet_hours_end": "07:00",
                "daily_summary": True,
            },
        )
        self.assertFalse(prefs["email_enabled"])
        self.assertTrue(prefs["sms_enabled"])
        loaded = get_user_notification_preferences(self.conn, 1)
        self.assertTrue(loaded["daily_summary"])
        self.assertEqual(loaded["quiet_hours_start"], "22:00")

    def test_module_preference_blocks_send(self):
        set_user_notification_preferences(
            self.conn,
            1,
            {"module_preferences": {"tasks": False}},
        )
        result = send_notification(
            self.conn,
            {
                "user_id": 1,
                "message": "Blocked",
                "notification_type": "Task Assigned",
                "module": "tasks",
            },
        )
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("reason"), "module_disabled")

    def test_schedule_notification(self):
        result = schedule_notification(
            self.conn,
            {
                "user_id": 1,
                "message": "Future",
                "notification_type": "Custom Notification",
                "scheduled_at": "2026-12-01 09:00:00",
            },
        )
        self.assertEqual(result["status"], "Scheduled")
        row = self.conn.execute(
            "SELECT status FROM notifications WHERE id=?", (result["notification_id"],)
        ).fetchone()
        self.assertEqual(row["status"], "Scheduled")

    def test_email_sms_stubs(self):
        result = send_notification(
            self.conn,
            {
                "user_id": 1,
                "message": "Multi-channel",
                "notification_type": "Security Alert",
                "channel": "all",
                "priority": "Critical",
            },
        )
        self.assertTrue(result.get("ok"))
        logs = self.conn.execute(
            "SELECT channel FROM notification_logs WHERE notification_id=?",
            (result["notification_id"],),
        ).fetchall()
        channels = {r[0] for r in logs}
        self.assertIn("in_app", channels)
        self.assertIn("email", channels)

    def test_retry_failed_notification(self):
        nid = send_notification(
            self.conn,
            {"user_id": 1, "message": "Retry me", "notification_type": "System Error"},
        )["notification_id"]
        self.conn.execute(
            "UPDATE notifications SET status='Failed', failed_reason='timeout' WHERE id=?",
            (nid,),
        )
        result = retry_failed_notification(self.conn, nid, actor="tester")
        self.assertTrue(result.get("ok"))
        row = self.conn.execute("SELECT status FROM notifications WHERE id=?", (nid,)).fetchone()
        self.assertEqual(row["status"], "Sent")

    def test_get_user_notifications_pagination(self):
        for i in range(5):
            notify_user(self.conn, 1, f"Msg {i}", "Custom Notification")
        listing = get_user_notifications(self.conn, 1, page=1, per_page=2)
        self.assertEqual(len(listing["items"]), 2)
        self.assertEqual(listing["total"], 5)
        self.assertEqual(listing["pages"], 3)

    def test_dashboard_metrics(self):
        notify_user(self.conn, 1, "High alert", "Security Alert", priority="Critical")
        notify_user(self.conn, 1, "Normal", "Custom Notification")
        metrics = get_dashboard_metrics(self.conn, 1)
        self.assertGreaterEqual(metrics["total"], 2)
        self.assertIn("unread", metrics)
        self.assertIn("delivery_by_channel", metrics)
        self.assertIn("trend", metrics)

    def test_invalid_notification_type(self):
        with self.assertRaises(ValueError):
            send_notification(
                self.conn,
                {"user_id": 1, "message": "Bad", "notification_type": "Not A Real Type"},
            )

    def test_user_isolation_in_get(self):
        nid = notify_user(self.conn, 1, "Secret", "Custom Notification")["notification_id"]
        with self.assertRaises(PermissionError):
            get_notification(self.conn, nid, user_id=2, admin=False)

    def test_channel_stubs_direct(self):
        nid = notify_user(self.conn, 1, "Direct", "Custom Notification")["notification_id"]
        payload = {"user_id": 1, "message": "Direct"}
        self.assertTrue(send_in_app(self.conn, nid, payload).get("ok"))
        self.assertTrue(send_email(self.conn, nid, payload).get("stub"))
        self.assertTrue(send_sms(self.conn, nid, payload).get("stub"))


class NotificationPermissionTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _base_users_schema(self.conn)
        ensure_notification_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_user_with_tab_permission(self):
        self.assertTrue(user_can_notification_center(self.conn, 1, "view"))
        self.assertTrue(user_can_notification_center(self.conn, 1, "create"))

    def test_user_without_permission(self):
        self.assertFalse(user_can_notification_center(self.conn, 2, "create"))

    def test_admin_bypass(self):
        self.assertTrue(user_can_notification_center(self.conn, 2, "create", is_admin=True))


class NotificationApiTests(unittest.TestCase):
    def setUp(self):
        os.environ["MAXEK_SKIP_DEMO_SEED"] = "1"
        import importlib.util

        app_path = os.path.join(ROOT, "app.py")
        spec = importlib.util.spec_from_file_location("maxek_flask_app", app_path)
        flask_app_module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(flask_app_module)
        init_db = flask_app_module.init_db
        get_db = flask_app_module.get_db
        self.app = flask_app_module.app

        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        with self.app.app_context():
            init_db()
        self.client = self.app.test_client()
        with self.app.app_context():
            db = get_db()
            ensure_notification_schema(db)
            row = db.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()
            self.user_id = int(row[0]) if row else 1
            db.execute(
                """
                INSERT OR IGNORE INTO user_tab_permissions(user_id, endpoint, granted, action_flags)
                VALUES (?, 'notification_center', 1, ?)
                """,
                (
                    self.user_id,
                    json.dumps({"view": True, "create": True, "edit": True, "delete": False}),
                ),
            )
            db.commit()

    def _login(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.user_id
            sess["username"] = "admin"
            sess["role"] = "Admin"

    def test_api_send_and_list(self):
        self._login()
        send_resp = self.client.post(
            "/api/v1/notifications/send",
            json={
                "user_id": self.user_id,
                "message": "API test",
                "notification_type": "Custom Notification",
                "title": "API",
            },
        )
        self.assertIn(send_resp.status_code, (200, 201))
        body = send_resp.get_json()
        self.assertTrue(body.get("ok"))

        list_resp = self.client.get("/api/v1/notifications")
        self.assertEqual(list_resp.status_code, 200)
        items = list_resp.get_json().get("items") or []
        self.assertGreaterEqual(len(items), 1)

    def test_api_unread_count_and_read(self):
        self._login()
        self.client.post(
            "/api/v1/notifications/send",
            json={"user_id": self.user_id, "message": "Unread API", "notification_type": "Custom Notification"},
        )
        count_resp = self.client.get("/api/v1/notifications/unread-count")
        self.assertEqual(count_resp.status_code, 200)
        self.assertGreaterEqual(count_resp.get_json().get("unread_count", 0), 1)

        read_all = self.client.post("/api/v1/notifications/read-all", json={})
        self.assertEqual(read_all.status_code, 200)
        count_after = self.client.get("/api/v1/notifications/unread-count").get_json()
        self.assertEqual(count_after.get("unread_count"), 0)

    def test_api_preferences(self):
        self._login()
        put_resp = self.client.put(
            "/api/v1/notifications/preferences",
            json={"email_enabled": False, "daily_summary": True},
        )
        self.assertEqual(put_resp.status_code, 200)
        prefs = self.client.get("/api/v1/notifications/preferences").get_json()
        self.assertFalse(prefs["preferences"]["email_enabled"])
        self.assertTrue(prefs["preferences"]["daily_summary"])

    def test_api_dashboard(self):
        self._login()
        resp = self.client.get("/api/v1/notifications/dashboard")
        self.assertEqual(resp.status_code, 200)
        metrics = resp.get_json().get("metrics") or {}
        self.assertIn("total", metrics)

    def test_notification_center_page(self):
        self._login()
        resp = self.client.get("/settings/notification-center")
        self.assertEqual(resp.status_code, 200)

    def test_validation_error(self):
        self._login()
        resp = self.client.post(
            "/api/v1/notifications/send",
            json={"message": "missing user"},
        )
        self.assertEqual(resp.status_code, 400)


class NotificationTypesTests(unittest.TestCase):
    def test_all_types_declared(self):
        self.assertIn("Approval Pending", NOTIFICATION_TYPES)
        self.assertIn("Custom Notification", NOTIFICATION_TYPES)
        self.assertEqual(len(NOTIFICATION_TYPES), 19)


if __name__ == "__main__":
    unittest.main()
