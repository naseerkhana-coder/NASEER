"""Unit and integration tests for User Management (MODULE-004)."""

from __future__ import annotations

import sqlite3
import unittest

from branch_master_service import ensure_branch_master_schema, save_branch_master
from company_master_service import ensure_company_master_schema, save_company
from department_master_service import ensure_department_master_schema, save_department_master
from user_import_service import save_user_import, validate_user_import
from user_management_service import (
    USER_STATUSES,
    activate_user_master,
    ai_validate_user,
    deactivate_user_master,
    ensure_user_master_schema,
    export_users_csv,
    get_user_master,
    hash_user_password,
    list_users_master,
    lock_user_master,
    record_failed_login,
    reset_user_password,
    save_user_master,
    soft_delete_user_master,
    unlock_user_master,
    user_can_user_management,
    user_is_login_allowed,
    validate_password_policy,
    validate_user_uniqueness,
    verify_user_password,
)


def _seed_org(conn) -> tuple[int, int, int]:
    company_id = save_company(
        conn,
        {
            "legal_name": "User Test Construction Pvt Ltd",
            "company_name": "User Test Co",
            "country": "India",
            "status": "Active",
        },
        "tester",
    )
    branch_id = save_branch_master(
        conn,
        {
            "company_id": company_id,
            "branch_code": "BR-UT-01",
            "branch_name": "Head Office",
            "status": "Active",
        },
        "tester",
    )
    dept_id = save_department_master(
        conn,
        {
            "company_id": company_id,
            "department_code": "DEPT-UT-01",
            "department_name": "Operations",
            "status": "Active",
        },
        "tester",
    )
    return company_id, branch_id, dept_id


class UserMasterSchemaTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_user_master_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_schema_has_module004_columns(self):
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(users)").fetchall()}
        for col in (
            "company_id",
            "branch_id",
            "department_id",
            "email",
            "mobile",
            "account_locked",
            "login_attempt_count",
            "password_expiry",
            "is_deleted",
            "profile_photo",
        ):
            self.assertIn(col, cols)
        tables = {
            row[0]
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        self.assertIn("user_password_history", tables)
        self.assertIn("user_password_reset_tokens", tables)


class UserPasswordPolicyTests(unittest.TestCase):
    def test_password_policy_rules(self):
        with self.assertRaises(ValueError):
            validate_password_policy("short")
        with self.assertRaises(ValueError):
            validate_password_policy("alllowercase1!")
        validate_password_policy("ValidPass1!")

    def test_hash_and_verify(self):
        hashed = hash_user_password("ValidPass1!")
        self.assertTrue(verify_user_password(hashed, "ValidPass1!"))
        self.assertFalse(verify_user_password(hashed, "wrong"))


class UserMasterCrudTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)
        ensure_branch_master_schema(self.conn)
        ensure_department_master_schema(self.conn)
        ensure_user_master_schema(self.conn)
        self.company_id, self.branch_id, self.dept_id = _seed_org(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def _user_form(self, **overrides):
        data = {
            "company_id": self.company_id,
            "branch_id": self.branch_id,
            "department_id": self.dept_id,
            "username": "jdoe",
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "mobile": "+91 9876543210",
            "system_role": "User",
            "workflow_role": "Maker",
            "status": "Active",
        }
        data.update(overrides)
        return data

    def test_create_update_lock_unlock_and_soft_delete(self):
        uid = save_user_master(self.conn, self._user_form(), "creator", password="ValidPass1!")
        self.conn.commit()
        row = get_user_master(self.conn, uid)
        self.assertIsNotNone(row)
        self.assertEqual(row["username"], "jdoe")
        self.assertEqual(row["status"], "Active")

        save_user_master(
            self.conn,
            self._user_form(mobile="+91 9876543211"),
            "editor",
            user_id=uid,
        )
        self.conn.commit()
        updated = get_user_master(self.conn, uid)
        self.assertEqual(updated["mobile"], "+91 9876543211")

        deactivate_user_master(self.conn, uid, "admin")
        self.conn.commit()
        self.assertEqual(get_user_master(self.conn, uid)["status"], "Inactive")

        activate_user_master(self.conn, uid, "admin")
        self.conn.commit()

        lock_user_master(self.conn, uid, "admin")
        self.conn.commit()
        locked = get_user_master(self.conn, uid)
        self.assertEqual(int(locked["account_locked"] or 0), 1)
        self.assertFalse(user_is_login_allowed(locked))

        unlock_user_master(self.conn, uid, "admin")
        self.conn.commit()

        reset_user_password(self.conn, uid, "NewValid1!", "admin", notify=False)
        self.conn.commit()

        listing = list_users_master(self.conn, search="jdoe", per_page=10)
        self.assertEqual(listing["total"], 1)

        soft_delete_user_master(self.conn, uid, "deleter")
        self.conn.commit()
        self.assertIsNone(get_user_master(self.conn, uid))

    def test_uniqueness_validation(self):
        save_user_master(self.conn, self._user_form(), "creator", password="ValidPass1!")
        self.conn.commit()
        with self.assertRaises(ValueError):
            validate_user_uniqueness(
                self.conn,
                username="jdoe",
                email="other@example.com",
                mobile="+91 9000000001",
            )

    def test_failed_login_lockout(self):
        uid = save_user_master(self.conn, self._user_form(), "creator", password="ValidPass1!")
        self.conn.commit()
        for _ in range(5):
            record_failed_login(self.conn, "jdoe")
        self.conn.commit()
        row = get_user_master(self.conn, uid)
        self.assertEqual(int(row["account_locked"] or 0), 1)

    def test_export_csv(self):
        save_user_master(self.conn, self._user_form(), "creator", password="ValidPass1!")
        self.conn.commit()
        csv_text = export_users_csv(self.conn)
        self.assertIn("username", csv_text)
        self.assertIn("jdoe", csv_text)


class UserImportTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)
        ensure_branch_master_schema(self.conn)
        ensure_department_master_schema(self.conn)
        ensure_user_master_schema(self.conn)
        self.company_id, self.branch_id, self.dept_id = _seed_org(self.conn)
        company = self.conn.execute(
            "SELECT company_code FROM companies WHERE id=?", (self.company_id,)
        ).fetchone()
        branch = self.conn.execute(
            "SELECT branch_code FROM company_branches WHERE id=?", (self.branch_id,)
        ).fetchone()
        dept = self.conn.execute(
            "SELECT department_code FROM departments WHERE id=?", (self.dept_id,)
        ).fetchone()
        self.company_code = company[0]
        self.branch_code = branch[0]
        self.dept_code = dept[0]
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_import_validate_and_save(self):
        rows = [
            {
                "_row_num": 2,
                "Company Code": self.company_code,
                "Branch Code": self.branch_code,
                "Department Code": self.dept_code,
                "Username": "importuser",
                "Password": "Import1!Pass",
                "First Name": "Import",
                "Last Name": "User",
                "Email": "import@example.com",
                "Mobile": "+91 9111111111",
                "System Role": "User",
                "Workflow Role": "Maker",
                "Status": "Active",
            }
        ]
        val = validate_user_import(self.conn, rows)
        self.assertTrue(val["ok"])
        result = save_user_import(self.conn, val["parsed_rows"], username="importer")
        self.conn.commit()
        self.assertEqual(result["imported"], 1)
        listing = list_users_master(self.conn, search="importuser")
        self.assertEqual(listing["total"], 1)


class UserPermissionTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_user_master_schema(self.conn)
        self.conn.execute(
            "INSERT INTO users(username, password, role, status) VALUES('adminuser','x','Admin','Active')"
        )
        self.conn.commit()
        self.admin_id = int(self.conn.execute("SELECT id FROM users").fetchone()[0])

    def tearDown(self):
        self.conn.close()

    def test_admin_has_full_access(self):
        self.assertTrue(user_can_user_management(self.conn, self.admin_id, "view", is_admin=True))
        self.assertTrue(user_can_user_management(self.conn, self.admin_id, "import", is_admin=True))


class UserAiValidateTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_user_master_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_ai_validate_flags_missing_fields(self):
        result = ai_validate_user(self.conn, form={"username": "solo"})
        self.assertFalse(result["ok"])
        self.assertTrue(result["issues"])


if __name__ == "__main__":
    unittest.main()
