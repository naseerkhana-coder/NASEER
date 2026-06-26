#!/usr/bin/env python3
"""Manual Super Admin platform seed for VPS — schema + idempotent bootstrap."""
from __future__ import annotations

import os
import sqlite3
import sys

import bcrypt

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

DB_PATH = os.path.join(ROOT, "database", "maxek.db")

from super_admin_service import bootstrap_super_admin  # noqa: E402


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(
        plain_password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


def _print_report(report: dict[str, list[str]]) -> None:
    created = report.get("created") or []
    skipped = report.get("skipped") or []
    errors = report.get("errors") or []
    print("")
    print("Super Admin seed complete.")
    print(f"Database: {DB_PATH}")
    if created:
        print(f"Created ({len(created)}):")
        for item in created:
            print(f"  + {item}")
    if skipped:
        print(f"Skipped ({len(skipped)}):")
        for item in skipped:
            print(f"  = {item}")
    if errors:
        print(f"Errors ({len(errors)}):")
        for item in errors:
            print(f"  ! {item}")
    if not created and not skipped and not errors:
        print("No changes reported.")


def main() -> int:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    try:
        report = bootstrap_super_admin(
            db,
            hash_password_fn=hash_password,
            include_sample_tenants=True,
        )
        db.commit()
    finally:
        db.close()
    _print_report(report)
    if report.get("errors"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
