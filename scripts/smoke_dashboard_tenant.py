#!/usr/bin/env python3
"""Smoke test: dashboard stats respect session customer_id tenant isolation."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)


def main() -> int:
    from app import app, get_dashboard_stats, get_db
    from super_admin_service import bootstrap_super_admin, ensure_super_admin_schema

    with app.app_context():
        db = get_db()
        ensure_super_admin_schema(db)
        bootstrap_super_admin(db, hash_password_fn=lambda p: p, include_sample_tenants=True)
        db.commit()

        global_count = db.execute("SELECT COUNT(*) AS c FROM projects").fetchone()["c"]
        tenant_row = db.execute(
            "SELECT id FROM erp_customers WHERE is_platform=0 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not tenant_row:
            print("SKIP: no non-platform tenant in database")
            return 0
        tenant_id = tenant_row["id"]
        tenant_project_count = db.execute(
            "SELECT COUNT(*) AS c FROM projects WHERE customer_id=?", (tenant_id,)
        ).fetchone()["c"]

        with app.test_request_context():
            from flask import session

            session["user_id"] = 999
            session["customer_id"] = tenant_id
            stats = get_dashboard_stats(db)
            if stats["total_projects"] != tenant_project_count:
                print(
                    f"FAIL: tenant dashboard total_projects={stats['total_projects']} "
                    f"expected {tenant_project_count} (global={global_count})"
                )
                return 1
            if global_count > tenant_project_count and stats["total_projects"] == global_count:
                print("FAIL: tenant user received global project count")
                return 1
            print(
                f"OK: tenant_id={tenant_id} dashboard projects={stats['total_projects']} "
                f"(global={global_count})"
            )

        with app.test_request_context():
            from flask import session

            session.clear()
            session["user_id"] = 1
            session["customer_id"] = None
            session["role"] = "Super Admin"
            stats_all = get_dashboard_stats(db)
            if stats_all["total_projects"] != global_count:
                print(
                    f"FAIL: platform view total_projects={stats_all['total_projects']} "
                    f"expected global {global_count}"
                )
                return 1
            print(f"OK: platform dashboard projects={stats_all['total_projects']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
