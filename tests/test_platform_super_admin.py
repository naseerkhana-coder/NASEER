"""Platform Super Admin access gate — v1.0.1 hotfix."""

import os
import sqlite3
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from super_admin_service import (
    PLATFORM_CUSTOMER_CODE,
    SUPER_ADMIN_ROLE,
    ensure_super_admin_schema,
    is_platform_super_admin,
    save_customer,
)


class PlatformSuperAdminTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_super_admin_schema(self.conn)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                password TEXT,
                role TEXT,
                status TEXT,
                customer_id INTEGER
            )
            """
        )
        self.conn.execute(
            """
            INSERT INTO erp_customers(
                customer_code, company_name, country, plan, package_code,
                enabled_departments, status, is_platform, created_at, modified_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (
                PLATFORM_CUSTOMER_CODE,
                "MAXEK Platform",
                "India",
                "Enterprise",
                "Enterprise",
                '["projects"]',
                "Active",
                1,
                "2026-01-01",
                "2026-01-01",
            ),
        )
        save_customer(
            self.conn,
            {
                "customer_code": "TRD001",
                "company_name": "Tenant Co",
                "country": "India",
                "status": "Active",
                "enabled_departments": ["projects"],
            },
        )
        self.conn.commit()
        platform_id = self.conn.execute(
            "SELECT id FROM erp_customers WHERE customer_code=?",
            (PLATFORM_CUSTOMER_CODE,),
        ).fetchone()["id"]
        tenant_id = self.conn.execute(
            "SELECT id FROM erp_customers WHERE customer_code=?",
            ("TRD001",),
        ).fetchone()["id"]
        self.conn.execute(
            "INSERT INTO users(username, password, role, status, customer_id) VALUES(?,?,?,?,?)",
            ("platform_sa", "x", SUPER_ADMIN_ROLE, "Active", platform_id),
        )
        self.conn.execute(
            "INSERT INTO users(username, password, role, status, customer_id) VALUES(?,?,?,?,?)",
            ("platform_admin", "x", "Admin", "Active", platform_id),
        )
        self.conn.execute(
            "INSERT INTO users(username, password, role, status, customer_id) VALUES(?,?,?,?,?)",
            ("tenant_admin", "x", "Admin", "Active", tenant_id),
        )
        self.conn.execute(
            "INSERT INTO users(username, password, role, status, customer_id) VALUES(?,?,?,?,?)",
            ("tenant_sa", "x", SUPER_ADMIN_ROLE, "Active", tenant_id),
        )
        self.conn.commit()
        self.users = {
            row["username"]: row
            for row in self.conn.execute("SELECT * FROM users").fetchall()
        }

    def tearDown(self):
        self.conn.close()

    def test_platform_super_admin_on_platform_tenant(self):
        self.assertTrue(
            is_platform_super_admin(self.conn, self.users["platform_sa"])
        )

    def test_platform_admin_role_not_super_admin(self):
        self.assertFalse(
            is_platform_super_admin(self.conn, self.users["platform_admin"])
        )

    def test_tenant_admin_not_platform_super_admin(self):
        self.assertFalse(
            is_platform_super_admin(self.conn, self.users["tenant_admin"])
        )

    def test_tenant_super_admin_role_not_platform_super_admin(self):
        self.assertFalse(
            is_platform_super_admin(self.conn, self.users["tenant_sa"])
        )


if __name__ == "__main__":
    unittest.main()
