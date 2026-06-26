#!/usr/bin/env python3
"""Dry-run user/branch/storage limits against a SQLite DB (local or VPS path).

Usage:
  python scripts/test_user_limits.py
  python scripts/test_user_limits.py /var/www/maxek-erp-flask/database/maxek.db
  python scripts/test_user_limits.py --legacy-sim
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import tempfile
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from super_admin_service import (  # noqa: E402
    backfill_customer_limit_rows,
    ensure_super_admin_schema,
    list_branch_limits,
    list_storage_limits,
    list_user_limits,
    sync_customer_usage_counts,
)


def _default_db_path() -> str:
    return os.path.join(ROOT, "database", "maxek.db")


def _connect(db_path: str) -> sqlite3.Connection:
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    return db


def _run_limits_check(db: sqlite3.Connection, label: str) -> bool:
    print(f"\n=== {label} ===")
    try:
        ensure_super_admin_schema(db)
        backfill_customer_limit_rows(db)
        db.commit()

        user_rows = list_user_limits(db)
        print(f"list_user_limits: {len(user_rows)} row(s)")
        for row in user_rows:
            sync_customer_usage_counts(db, int(row["customer_id"]))
        db.commit()
        user_rows = list_user_limits(db)
        if user_rows:
            sample = user_rows[0]
            print(
                "  sample:",
                sample.get("customer_code"),
                sample.get("users_allowed"),
                sample.get("current_users"),
            )

        branch_rows = list_branch_limits(db)
        print(f"list_branch_limits: {len(branch_rows)} row(s)")

        storage_rows = list_storage_limits(db)
        print(f"list_storage_limits: {len(storage_rows)} row(s)")

        print("OK")
        return True
    except Exception as exc:
        print(f"FAILED: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return False


def _build_legacy_sim_db() -> str:
    fd, path = tempfile.mkstemp(prefix="maxek_limits_legacy_", suffix=".db")
    os.close(fd)
    db = _connect(path)
    db.execute(
        "CREATE TABLE users("
        "id INTEGER PRIMARY KEY, username TEXT, password TEXT, role TEXT, status TEXT)"
    )
    db.execute(
        "CREATE TABLE erp_customers("
        "id INTEGER PRIMARY KEY, customer_code TEXT, company_name TEXT)"
    )
    db.execute(
        "INSERT INTO erp_customers(customer_code, company_name) VALUES('TRD001','Legacy Test Co')"
    )
    db.execute(
        "CREATE TABLE erp_user_limits("
        "id INTEGER PRIMARY KEY, customer_id INTEGER, users_allowed INTEGER)"
    )
    db.execute("INSERT INTO erp_user_limits(customer_id, users_allowed) VALUES(1, 10)")
    db.commit()
    db.close()
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run ERP limits screens")
    parser.add_argument(
        "db_path",
        nargs="?",
        default=_default_db_path(),
        help="SQLite database path (default: database/maxek.db)",
    )
    parser.add_argument(
        "--legacy-sim",
        action="store_true",
        help="Run against a temporary legacy-schema DB instead of db_path",
    )
    args = parser.parse_args()

    legacy_path: str | None = None
    db_path = args.db_path
    if args.legacy_sim:
        legacy_path = _build_legacy_sim_db()
        db_path = legacy_path
        print(f"Legacy simulation DB: {db_path}")

    if not os.path.isfile(db_path):
        print(f"Database not found: {db_path}")
        return 1

    db = _connect(db_path)
    try:
        ok = _run_limits_check(db, os.path.basename(db_path))
    finally:
        db.close()
        if legacy_path:
            os.unlink(legacy_path)

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
