"""Verify attendance list resolves worker names for staff and subcontractor workers."""

import sqlite3
import unittest

from attendance_service import list_daily_attendance_records


def _make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE workers(
            id INTEGER PRIMARY KEY,
            worker_code TEXT,
            worker_name TEXT,
            designation TEXT,
            worker_category TEXT,
            subcontractor_id INTEGER,
            status TEXT
        );
        CREATE TABLE staff(
            id INTEGER PRIMARY KEY,
            employee_code TEXT,
            staff_name TEXT,
            designation TEXT,
            designation_id INTEGER,
            status TEXT
        );
        CREATE TABLE designations(
            id INTEGER PRIMARY KEY,
            designation_name TEXT,
            status TEXT
        );
        CREATE TABLE trades(
            id INTEGER PRIMARY KEY,
            trade_name TEXT,
            status TEXT
        );
        CREATE TABLE projects(
            id INTEGER PRIMARY KEY,
            project_code TEXT,
            project_name TEXT
        );
        CREATE TABLE attendance(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER,
            worker_source TEXT DEFAULT 'worker',
            project_id INTEGER,
            attendance_date TEXT,
            in_time TEXT,
            out_time TEXT,
            break_hours REAL,
            total_hours REAL,
            ot_hours REAL,
            status TEXT,
            approval_status TEXT,
            trade_id INTEGER,
            designation_id INTEGER
        );
        INSERT INTO workers VALUES
            (1, 'W-001', 'Sub Worker One', 'Mason', 'Sub Contractor Staff', 10, 'Active'),
            (2, 'W-002', '', 'Helper', 'Company Staff', NULL, 'Active');
        INSERT INTO staff VALUES
            (5, 'E-005', 'Company Staff Five', 'Supervisor', NULL, 'Active');
        INSERT INTO designations VALUES (1, 'Site Engineer', 'Active');
        INSERT INTO projects VALUES (1, 'PRJ-01', 'Tower A');
        INSERT INTO attendance(
            worker_id, worker_source, project_id, attendance_date,
            in_time, out_time, break_hours, total_hours, ot_hours, status
        ) VALUES
            (1, 'worker', 1, '2026-06-01', '08:00', '17:00', 1, 8, 0, 'Present'),
            (5, 'staff', 1, '2026-06-01', '09:00', '18:00', 1, 8, 0, 'Present'),
            (5, 'worker', 1, '2026-06-02', '09:00', '18:00', 1, 8, 0, 'Present');
        """
    )
    return conn


class AttendanceWorkerNameLookupTests(unittest.TestCase):
    def test_resolves_subcontractor_and_staff_names(self):
        db = _make_db()
        rows = list_daily_attendance_records(db)
        by_date_source = {
            (row["attendance_date"], row.get("worker_source")): row for row in rows
        }
        sub_row = by_date_source[("2026-06-01", "worker")]
        self.assertEqual(sub_row["worker_name"], "Sub Worker One")
        self.assertEqual(sub_row["worker_code"], "W-001")
        self.assertEqual(sub_row["designation"], "Mason")

        staff_row = by_date_source[("2026-06-01", "staff")]
        self.assertEqual(staff_row["worker_name"], "Company Staff Five")
        self.assertEqual(staff_row["worker_code"], "E-005")

    def test_legacy_mis_tagged_staff_falls_back_to_staff_name(self):
        db = _make_db()
        rows = list_daily_attendance_records(db)
        legacy = next(row for row in rows if row["attendance_date"] == "2026-06-02")
        self.assertEqual(legacy["worker_name"], "Company Staff Five")
        self.assertEqual(legacy["worker_code"], "E-005")


if __name__ == "__main__":
    unittest.main()
