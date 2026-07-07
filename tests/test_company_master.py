"""Unit and integration tests for Company Master (MODULE-001)."""

from __future__ import annotations

import io
import sqlite3
import unittest

from company_import_service import save_company_import, validate_company_import
from company_master_service import (
    approve_company,
    ensure_company_master_schema,
    export_companies_csv,
    get_company,
    list_companies,
    save_company,
    soft_delete_company,
    validate_company_contact,
    validate_company_uniqueness,
    validate_email,
    validate_gst_number,
    validate_pan_number,
)


class CompanyMasterSchemaTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_schema_has_module001_columns(self):
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(companies)").fetchall()}
        for col in (
            "company_name",
            "company_type",
            "district",
            "gst_number",
            "pan_number",
            "tan_number",
            "cin_number",
            "currency",
            "financial_year",
            "timezone",
            "language",
            "company_logo",
            "modified_by",
            "is_deleted",
            "approved_by",
            "approval_status",
        ):
            self.assertIn(col, cols)


class CompanyMasterValidationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_email_validation(self):
        validate_email("info@maxek.com")
        with self.assertRaises(ValueError):
            validate_email("not-an-email")

    def test_gst_and_pan_validation(self):
        validate_gst_number("27AABCU9603R1ZM")
        validate_pan_number("AABCU9603R")
        with self.assertRaises(ValueError):
            validate_gst_number("INVALID")
        with self.assertRaises(ValueError):
            validate_pan_number("BADPAN")

    def test_unique_company_code(self):
        form = {
            "legal_name": "Alpha Builders Private Limited",
            "company_name": "Alpha Builders",
            "country": "India",
            "status": "Active",
        }
        save_company(self.conn, form, "tester")
        self.conn.commit()
        with self.assertRaises(ValueError):
            validate_company_uniqueness(
                self.conn,
                company_code="CO-2026-0001",
                legal_name="Another Co",
            )

    def test_unique_gst(self):
        self.conn.execute(
            """
            INSERT INTO companies(
                company_code, legal_name, company_name, country, status, gst_number,
                created_by, created_at, modified_by, modified_at
            ) VALUES('CO-TEST-1','Legal One','Co One','India','Active','27AABCU9603R1ZM','t','now','t','now')
            """
        )
        with self.assertRaises(ValueError):
            validate_company_uniqueness(self.conn, gst_number="27AABCU9603R1ZM", legal_name="Other")


class CompanyMasterCrudTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def _sample_form(self, **overrides):
        data = {
            "legal_name": "Beta Construction Private Limited",
            "company_name": "Beta Construction",
            "company_type": "Private Limited",
            "country": "India",
            "status": "Active",
            "email": "beta@example.com",
            "phone": "+91 9876543210",
            "website": "https://beta.example.com",
            "currency": "INR",
            "financial_year": "April-March",
            "timezone": "Asia/Kolkata",
            "language": "en",
        }
        data.update(overrides)
        return data

    def test_create_update_soft_delete_and_pagination(self):
        cid = save_company(self.conn, self._sample_form(), "creator")
        self.conn.commit()
        row = get_company(self.conn, cid)
        self.assertIsNotNone(row)
        self.assertEqual(row["company_name"], "Beta Construction")
        self.assertEqual(row["approval_status"], "Draft")

        save_company(
            self.conn,
            self._sample_form(city="Mumbai"),
            "editor",
            cid,
        )
        self.conn.commit()
        updated = get_company(self.conn, cid)
        self.assertEqual(updated["city"], "Mumbai")
        self.assertEqual(updated["modified_by"], "editor")

        approve_company(self.conn, cid, "approver")
        self.conn.commit()
        approved = get_company(self.conn, cid)
        self.assertEqual(approved["approval_status"], "Approved")
        self.assertEqual(approved["approved_by"], "approver")

        soft_delete_company(self.conn, cid, "deleter")
        self.conn.commit()
        self.assertIsNone(get_company(self.conn, cid))
        deleted = get_company(self.conn, cid, include_deleted=True)
        self.assertEqual(deleted["is_deleted"], 1)

        listing = list_companies(self.conn, search="Beta", per_page=10)
        self.assertEqual(listing["total"], 0)
        listing_deleted = list_companies(self.conn, include_deleted=True, per_page=10)
        self.assertEqual(listing_deleted["total"], 1)

    def test_export_csv(self):
        save_company(self.conn, self._sample_form(), "creator")
        self.conn.commit()
        csv_text = export_companies_csv(self.conn)
        self.assertIn("company_code", csv_text)
        self.assertIn("Beta Construction", csv_text)


class CompanyMasterImportTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_company_master_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_import_validate_and_save(self):
        rows = [
            {
                "_row_num": 2,
                "company_code": "CO-IMP-001",
                "company_name": "Import Co",
                "legal_name": "Import Company Private Limited",
                "country": "India",
                "status": "Active",
                "email": "import@example.com",
            }
        ]
        val = validate_company_import(self.conn, rows)
        self.assertTrue(val["ok"])
        result = save_company_import(self.conn, val["parsed_rows"], username="importer", filename="test.xlsx")
        self.assertEqual(result["imported"], 1)
        self.conn.commit()
        listing = list_companies(self.conn, search="Import")
        self.assertEqual(listing["total"], 1)


if __name__ == "__main__":
    unittest.main()
