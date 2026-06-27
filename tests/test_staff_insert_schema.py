"""Verify staff INSERT column/placeholder alignment and runtime schema."""
import os
import sqlite3
import tempfile
import unittest


STAFF_INSERT_COLUMNS = (
    "employee_code, staff_name, mobile, email, department, designation, "
    "designation_id, reporting_manager, workflow_role, salary_type, salary_amount, "
    "ot_applicable, ot_rate_per_hour, holiday_pay_applicable, working_hours, joining_date, "
    "date_of_birth, gender, photo, status, "
    "aadhaar_number, pan_number, bank_account, bank_name, ifsc_code, branch_name, id_proof, "
    "aadhaar_document, pan_document, company_room_provided, company_food_provided"
)


def _count_placeholders(values_clause: str) -> int:
    inner = values_clause.strip()
    if inner.startswith("(") and inner.endswith(")"):
        inner = inner[1:-1]
    return len([p for p in inner.split(",") if p.strip() == "?"])


class StaffInsertSchemaTest(unittest.TestCase):
    def test_insert_column_count_matches_placeholders_in_app_source(self):
        app_path = os.path.join(os.path.dirname(__file__), "..", "app.py")
        with open(app_path, encoding="utf-8") as fh:
            lines = fh.readlines()
        values_line = next(
            line
            for line in lines
            if "INSERT INTO staff(" in line
            or (
                "customer_id, company_id, branch_id)" in line
                and "VALUES(" in line
            )
        )
        if "VALUES(" not in values_line:
            idx = next(
                i
                for i, line in enumerate(lines)
                if "customer_id, company_id, branch_id)" in line
            )
            values_line = lines[idx + 1]
        start = values_line.index("VALUES(") + 7
        end = values_line.index(")", start)
        values_clause = values_line[start:end]
        col_count = len([c.strip() for c in STAFF_INSERT_COLUMNS.split(",") if c.strip()]) + 3
        self.assertEqual(_count_placeholders(values_clause), col_count)

    def test_runtime_insert_after_schema_bootstrap(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            conn.execute(
                """
                CREATE TABLE staff(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_code TEXT,
                    staff_name TEXT,
                    mobile TEXT,
                    email TEXT,
                    department TEXT,
                    designation TEXT,
                    salary_type TEXT,
                    salary_amount REAL,
                    ot_applicable TEXT,
                    working_hours REAL,
                    joining_date TEXT,
                    photo TEXT,
                    status TEXT
                )
                """
            )
            staff_master_columns = (
                ("designation_id", "INTEGER"),
                ("reporting_manager", "TEXT"),
                ("workflow_role", "TEXT"),
                ("ot_rate_per_hour", "REAL DEFAULT 0"),
                ("holiday_pay_applicable", "TEXT DEFAULT 'No'"),
                ("date_of_birth", "TEXT"),
                ("gender", "TEXT"),
                ("aadhaar_number", "TEXT"),
                ("pan_number", "TEXT"),
                ("bank_account", "TEXT"),
                ("bank_name", "TEXT"),
                ("ifsc_code", "TEXT"),
                ("branch_name", "TEXT"),
                ("id_proof", "TEXT"),
                ("aadhaar_document", "TEXT"),
                ("pan_document", "TEXT"),
                ("company_room_provided", "TEXT DEFAULT 'No'"),
                ("company_food_provided", "TEXT DEFAULT 'No'"),
            )
            for column, col_type in staff_master_columns:
                conn.execute(f"ALTER TABLE staff ADD COLUMN {column} {col_type}")
            for tenant_col in ("customer_id", "company_id", "branch_id"):
                conn.execute(f"ALTER TABLE staff ADD COLUMN {tenant_col} INTEGER")
            values = (
                "EMP101",
                "Test User",
                "9999999999",
                "test@example.com",
                "HR",
                "Engineer",
                1,
                "Manager",
                None,
                "Monthly",
                50000.0,
                "No",
                0.0,
                "No",
                8.0,
                "2026-01-01",
                "1990-01-01",
                "Male",
                None,
                "Active",
                "",
                "",
                "",
                "",
                "",
                "",
                None,
                None,
                None,
                "No",
                "No",
            )
            placeholders = ",".join(["?"] * len(values))
            conn.execute(
                f"INSERT INTO staff({STAFF_INSERT_COLUMNS}) VALUES({placeholders})",
                values,
            )
            row = conn.execute("SELECT staff_name FROM staff WHERE employee_code='EMP101'").fetchone()
            self.assertEqual(row["staff_name"], "Test User")
            conn.close()


if __name__ == "__main__":
    unittest.main()
