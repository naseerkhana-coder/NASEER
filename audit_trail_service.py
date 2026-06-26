"""Audit trail columns, change log, and soft-delete helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

AUDIT_COLUMNS = (
    ("created_by", "TEXT"),
    ("created_at", "TEXT"),
    ("modified_by", "TEXT"),
    ("modified_at", "TEXT"),
    ("approved_by", "TEXT"),
    ("approved_at", "TEXT"),
    ("rejected_by", "TEXT"),
    ("rejected_at", "TEXT"),
    ("is_deleted", "INTEGER DEFAULT 0"),
    ("deleted_by", "TEXT"),
    ("deleted_at", "TEXT"),
)

TRANSACTION_TABLES = (
    "material_requests",
    "purchase_requests",
    "purchase_orders",
    "store_receipts",
    "store_issues",
    "material_transfers",
    "payroll_records",
    "petty_cash_requests",
    "account_expenses",
    "payment_vouchers",
    "receipt_vouchers",
    "account_transactions",
    "project_expenses",
    "head_office_expenses",
    "leave_requests",
    "subcontract_requests",
    "boq_master",
    "dpr_entries",
    "client_billing_register",
)


def _table_exists(db, table: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _column_exists(db, table: str, column: str) -> bool:
    if not _table_exists(db, table):
        return False
    cols = [r[1] for r in db.execute(f"PRAGMA table_info({table})").fetchall()]
    return column in cols


def ensure_audit_schema(db) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS erp_record_audit(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_table TEXT NOT NULL,
            record_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            field_name TEXT,
            old_value TEXT,
            new_value TEXT,
            changed_by TEXT,
            changed_at TEXT NOT NULL,
            remarks TEXT
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_erp_record_audit_lookup "
        "ON erp_record_audit(record_table, record_id, changed_at)"
    )
    for table in TRANSACTION_TABLES:
        if not _table_exists(db, table):
            continue
        for col, ctype in AUDIT_COLUMNS:
            if not _column_exists(db, table, col):
                db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ctype}")


def stamp_created(db, table: str, record_id: int, username: str) -> None:
    if not _table_exists(db, table):
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sets = []
    params: list[Any] = []
    if _column_exists(db, table, "created_by"):
        sets.append("created_by=?")
        params.append(username)
    if _column_exists(db, table, "created_at"):
        sets.append("created_at=?")
        params.append(now)
    if not sets:
        return
    params.append(record_id)
    db.execute(f"UPDATE {table} SET {', '.join(sets)} WHERE id=?", tuple(params))


def stamp_modified(db, table: str, record_id: int, username: str) -> None:
    if not _table_exists(db, table):
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sets = []
    params: list[Any] = []
    if _column_exists(db, table, "modified_by"):
        sets.append("modified_by=?")
        params.append(username)
    if _column_exists(db, table, "modified_at"):
        sets.append("modified_at=?")
        params.append(now)
    if not sets:
        return
    params.append(record_id)
    db.execute(f"UPDATE {table} SET {', '.join(sets)} WHERE id=?", tuple(params))


def stamp_approval(
    db,
    table: str,
    record_id: int,
    *,
    approved: bool,
    username: str,
) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if approved:
        if _column_exists(db, table, "approved_by"):
            db.execute(
                f"UPDATE {table} SET approved_by=?, approved_at=? WHERE id=?",
                (username, now, record_id),
            )
    else:
        if _column_exists(db, table, "rejected_by"):
            db.execute(
                f"UPDATE {table} SET rejected_by=?, rejected_at=? WHERE id=?",
                (username, now, record_id),
            )


def log_audit_event(
    db,
    *,
    record_table: str,
    record_id: int,
    action: str,
    changed_by: str,
    field_name: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
    remarks: str | None = None,
) -> None:
    ensure_audit_schema(db)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        """
        INSERT INTO erp_record_audit(
            record_table, record_id, action, field_name, old_value, new_value,
            changed_by, changed_at, remarks
        ) VALUES(?,?,?,?,?,?,?,?,?)
        """,
        (
            record_table,
            int(record_id),
            action,
            field_name,
            old_value,
            new_value,
            changed_by,
            now,
            remarks,
        ),
    )


def soft_delete_record(db, table: str, record_id: int, username: str) -> bool:
    if not _table_exists(db, table):
        return False
    ensure_audit_schema(db)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if _column_exists(db, table, "is_deleted"):
        db.execute(
            f"UPDATE {table} SET is_deleted=1, deleted_by=?, deleted_at=? WHERE id=?",
            (username, now, record_id),
        )
    else:
        return False
    log_audit_event(
        db,
        record_table=table,
        record_id=record_id,
        action="soft_delete",
        changed_by=username,
        remarks="Record marked deleted (not purged)",
    )
    db.commit()
    return True


def list_audit_trail(db, record_table: str, record_id: int, limit: int = 50) -> list[dict[str, Any]]:
    ensure_audit_schema(db)
    rows = db.execute(
        """
        SELECT * FROM erp_record_audit
        WHERE record_table=? AND record_id=?
        ORDER BY changed_at DESC, id DESC
        LIMIT ?
        """,
        (record_table, int(record_id), limit),
    ).fetchall()
    return [dict(r) for r in rows]
