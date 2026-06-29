#!/usr/bin/env python3
"""Smoke test: workflow approval visibility + tenant-scoped dashboard cards."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, get_db, init_db
from tenant_isolation import backfill_projects_tenant_scope
from workflow_service import (
    STATUS_APPROVED,
    STATUS_PENDING_CHECKER,
    RECORD_APPROVED,
    RECORD_PENDING_CHECKER,
    advance_approval,
    create_approval_request,
    get_pending_counts,
    get_workflow_dashboard_cards,
    get_approval_summary,
)


def _ensure_demo_tenant(db) -> int | None:
    """Assign demo workflow users to a tenant when customer_id is unset."""
    tables = {
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if "erp_customers" not in tables:
        return None
    row = db.execute(
        "SELECT id FROM erp_customers WHERE COALESCE(is_platform, 0)=0 "
        "ORDER BY id LIMIT 1"
    ).fetchone()
    if row:
        customer_id = row["id"]
    else:
        db.execute(
            "INSERT INTO erp_customers(customer_code, customer_name, status, plan) "
            "VALUES(?,?,?,?)",
            ("DEMO001", "Demo Tenant", "Active", "Standard"),
        )
        customer_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    for username in ("maker1", "checker1", "approver1"):
        db.execute(
            "UPDATE users SET customer_id=? WHERE username=? AND "
            "(customer_id IS NULL OR customer_id='')",
            (customer_id, username),
        )
    return customer_id


def run() -> int:
    failures = []
    with app.app_context():
        init_db()
        db = get_db()
        _ensure_demo_tenant(db)
        backfill_projects_tenant_scope(db)
        db.commit()

        maker = db.execute("SELECT id, username, customer_id FROM users WHERE username='maker1'").fetchone()
        checker = db.execute("SELECT id, username, customer_id, workflow_role FROM users WHERE username='checker1'").fetchone()
        approver = db.execute("SELECT id, username, workflow_role FROM users WHERE username='approver1'").fetchone()
        if not (maker and checker and approver):
            print("SKIP: demo users not seeded")
            return 0

        customer_id = maker["customer_id"]
        db.execute(
            "INSERT INTO projects(project_name, location, start_date, status, budget, "
            "created_by, customer_id, approval_status) VALUES(?,?,?,?,?,?,?,?)",
            ("Smoke WF Project", "Site A", "2026-06-01", "Active", 100000,
             maker["username"], customer_id, RECORD_PENDING_CHECKER),
        )
        pid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        create_approval_request(
            db, "project_creation", pid, "projects", maker["username"], maker["id"]
        )
        db.commit()

        row = db.execute("SELECT customer_id, approval_status, status FROM projects WHERE id=?", (pid,)).fetchone()
        if not row["customer_id"]:
            failures.append("project missing customer_id after create")
        req = db.execute(
            "SELECT id FROM approval_requests WHERE record_table='projects' AND record_id=?",
            (pid,),
        ).fetchone()

        ok, _ = advance_approval(db, req["id"], checker["id"], "verify", "ok", False)
        if not ok:
            failures.append("checker verify failed")
        db.commit()

        ok, _ = advance_approval(db, req["id"], approver["id"], "approve", "ok", False)
        if not ok:
            failures.append("approver approve failed")
        db.commit()

        row = db.execute(
            "SELECT approval_status, status, customer_id FROM projects WHERE id=?", (pid,)
        ).fetchone()
        if row["approval_status"] != RECORD_APPROVED:
            failures.append(f"approval_status={row['approval_status']}")
        if row["status"] != "Active":
            failures.append(f"status={row['status']}")
        if not row["customer_id"]:
            failures.append("customer_id lost after approval")

        visible = db.execute(
            "SELECT COUNT(*) AS c FROM projects WHERE id=? AND customer_id=?",
            (pid, customer_id),
        ).fetchone()["c"]
        if visible != 1:
            failures.append("project not visible under tenant filter")

        checker_counts = get_pending_counts(
            db, checker["id"], False, customer_id=customer_id, workflow_role="Checker"
        )
        if "checker" not in checker_counts:
            failures.append("checker pending counts missing")

        checker_cards = get_workflow_dashboard_cards(
            db, checker["id"], "checker", False, customer_id=customer_id, workflow_role="Checker"
        )
        if not isinstance(checker_cards, list):
            failures.append("checker cards not a list")

        summary = get_approval_summary(db, customer_id=customer_id)
        if "pending_checker" not in summary:
            failures.append("approval summary missing pending_checker")

        db.execute("DELETE FROM approval_requests WHERE record_table='projects' AND record_id=?", (pid,))
        db.execute("DELETE FROM projects WHERE id=?", (pid,))
        db.commit()

    if failures:
        print("FAIL:", "; ".join(failures))
        return 1
    print("OK: workflow tenant smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
