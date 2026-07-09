"""Tests for multi-BOQ DPR batch save — same measurements applied to all items."""

from __future__ import annotations

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import (  # noqa: E402
    _parse_dpr_measurement_payload,
    _save_one_dpr_measurement,
    app,
    get_db,
    init_db,
    prepare_dpr_page_db,
)


SHARED_MEASUREMENT = {
    "lengths": [10, 10],
    "widths": [5, 5],
    "depths": [2, 2],
}


class TestDprBatchMeasurements(unittest.TestCase):
    def test_same_payload_same_quantity_for_same_unit(self):
        """One measurement form → identical qty when BOQ units match."""
        parsed_a = _parse_dpr_measurement_payload(SHARED_MEASUREMENT, "Cum")
        parsed_b = _parse_dpr_measurement_payload(SHARED_MEASUREMENT, "Cum")
        self.assertEqual(parsed_a["quantity"], parsed_b["quantity"])
        self.assertGreater(parsed_a["quantity"], 0)
        self.assertEqual(parsed_a["data"]["avg_length"], 10.0)

    def test_batch_save_creates_multiple_records_with_identical_measurements(self):
        """Batch save duplicates measurement_data to each selected BOQ item."""
        with app.app_context():
            init_db()
            db = get_db()
            prepare_dpr_page_db(db)

            project = db.execute("SELECT id FROM projects LIMIT 1").fetchone()
            if not project:
                db.execute(
                    "INSERT INTO projects(project_code, project_name, approval_status) VALUES(?, ?, ?)",
                    ("DPR-BATCH", "DPR Batch Test Project", "Approved"),
                )
                db.commit()
                project = db.execute("SELECT id FROM projects LIMIT 1").fetchone()
            self.assertIsNotNone(project, "Need at least one project in test DB")
            project_id = project[0]

            db.execute(
                """
                INSERT INTO boq_master(project_id, boq_number, total_amount, line_count, approval_status, is_deleted)
                VALUES (?, 'B-MULTI', 0, 2, 'Approved', 0)
                """,
                (project_id,),
            )
            boq_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute(
                """
                INSERT INTO boq_items(boq_id, project_id, line_no, item_code, item_description, unit, quantity, rate)
                VALUES (?, ?, 1, 'L1', 'Item A', 'Cum', 100, 500),
                       (?, ?, 2, 'L2', 'Item B', 'Cum', 80, 600)
                """,
                (boq_id, project_id, boq_id, project_id),
            )
            db.commit()
            rows = db.execute(
                "SELECT id, item_description, unit FROM boq_items WHERE boq_id=? ORDER BY line_no",
                (boq_id,),
            ).fetchall()
            self.assertEqual(len(rows), 2)

            parsed = _parse_dpr_measurement_payload(SHARED_MEASUREMENT, "Cum")
            created_at = "2026-07-07 12:00:00"
            saved_ids = []

            for row in rows:
                result = _save_one_dpr_measurement(
                    db,
                    project_id=str(project_id),
                    report_date="2026-07-07",
                    boq_item_id=row[0],
                    boq_number="B-MULTI",
                    boq_description=row[1],
                    unit=row[2],
                    work_description="Shared excavation work",
                    bill_client=0,
                    for_costing=1,
                    measurement_store=dict(parsed["data"]),
                    parsed=parsed,
                    manpower_rows=[],
                    dpr_status="draft",
                    created_by="test",
                    created_at=created_at,
                )
                self.assertIsNotNone(result)
                saved_ids.append(result["id"])

            db.commit()
            self.assertEqual(len(saved_ids), 2)

            measurements = db.execute(
                "SELECT calculated_quantity, measurement_data, work_description, boq_item_id "
                "FROM dpr_measurements WHERE id IN (?, ?) ORDER BY boq_item_id",
                saved_ids,
            ).fetchall()

            self.assertEqual(measurements[0][0], measurements[1][0])
            self.assertEqual(measurements[0][1], measurements[1][1])
            self.assertEqual(measurements[0][2], "Shared excavation work")

            data_a = json.loads(measurements[0][1])
            data_b = json.loads(measurements[1][1])
            self.assertEqual(data_a["avg_length"], data_b["avg_length"])
            self.assertEqual(data_a["avg_width"], data_b["avg_width"])
            self.assertEqual(data_a["avg_depth"], data_b["avg_depth"])


if __name__ == "__main__":
    unittest.main()
