"""Verify license INSERT column/placeholder alignment and runtime schema."""
import os
import sqlite3
import tempfile
import unittest

from super_admin_service import ensure_super_admin_schema, save_customer, save_license


LICENSE_INSERT_COLUMNS = (
    "license_no, customer_id, product, plan, start_date, expiry_date, status, "
    "created_at, modified_at"
)


def _count_placeholders(values_clause: str) -> int:
    inner = values_clause.strip()
    if inner.startswith("(") and inner.endswith(")"):
        inner = inner[1:-1]
    return len([p for p in inner.split(",") if p.strip() == "?"])


class LicenseInsertSchemaTest(unittest.TestCase):
    def test_insert_column_count_matches_placeholders_in_service_source(self):
        service_path = os.path.join(os.path.dirname(__file__), "..", "super_admin_service.py")
        with open(service_path, encoding="utf-8") as fh:
            content = fh.read()
        marker = (
            '"INSERT INTO erp_licenses("\n'
            '        "license_no, customer_id, product, plan, start_date, expiry_date, status, created_at, modified_at"\n'
            '        ") VALUES(?,?,?,?,?,?,?,?,?)"'
        )
        start = content.index(marker)
        values_start = content.index("VALUES(", start) + 7
        values_end = content.index(")", values_start)
        values_clause = content[values_start:values_end]
        col_count = len([c.strip() for c in LICENSE_INSERT_COLUMNS.split(",") if c.strip()])
        self.assertEqual(_count_placeholders(values_clause), col_count)

    def test_runtime_insert_after_schema_bootstrap(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            conn.execute(
                """
                CREATE TABLE erp_customers(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_code TEXT UNIQUE NOT NULL,
                    company_name TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE erp_licenses(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    license_no TEXT UNIQUE NOT NULL,
                    customer_id INTEGER NOT NULL
                )
                """
            )
            ensure_super_admin_schema(conn)
            save_customer(
                conn,
                {
                    "customer_code": "TRD001",
                    "company_name": "Test Customer",
                    "country": "India",
                    "plan": "Standard",
                    "status": "Active",
                },
            )
            conn.commit()
            license_id = save_license(
                conn,
                {
                    "license_no": "LIC-2026-TEST",
                    "customer_code": "TRD001",
                    "product": "MAXEK ERP",
                    "plan": "Standard",
                    "status": "Active",
                },
            )
            conn.commit()
            row = conn.execute(
                "SELECT license_no, product, plan, status FROM erp_licenses WHERE id=?",
                (license_id,),
            ).fetchone()
            self.assertIsNotNone(row, f"license row missing for id={license_id}")
            self.assertEqual(row["license_no"], "LIC-2026-TEST")
            self.assertEqual(row["product"], "MAXEK ERP")
            self.assertEqual(row["plan"], "Standard")
            self.assertEqual(row["status"], "Active")
            conn.close()


if __name__ == "__main__":
    unittest.main()
