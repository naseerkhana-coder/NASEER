"""Audit log for bulk data imports with minimal rollback support."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any


IMPORT_STATUS_COMPLETED = "completed"
IMPORT_STATUS_ROLLED_BACK = "rolled_back"


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
            notes TEXT,
            status TEXT DEFAULT 'completed',
            rollback_payload TEXT
        )
    """)
    columns = {
        row[1] for row in db.execute("PRAGMA table_info(import_audit_log)").fetchall()
    }
    if "status" not in columns:
        db.execute(
            "ALTER TABLE import_audit_log ADD COLUMN status TEXT DEFAULT 'completed'",
        )
    if "rollback_payload" not in columns:
        db.execute("ALTER TABLE import_audit_log ADD COLUMN rollback_payload TEXT")
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
    rollback_payload: dict[str, Any] | None = None,
) -> int:
    ensure_import_audit_schema(db)
    imported_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload_json = json.dumps(rollback_payload) if rollback_payload else None
    db.execute(
        "INSERT INTO import_audit_log("
        "module_key, imported_by, imported_at, filename, total_rows, "
        "success_rows, failed_rows, customer_id, notes, status, rollback_payload"
        ") VALUES(?,?,?,?,?,?,?,?,?,?,?)",
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
            IMPORT_STATUS_COMPLETED,
            payload_json,
        ),
    )
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


def get_import_audit(db, audit_id: int) -> dict[str, Any] | None:
    ensure_import_audit_schema(db)
    row = db.execute("SELECT * FROM import_audit_log WHERE id=?", (int(audit_id),)).fetchone()
    return dict(row) if row else None


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


def _parse_payload(entry: dict[str, Any]) -> dict[str, Any] | None:
    raw = entry.get("rollback_payload")
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(str(raw))
    except (json.JSONDecodeError, TypeError):
        return None


def rollback_import(db, audit_id: int, *, rolled_back_by: str = "") -> dict[str, Any]:
    """Undo a completed import when rollback_payload was recorded at save time."""
    entry = get_import_audit(db, audit_id)
    if not entry:
        raise ValueError("Import audit record not found.")
    if entry.get("status") == IMPORT_STATUS_ROLLED_BACK:
        raise ValueError("This import has already been rolled back.")
    if int(entry.get("success_rows") or 0) <= 0:
        raise ValueError("Nothing to roll back — import had no successful rows.")

    payload = _parse_payload(entry)
    if not payload:
        raise ValueError(
            "Rollback is not available for this import (no rollback payload recorded).",
        )

    module_key = str(entry.get("module_key") or payload.get("module_key") or "")
    removed = 0

    if module_key == "customers":
        for record in payload.get("records", []):
            if record.get("table") == "clients" and record.get("id"):
                db.execute("DELETE FROM clients WHERE id=?", (int(record["id"]),))
                removed += 1
    elif module_key == "vendors":
        for record in payload.get("records", []):
            if record.get("table") == "vendors" and record.get("id"):
                db.execute("DELETE FROM vendors WHERE id=?", (int(record["id"]),))
                removed += 1
    elif module_key == "boq":
        boq_id = payload.get("boq_id")
        if boq_id:
            db.execute("DELETE FROM boq_items WHERE boq_id=?", (int(boq_id),))
            db.execute(
                "DELETE FROM approval_requests WHERE module_id=? AND record_id=?",
                ("boq", int(boq_id)),
            )
            master_cols = {
                row[1] for row in db.execute("PRAGMA table_info(boq_master)").fetchall()
            }
            if "is_deleted" in master_cols:
                db.execute(
                    "UPDATE boq_master SET is_deleted=1 WHERE id=?",
                    (int(boq_id),),
                )
            else:
                db.execute("DELETE FROM boq_master WHERE id=?", (int(boq_id),))
            removed = 1
    else:
        raise ValueError(f"Rollback is not implemented for module: {module_key}")

    note = f"Rolled back by {rolled_back_by or 'system'}; removed {removed} record group(s)."
    db.execute(
        "UPDATE import_audit_log SET status=?, notes=? WHERE id=?",
        (IMPORT_STATUS_ROLLED_BACK, note, int(audit_id)),
    )
    return {
        "ok": True,
        "audit_id": audit_id,
        "module_key": module_key,
        "removed": removed,
        "message": note,
    }
