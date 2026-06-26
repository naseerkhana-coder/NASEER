#!/usr/bin/env python3
"""One-shot VPS migration for Petty Cash FRS schema.

Run from the MAXEK_ERP project root after uploading app.py:

    python3 deploy/migrate_petty_cash_frs.py

Then restart the app service (gunicorn/uwsgi/systemd).
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
os.environ.setdefault("MAXEK_SKIP_DEMO_SEED", "1")

import app as app_module  # noqa: E402


def main() -> None:
    with app_module.app.app_context():
        db = app_module.get_db()
        app_module.ensure_petty_cash_tables(db)
        print("Petty cash FRS tables and columns are up to date.")


if __name__ == "__main__":
    main()
