"""Tests for subcontractor worker monthly timesheet save."""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from werkzeug.datastructures import MultiDict

from employee_timesheet_service import ensure_employee_timesheet_schema, save_monthly_timesheet


def test_worker_timesheet_save_after_schema_ensure_on_legacy_workers():
    tmp = tempfile.mkdtemp()
    conn = sqlite3.connect(os.path.join(tmp, "legacy.db"))
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE subcontractors(id INTEGER PRIMARY KEY, subcontractor_name TEXT)"
    )
    conn.execute(
        """
        CREATE TABLE workers(
            id INTEGER PRIMARY KEY,
            worker_code TEXT,
            worker_name TEXT,
            designation TEXT,
            subcontractor_id INTEGER,
            status TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO subcontractors(subcontractor_name) VALUES('Legacy Sub')"
    )
    conn.execute(
        "INSERT INTO workers(worker_code, worker_name, designation, subcontractor_id, status) "
        "VALUES('LW1','Legacy Worker','Mason',1,'Active')"
    )
    conn.commit()

    ensure_employee_timesheet_schema(conn)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(workers)").fetchall()}
    assert "project_id" in cols

    form = MultiDict(
        [
            ("employee_source", "worker"),
            ("employee_id", "1"),
            ("year_month", "2026-06"),
        ]
    )
    ts_id = save_monthly_timesheet(conn, form, "tester", None)
    conn.commit()
    assert ts_id > 0
    row = conn.execute(
        "SELECT employee_source, worker_id FROM employee_monthly_timesheets WHERE id=?",
        (ts_id,),
    ).fetchone()
    assert row["employee_source"] == "worker"
    assert row["worker_id"] == 1
