"""Unit and integration tests for Roles & Permissions (MODULE-006)."""

from __future__ import annotations

import json
import sqlite3
import unittest

from branch_master_service import ensure_branch_master_schema, save_branch_master
from company_master_service import ensure_company_master_schema, save_company
from department_master_service import ensure_department_master_schema, save_department_master
from roles_permissions_import_service import save_roles_import, validate_roles_import
from roles_permissions_service import (
    DEFAULT_ROLE_TYPES,
    STANDARD_ACTIONS,
    activate_role_master,
    aggregate_user_role_permissions,
    assign_roles_to_user,
    deactivate_role_master,
    ensure_roles_permissions_schema,
    export_roles_csv,
    get_role_master,
    get_role_permission_matrix,
    is_roles_super_administrator,
    list_permissions_master,
    list_roles_for_user,
    list_roles_master,
    save_permission_master,
    save_role_master,
    save_role_permission_matrix,
    soft_delete_role_master,
    user_can_roles_permissions,
    user_has_assigned_role_permission,
    validate_role_uniqueness,
)
from user_management_service import ensure_user_master_schema, hash_user_password, save_user_master


def _seed_company(conn) -> int:
    return save_company(
        conn,
        {
            "legal_name": "Omega Construction Private Limited",
            "company_name": "Omega Construction",
            "country": "India",
            "status": "Active",
        },
        "tester",
    )


def _seed_org(conn) -> tuple[int, int, int]:
    company_id = _seed_company(conn)
    branch_id = save_branch_master(
        conn,
        {
            "company_id": company_id,
            "branch_code": "BR-RP-01",
            "branch_name": "Head Office",
            "status": "Active",
        },
        "tester",
    )
    dept_id = save_department_master(
        conn,
        {
            "company_id": company_id,
            "department_code": "DEPT-RP-01",
            "department_name": "Operations",
            "status": "Active",
        },
        "tester",
    )
    return company_id, branch_id, dept_id


def _seed_user(
    conn,
    company_id: int,
    branch_id: int,
    department_id: int,
    username: str = "testuser",
) -> int:
    ensure_user_master_schema(conn)
    return save_user_master(
        conn,
        {
            "username": username,
            "password": hash_user_password("Test@1234"),
            "company_id": company_id,
            "branch_id": branch_id,
            "department_id": department_id,
            "employee_name": "Test User",
            "email": f"{username}@example.com",
            "status": "Active",
        },
        "tester",
        password="Test@1234",
    )


class RolesPermissionsSchemaTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)
        _seed_company(self.conn)
        ensure_roles_permissions_schema(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_schema_tables_exist(self):
        tables = {
            row[0]
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        for table in ("roles", "permissions", "role_permissions", "user_roles"):
            self.assertIn(table, tables)

    def test_default_roles_seeded(self):
        count = self.conn.execute(
            "SELECT COUNT(*) FROM roles WHERE COALESCE(is_deleted,0)=0"
        ).fetchone()[0]
        self.assertGreaterEqual(int(count), len(DEFAULT_ROLE_TYPES))

    def test_default_permissions_seeded(self):
        count = self.conn.execute(
            "SELECT COUNT(*) FROM permissions WHERE COALESCE(is_deleted,0)=0"
        ).fetchone()[0]
        self.assertGreater(int(count), 0)


class RolesPermissionsValidationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)
        self.company_id = _seed_company(self.conn)
        ensure_roles_permissions_schema(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_unique_code_and_name_per_company(self):
        form = {
            "company_id": self.company_id,
            "role_code": "SITE-ENG",
            "role_name": "Site Engineer Custom",
            "status": "Active",
        }
        save_role_master(self.conn, form, "creator")
        self.conn.commit()
        with self.assertRaises(ValueError):
            validate_role_uniqueness(
                self.conn,
                company_id=self.company_id,
                role_code="SITE-ENG",
                role_name="Other Name",
            )
        with self.assertRaises(ValueError):
            validate_role_uniqueness(
                self.conn,
                company_id=self.company_id,
                role_code="SITE-ENG-2",
                role_name="Site Engineer Custom",
            )


class RolesPermissionsCrudTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)
        self.company_id = _seed_company(self.conn)
        ensure_roles_permissions_schema(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_create_update_activate_deactivate_delete(self):
        rid = save_role_master(
            self.conn,
            {
                "company_id": self.company_id,
                "role_code": "CUSTOM-01",
                "role_name": "Custom Role Alpha",
                "description": "Test role",
                "status": "Active",
            },
            "creator",
        )
        self.conn.commit()
        row = get_role_master(self.conn, rid)
        self.assertIsNotNone(row)
        self.assertEqual(row["role_name"], "Custom Role Alpha")

        save_role_master(
            self.conn,
            {
                "company_id": self.company_id,
                "role_code": "CUSTOM-01",
                "role_name": "Custom Role Beta",
                "description": "Updated",
                "status": "Active",
            },
            "editor",
            rid,
        )
        self.conn.commit()
        updated = get_role_master(self.conn, rid)
        self.assertEqual(updated["role_name"], "Custom Role Beta")

        deactivate_role_master(self.conn, rid, "editor")
        self.conn.commit()
        self.assertEqual(get_role_master(self.conn, rid)["status"], "Inactive")

        activate_role_master(self.conn, rid, "editor")
        self.conn.commit()
        self.assertEqual(get_role_master(self.conn, rid)["status"], "Active")

        soft_delete_role_master(self.conn, rid, "editor")
        self.conn.commit()
        self.assertIsNone(get_role_master(self.conn, rid))

    def test_system_role_cannot_delete(self):
        admin = self.conn.execute(
            "SELECT id FROM roles WHERE role_name='Administrator' LIMIT 1"
        ).fetchone()
        self.assertIsNotNone(admin)
        with self.assertRaises(ValueError):
            soft_delete_role_master(self.conn, int(admin[0]), "tester")


class RolesPermissionsMatrixTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)
        self.company_id = _seed_company(self.conn)
        ensure_roles_permissions_schema(self.conn)
        self.conn.commit()
        self.role_id = save_role_master(
            self.conn,
            {
                "company_id": self.company_id,
                "role_code": "MATRIX-01",
                "role_name": "Matrix Test Role",
                "status": "Active",
            },
            "creator",
        )
        self.conn.commit()
        perm = list_permissions_master(self.conn, per_page=1)["items"][0]
        self.permission_id = int(perm["id"])

    def tearDown(self):
        self.conn.close()

    def test_save_and_read_matrix(self):
        flags = {a: (a == "view") for a in STANDARD_ACTIONS}
        save_role_permission_matrix(
            self.conn,
            self.role_id,
            [{"permission_id": self.permission_id, "action_flags": flags}],
            "tester",
        )
        self.conn.commit()
        matrix = get_role_permission_matrix(self.conn, self.role_id)
        assigned = [m for m in matrix if m["id"] == self.permission_id][0]
        self.assertTrue(assigned["action_flags"]["view"])
        self.assertFalse(assigned["action_flags"]["delete"])


class RolesPermissionsAssignmentTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)
        ensure_branch_master_schema(self.conn)
        ensure_department_master_schema(self.conn)
        ensure_user_master_schema(self.conn)
        self.company_id, self.branch_id, self.dept_id = _seed_org(self.conn)
        ensure_roles_permissions_schema(self.conn)
        self.user_id = _seed_user(self.conn, self.company_id, self.branch_id, self.dept_id)
        self.conn.commit()
        self.role_id = save_role_master(
            self.conn,
            {
                "company_id": self.company_id,
                "role_code": "ASSIGN-01",
                "role_name": "Assign Test Role",
                "status": "Active",
            },
            "creator",
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_assign_roles_to_user(self):
        assign_roles_to_user(self.conn, self.user_id, [self.role_id], "admin")
        self.conn.commit()
        roles = list_roles_for_user(self.conn, self.user_id)
        self.assertEqual(len(roles), 1)
        self.assertEqual(int(roles[0]["id"]), self.role_id)

    def test_permission_inheritance(self):
        perm = list_permissions_master(self.conn, per_page=1)["items"][0]
        flags = {a: (a in ("view", "export")) for a in STANDARD_ACTIONS}
        save_role_permission_matrix(
            self.conn,
            self.role_id,
            [{"permission_id": perm["id"], "action_flags": flags}],
            "admin",
        )
        assign_roles_to_user(self.conn, self.user_id, [self.role_id], "admin")
        self.conn.commit()
        merged = aggregate_user_role_permissions(self.conn, self.user_id)
        self.assertIn(perm["permission_code"], merged)
        self.assertTrue(merged[perm["permission_code"]]["view"])
        allowed = user_has_assigned_role_permission(
            self.conn,
            self.user_id,
            module_name=perm["module_name"],
            screen_name=perm["screen_name"],
            action="view",
        )
        self.assertTrue(allowed)
        denied = user_has_assigned_role_permission(
            self.conn,
            self.user_id,
            module_name=perm["module_name"],
            screen_name=perm["screen_name"],
            action="delete",
        )
        self.assertFalse(denied)


class RolesPermissionsAccessTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)
        ensure_branch_master_schema(self.conn)
        ensure_department_master_schema(self.conn)
        ensure_user_master_schema(self.conn)
        self.company_id, self.branch_id, self.dept_id = _seed_org(self.conn)
        ensure_roles_permissions_schema(self.conn)
        self.user_id = _seed_user(self.conn, self.company_id, self.branch_id, self.dept_id, "regular")
        self.conn.commit()
        admin_role = self.conn.execute(
            "SELECT id FROM roles WHERE role_name='Administrator' LIMIT 1"
        ).fetchone()
        self.admin_role_id = int(admin_role[0])

    def tearDown(self):
        self.conn.close()

    def test_super_administrator_via_administrator_role(self):
        assign_roles_to_user(self.conn, self.user_id, [self.admin_role_id], "system")
        self.conn.commit()
        self.assertTrue(
            is_roles_super_administrator(self.conn, self.user_id, is_platform_super_admin=False)
        )
        self.assertTrue(
            user_can_roles_permissions(
                self.conn, self.user_id, "create", is_platform_super_admin=False
            )
        )

    def test_regular_user_cannot_create_roles(self):
        self.assertFalse(
            user_can_roles_permissions(
                self.conn, self.user_id, "create", is_platform_super_admin=False
            )
        )


class RolesPermissionsImportExportTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)
        self.company_id = _seed_company(self.conn)
        ensure_roles_permissions_schema(self.conn)
        co = self.conn.execute(
            "SELECT company_code FROM companies WHERE id=?", (self.company_id,)
        ).fetchone()
        self.company_code = co[0]
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_import_and_export(self):
        rows = [
            {
                "_row_num": 2,
                "company_code": self.company_code,
                "role_code": "IMP-01",
                "role_name": "Imported Role",
                "description": "From import",
                "status": "Active",
            }
        ]
        val = validate_roles_import(self.conn, rows)
        self.assertTrue(val["ok"])
        result = save_roles_import(self.conn, val["parsed_rows"], username="importer")
        self.conn.commit()
        self.assertEqual(result["imported"], 1)
        csv_text = export_roles_csv(self.conn, company_id=self.company_id)
        self.assertIn("Imported Role", csv_text)


class RolesPermissionsPermissionCrudTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)
        _seed_company(self.conn)
        ensure_roles_permissions_schema(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_create_permission(self):
        pid = save_permission_master(
            self.conn,
            {
                "permission_code": "TST-CUSTOM",
                "permission_name": "Custom Screen",
                "module_name": "Testing",
                "screen_name": "custom_screen",
                "status": "Active",
            },
            "admin",
        )
        self.conn.commit()
        listing = list_permissions_master(self.conn, search="TST-CUSTOM")
        self.assertEqual(listing["total"], 1)
        self.assertEqual(int(listing["items"][0]["id"]), pid)


if __name__ == "__main__":
    unittest.main()
