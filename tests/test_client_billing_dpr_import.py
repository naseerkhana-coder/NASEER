"""Tests for client billing DPR measurement import."""

import sqlite3
import unittest

from client_billing_service import (
    ensure_client_billing_schema,
    import_dpr_for_billing,
    list_dpr_measurement_sheet_rows,
)


def _memory_db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE projects(id INTEGER PRIMARY KEY, project_name TEXT)")
    db.execute("INSERT INTO projects(id, project_name) VALUES(1, 'Test Project')")
    db.execute("""
        CREATE TABLE boq_items(
            id INTEGER PRIMARY KEY, project_id INTEGER, item_code TEXT,
            item_description TEXT, quantity REAL, unit TEXT, rate REAL, is_deleted INTEGER DEFAULT 0
        )
    """)
    db.execute(
        "INSERT INTO boq_items(id, project_id, item_code, item_description, quantity, unit, rate) "
        "VALUES(10, 1, 'BOQ-1', 'Earth work', 100, 'Cum', 500)"
    )
    db.execute("""
        CREATE TABLE dpr_measurements(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, report_date TEXT, boq_item_id INTEGER,
            boq_number TEXT, boq_description TEXT, unit TEXT,
            calculated_quantity REAL, measurement_type TEXT, measurement_data TEXT,
            bill_client INTEGER DEFAULT 0, billing_status TEXT DEFAULT 'none',
            dpr_status TEXT DEFAULT 'submitted'
        )
    """)
    ensure_client_billing_schema(db)
    return db


class TestImportDprMeasurements(unittest.TestCase):
    def test_pending_bill_client_rows_imported(self):
        db = _memory_db()
        db.execute(
            "INSERT INTO dpr_measurements(project_id, report_date, boq_item_id, boq_number, "
            "boq_description, unit, calculated_quantity, bill_client, billing_status) "
            "VALUES(1, '2026-06-01', 10, 'BOQ-1', 'Earth work', 'Cum', 5, 1, 'pending')"
        )
        db.commit()
        result = import_dpr_for_billing(db, 1, "2026-06-01", "2026-06-30")
        self.assertEqual(len(result["measurements"]), 1)
        self.assertEqual(len(result["lines"]), 1)
        self.assertEqual(result["lines"][0]["executed_qty"], 5.0)

    def test_non_pending_billing_status_excluded(self):
        db = _memory_db()
        db.execute(
            "INSERT INTO dpr_measurements(project_id, report_date, boq_item_id, boq_number, "
            "boq_description, unit, calculated_quantity, bill_client, billing_status) "
            "VALUES(1, '2026-06-01', 10, 'BOQ-1', 'Earth work', 'Cum', 5, 1, 'none')"
        )
        db.commit()
        rows = list_dpr_measurement_sheet_rows(db, 1, "2026-06-01", "2026-06-30")
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
