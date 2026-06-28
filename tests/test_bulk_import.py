"""Tests for bulk import — BOQ validate minimum."""

import sqlite3
import unittest

from boq_import_service import validate_boq_import
from bulk_import_service import validate_duplicates, validate_gst
from import_audit_service import ensure_import_audit_schema, log_import
from standard_boq_library_service import ensure_standard_boq_library_schema, save_standard_boq_item


def _memory_db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE projects(id INTEGER PRIMARY KEY, project_code TEXT, project_name TEXT)")
    db.execute("INSERT INTO projects(id, project_code, project_name) VALUES(1, 'PRJ-001', 'Test Project')")
    db.execute("""
        CREATE TABLE boq_master(
            id INTEGER PRIMARY KEY AUTOINCREMENT, boq_number TEXT, project_id INTEGER,
            total_amount REAL, line_count INTEGER, created_by TEXT, approval_status TEXT, created_at TEXT,
            is_deleted INTEGER DEFAULT 0
        )
    """)
    db.execute("""
        CREATE TABLE boq_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT, boq_id INTEGER, line_no INTEGER, item_code TEXT,
            project_id INTEGER, item_description TEXT, quantity REAL, unit TEXT, rate REAL, amount REAL,
            remarks TEXT, created_by TEXT, created_at TEXT, approval_status TEXT, is_deleted INTEGER DEFAULT 0
        )
    """)
    db.execute("""
        CREATE TABLE approval_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT, module_id TEXT, record_id INTEGER,
            table_name TEXT, created_by TEXT, status TEXT
        )
    """)
    ensure_standard_boq_library_schema(db)
    ensure_import_audit_schema(db)
    save_standard_boq_item(
        db,
        {
            "boq_code": "EWC-001",
            "description": "Earth work",
            "unit": "Cum",
            "standard_rate": "450",
        },
        item_id=None,
        username="tester",
    )
    db.commit()
    return db


def _boq_row(**kwargs):
    base = {
        "_row_num": 2,
        "item_no": "1",
        "boq_code": "",
        "description": "",
        "specification": "",
        "unit": "Cum",
        "quantity": "10",
        "rate": "100",
        "amount": "1000",
        "remarks": "",
    }
    base.update(kwargs)
    return base


BOQ_UNITS = ["Nos", "Sqm", "Cum", "MT", "Rmt"]


class TestBulkImportFramework(unittest.TestCase):
    def test_gst_validator_rejects_invalid(self):
        errors = validate_gst("INVALID", "GSTIN", 2)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["column"], "GSTIN")

    def test_duplicate_detection(self):
        rows = [
            {"_row_num": 2, "code": "A1"},
            {"_row_num": 3, "code": "A1"},
        ]
        errors = validate_duplicates(rows, "code", "Code")
        self.assertTrue(any("Duplicate" in e["error"] for e in errors))


class TestBoqImportValidate(unittest.TestCase):
    def test_valid_boq_rows_pass(self):
        db = _memory_db()
        rows = [
            _boq_row(
                boq_code="EWC-001",
                description="Earth work in excavation",
                specification="Ordinary soil",
                quantity="100",
                rate="450",
                amount="45000",
            )
        ]
        result = validate_boq_import(db, rows, boq_units=BOQ_UNITS, project_id=1)
        self.assertTrue(result["ok"])
        self.assertEqual(result["total_rows"], 1)

    def test_missing_description_fails(self):
        db = _memory_db()
        rows = [_boq_row(description="", boq_code="")]
        result = validate_boq_import(db, rows, boq_units=BOQ_UNITS, project_id=1)
        self.assertFalse(result["ok"])
        self.assertTrue(len(result["errors"]) >= 1)

    def test_unknown_boq_code_fails(self):
        db = _memory_db()
        rows = [_boq_row(boq_code="MISSING-99", description="Some work")]
        result = validate_boq_import(db, rows, boq_units=BOQ_UNITS, project_id=1)
        self.assertFalse(result["ok"])
        self.assertTrue(any(e["column"] == "BOQ Code" for e in result["errors"]))

    def test_amount_mismatch_fails(self):
        db = _memory_db()
        rows = [_boq_row(boq_code="EWC-001", description="Earth work", amount="9999")]
        result = validate_boq_import(db, rows, boq_units=BOQ_UNITS, project_id=1)
        self.assertFalse(result["ok"])
        self.assertTrue(any(e["column"] == "Amount" for e in result["errors"]))


class TestImportAudit(unittest.TestCase):
    def test_log_import_writes_row(self):
        db = _memory_db()
        log_import(
            db,
            module_key="boq",
            imported_by="admin",
            filename="test.xlsx",
            total_rows=5,
            success_rows=5,
            failed_rows=0,
        )
        db.commit()
        row = db.execute("SELECT * FROM import_audit_log").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["success_rows"], 5)


if __name__ == "__main__":
    unittest.main()
