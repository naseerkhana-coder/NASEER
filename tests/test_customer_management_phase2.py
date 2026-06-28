"""Customer Management Phase 2 — delete cascade, admin onboarding, tenant settings, bank schema."""
import sqlite3
import unittest

from company_master_service import ensure_company_master_schema
from super_admin_service import (
    create_customer_admin_user,
    delete_customer,
    ensure_super_admin_schema,
    get_customer_by_id,
    list_audit_logs,
    save_customer,
    save_customer_tenant_settings,
)


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
            workflow_role TEXT,
            employee_name TEXT,
            status TEXT DEFAULT 'Active',
            customer_id INTEGER
        )
        """
    )
    ensure_super_admin_schema(conn)
    conn.commit()
    return conn


class CustomerManagementPhase2Test(unittest.TestCase):
    def test_delete_customer_cascade_removes_users_and_audits(self):
        db = _memory_db()

        def _hash(pw):
            return f"hashed:{pw}"

        customer_id = save_customer(
            db,
            {
                "customer_code": "TST001",
                "company_name": "Test Tenant Ltd",
                "country": "India",
                "plan": "Standard",
                "status": "Active",
            },
        )
        create_customer_admin_user(
            db,
            customer_id,
            username="tenantadmin",
            password="Secret123",
            confirm_password="Secret123",
            display_name="Tenant Admin",
            email="admin@test.local",
            mobile="+919999999999",
            hash_password_fn=_hash,
        )
        db.commit()
        self.assertEqual(
            db.execute("SELECT COUNT(*) FROM users WHERE customer_id=?", (customer_id,)).fetchone()[0],
            1,
        )

        delete_customer(db, customer_id, cascade=True)
        db.commit()

        self.assertIsNone(get_customer_by_id(db, customer_id))
        self.assertEqual(
            db.execute("SELECT COUNT(*) FROM users WHERE customer_id=?", (customer_id,)).fetchone()[0],
            0,
        )
        audits = list_audit_logs(db)
        delete_entries = [a for a in audits if a.get("action") == "Delete" and "TST001" in (a.get("details") or "")]
        self.assertTrue(delete_entries, "Expected audit log entry for customer delete")

    def test_create_customer_admin_user_requires_matching_password(self):
        db = _memory_db()
        customer_id = save_customer(
            db,
            {
                "customer_code": "TST002",
                "company_name": "Another Tenant",
                "country": "India",
                "plan": "Standard",
                "status": "Active",
            },
        )
        db.commit()
        with self.assertRaises(ValueError):
            create_customer_admin_user(
                db,
                customer_id,
                username="admin2",
                password="abc",
                confirm_password="xyz",
                email="a@b.c",
                mobile="1",
                hash_password_fn=lambda p: p,
            )

    def test_save_customer_tenant_settings_persists_branding_fields(self):
        db = _memory_db()
        customer_id = save_customer(
            db,
            {
                "customer_code": "TST003",
                "company_name": "Branding Co",
                "country": "India",
                "plan": "Standard",
                "status": "Active",
            },
        )
        db.commit()
        save_customer_tenant_settings(
            db,
            customer_id,
            {
                "company_name": "Branding Display Name",
                "logo_path": "uploads/customer_logos/logo.png",
                "theme": "pro-light",
                "address": "123 Main St",
                "vat_gst_number": "27AABCU9603R1ZM",
                "financial_year": "2025-26",
                "currency": "INR",
                "timezone": "Asia/Kolkata",
                "email_settings": "smtp.example.com",
            },
        )
        db.commit()
        row = dict(get_customer_by_id(db, customer_id))
        self.assertEqual(row["company_name"], "Branding Display Name")
        self.assertEqual(row["logo_path"], "uploads/customer_logos/logo.png")
        self.assertEqual(row["theme"], "pro-light")
        self.assertEqual(row["financial_year"], "2025-26")
        self.assertEqual(row["email_settings"], "smtp.example.com")

    def test_company_master_bank_columns_exist(self):
        conn = sqlite3.connect(":memory:")
        try:
            ensure_company_master_schema(conn)
            cols = {
                row[1]
                for row in conn.execute("PRAGMA table_info(companies)").fetchall()
            }
            for required in (
                "bank_name",
                "bank_branch_name",
                "bank_account_name",
                "bank_account_number",
                "bank_ifsc",
                "bank_swift",
                "bank_upi",
            ):
                self.assertIn(required, cols, f"Missing companies.{required}")
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
