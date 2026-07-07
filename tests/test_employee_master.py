"""Unit and integration tests for Employee Master (MODULE-014)."""

from __future__ import annotations

import sqlite3
import unittest

from employee_import_service import save_employee_import, validate_employee_import
from employee_master_service import (
    EMPLOYEE_TYPES,
    activate_employee_master,
    ai_validate_employee,
    approve_employee_master,
    deactivate_employee_master,
    employee_has_references,
    employee_report,
    ensure_employee_master_schema,
    export_employees_csv,
    generate_employee_code,
    get_employee_master,
    list_employees_master,
    save_employee_master,
    soft_delete_employee_master,
    user_can_employee_master,
    validate_employee_uniqueness,
)


def _seed_org(conn):
    conn.execute(
        """
        INSERT INTO companies(id, company_code, company_name, legal_name, country, status)
        VALUES(1, 'CO001', 'Maxek Build', 'Maxek Build Pvt Ltd', 'India', 'Active')
        """
    )
    conn.execute(
        """
        INSERT INTO departments(id, company_id, department_code, department_name, status)
        VALUES(1, 1, 'DEPT-HO', 'Head Office', 'Active')
        """
    )
    conn.execute(
        """
        INSERT INTO designations(id, company_id, department_id, designation_code, designation_name, status)
        VALUES(1, 1, 1, 'DES-ENG', 'Site Engineer', 'Active')
        """
    )
    conn.commit()


def _sample_form(**overrides):
    form = {
        "employee_code": "EMP9001",
        "first_name": "Anita",
        "last_name": "Sharma",
        "employee_type": "Permanent",
        "company_id": "1",
        "department_id": "1",
        "designation_id": "1",
        "joining_date": "2026-01-15",
        "official_email": "anita.sharma@maxek.in",
        "mobile": "9876543210",
        "pan_number": "ABCDE1234F",
        "status": "Active",
        "contact_name[]": ["Ravi Sharma"],
        "relationship[]": ["Spouse"],
        "phone[]": ["9876500000"],
        "email[]": ["ravi@example.com"],
        "address[]": ["Bengaluru"],
    }
    form.update(overrides)
    return form


class EmployeeMasterSchemaTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_employee_master_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_schema_has_module014_columns(self):
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(staff)").fetchall()}
        for col in (
            "employee_type",
            "company_id",
            "department_id",
            "designation_id",
            "reporting_manager_id",
            "official_email",
            "profile_photo",
            "digital_signature",
            "employment_status",
            "approval_status",
            "is_deleted",
        ):
            self.assertIn(col, cols)

    def test_child_tables_exist(self):
        tables = {
            row[0]
            for row in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        for table in (
            "employee_emergency_contacts",
            "employee_qualifications",
            "employee_experience",
            "employee_skills",
            "employee_employment_history",
        ):
            self.assertIn(table, tables)


class EmployeeMasterValidationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_employee_master_schema(self.conn)
        _seed_org(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_unique_employee_code_and_email(self):
        save_employee_master(self.conn, _sample_form(), "creator")
        self.conn.commit()
        with self.assertRaises(ValueError):
            validate_employee_uniqueness(
                self.conn,
                employee_code="EMP9001",
                official_email="other@maxek.in",
            )
        with self.assertRaises(ValueError):
            validate_employee_uniqueness(
                self.conn,
                employee_code="EMP9002",
                official_email="anita.sharma@maxek.in",
            )

    def test_mandatory_department_designation_joining(self):
        with self.assertRaises(ValueError):
            save_employee_master(
                self.conn,
                _sample_form(department_id="", designation_id="", joining_date=""),
                "creator",
            )


class EmployeeMasterCrudTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_employee_master_schema(self.conn)
        _seed_org(self.conn)
        self.conn.execute(
            """
            CREATE TABLE users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                staff_id INTEGER
            )
            """
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_create_and_get_employee(self):
        new_id = save_employee_master(self.conn, _sample_form(), "creator")
        self.conn.commit()
        row = get_employee_master(self.conn, new_id)
        self.assertIsNotNone(row)
        self.assertEqual(row["employee_code"], "EMP9001")
        self.assertEqual(row["staff_name"], "Anita Sharma")
        self.assertEqual(row["department"], "Head Office")
        self.assertEqual(len(row["emergency_contacts"]), 1)

    def test_list_and_export(self):
        save_employee_master(self.conn, _sample_form(), "creator")
        self.conn.commit()
        listing = list_employees_master(self.conn, search="Anita")
        self.assertEqual(listing["total"], 1)
        csv_text = export_employees_csv(self.conn)
        self.assertIn("EMP9001", csv_text)

    def test_soft_delete_blocked_by_user_link(self):
        new_id = save_employee_master(self.conn, _sample_form(), "creator")
        self.conn.execute("INSERT INTO users(username, staff_id) VALUES('anita', ?)", (new_id,))
        self.conn.commit()
        self.assertTrue(employee_has_references(self.conn, new_id))
        with self.assertRaises(ValueError):
            soft_delete_employee_master(self.conn, new_id, "admin")
        self.conn.execute("DELETE FROM users WHERE staff_id=?", (new_id,))
        self.conn.commit()
        soft_delete_employee_master(self.conn, new_id, "admin")
        self.conn.commit()
        row = get_employee_master(self.conn, new_id)
        self.assertIsNone(row)

    def test_activate_deactivate_approve(self):
        new_id = save_employee_master(self.conn, _sample_form(), "creator")
        self.conn.commit()
        approve_employee_master(self.conn, new_id, "approver")
        deactivate_employee_master(self.conn, new_id, "admin")
        activate_employee_master(self.conn, new_id, "admin")
        row = get_employee_master(self.conn, new_id)
        self.assertEqual(row["approval_status"], "Approved")
        self.assertEqual(row["status"], "Active")

    def test_generate_employee_code(self):
        code1 = generate_employee_code(self.conn)
        save_employee_master(self.conn, _sample_form(employee_code=code1), "creator")
        self.conn.commit()
        code2 = generate_employee_code(self.conn)
        self.assertNotEqual(code1, code2)

    def test_generate_employee_code_skips_gaps(self):
        for num in (110, 112, 114):
            save_employee_master(
                self.conn,
                _sample_form(employee_code=f"EMP{num}", official_email=f"emp{num}@test.in"),
                "creator",
            )
        self.conn.commit()
        self.assertEqual(generate_employee_code(self.conn), "EMP115")

    def test_generate_employee_code_counts_deleted_and_spaced_codes(self):
        save_employee_master(
            self.conn,
            _sample_form(employee_code="EMP103", official_email="emp103@test.in"),
            "creator",
        )
        save_employee_master(
            self.conn,
            _sample_form(employee_code="EMP 114", official_email="emp114@test.in"),
            "creator",
        )
        self.conn.execute("UPDATE staff SET is_deleted=1 WHERE employee_code='EMP 114'")
        self.conn.commit()
        self.assertEqual(generate_employee_code(self.conn), "EMP115")

    def test_report_directory(self):
        save_employee_master(self.conn, _sample_form(), "creator")
        self.conn.commit()
        rows = employee_report(self.conn, "directory")
        self.assertEqual(len(rows), 1)


class EmployeeMasterImportTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_employee_master_schema(self.conn)
        _seed_org(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_import_row(self):
        rows = [
            {
                "_row_num": 2,
                "employee_code": "EMP9100",
                "first_name": "Vikram",
                "last_name": "Singh",
                "company_code": "CO001",
                "department_code": "DEPT-HO",
                "designation_code": "DES-ENG",
                "joining_date": "2026-02-01",
                "official_email": "vikram@maxek.in",
                "mobile": "9123456780",
                "status": "Active",
            }
        ]
        val = validate_employee_import(self.conn, rows)
        self.assertTrue(val["ok"])
        result = save_employee_import(self.conn, val["parsed_rows"], username="importer")
        self.conn.commit()
        self.assertEqual(result["imported"], 1)


class EmployeeMasterAiTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_employee_master_schema(self.conn)
        _seed_org(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_ai_validate_graceful(self):
        result = ai_validate_employee(
            self.conn,
            form=_sample_form(profile_photo="", aadhaar_document=""),
        )
        self.assertFalse(result["ai_available"])
        self.assertIn("profile_photo", result["missing_documents"])


class EmployeeMasterPermissionTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            """
            CREATE TABLE user_tab_permissions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                endpoint TEXT,
                granted INTEGER,
                action_flags TEXT
            )
            """
        )

    def tearDown(self):
        self.conn.close()

    def test_admin_always_allowed(self):
        self.assertTrue(user_can_employee_master(self.conn, None, "view", is_admin=True))

    def test_denied_without_permission(self):
        self.assertFalse(user_can_employee_master(self.conn, 1, "create", is_admin=False))


if __name__ == "__main__":
    unittest.main()
