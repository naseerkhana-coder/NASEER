"""Audit log for bulk data imports."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any


def ensure_import_audit_schema(db) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS import_audit_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_key TEXT NOT NULL,
            imported_by TEXT,
            imported_at TEXT NOT NULL,
            filename TEXT,
            total_rows INTEGER DEFAULT 0,
            success_rows INTEGER DEFAULT 0,
            failed_rows INTEGER DEFAULT 0,
            customer_id INTEGER,
            notes TEXT
        )
    """)
    try:
        db.commit()
    except sqlite3.Error:
        pass


def log_import(
    db,
    *,
    module_key: str,
    imported_by: str,
    filename: str,
    total_rows: int,
    success_rows: int,
    failed_rows: int,
    customer_id: int | None = None,
    notes: str = "",
) -> int:
    ensure_import_audit_schema(db)
    imported_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "INSERT INTO import_audit_log("
        "module_key, imported_by, imported_at, filename, total_rows, "
        "success_rows, failed_rows, customer_id, notes"
        ") VALUES(?,?,?,?,?,?,?,?,?)",
        (
            module_key,
            imported_by or "",
            imported_at,
            filename or "",
            int(total_rows),
            int(success_rows),
            int(failed_rows),
            customer_id,
            notes or "",
        ),
    )
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


def list_import_audit(
    db,
    *,
    module_key: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    ensure_import_audit_schema(db)
    sql = "SELECT * FROM import_audit_log "
    params: list[Any] = []
    if module_key:
        sql += "WHERE module_key=? "
        params.append(module_key)
    sql += "ORDER BY id DESC LIMIT ?"
    params.append(int(limit))
    return [dict(r) for r in db.execute(sql, params).fetchall()]
