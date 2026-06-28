"""Standard BOQ Library — reusable item catalogue for BOQ creation."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any


def _ensure_column(db, table: str, column: str, col_type: str) -> None:
    cols = {r[1] for r in db.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def ensure_standard_boq_library_schema(db) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS standard_boq_library(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            boq_code TEXT NOT NULL,
            item_number TEXT,
            description TEXT NOT NULL,
            detailed_specification TEXT,
            unit TEXT,
            category TEXT,
            sub_category TEXT,
            standard_rate REAL DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_by TEXT,
            created_at TEXT,
            modified_by TEXT,
            modified_at TEXT
        )
    """)
    db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_standard_boq_library_code "
        "ON standard_boq_library(boq_code)"
    )
    _ensure_column(db, "boq_items", "detailed_specification", "TEXT")
    _ensure_column(db, "boq_items", "library_item_id", "INTEGER")
    _ensure_column(db, "boq_items", "boq_code", "TEXT")
    try:
        db.commit()
    except sqlite3.Error:
        pass


def list_standard_boq_library(
    db,
    *,
    search: str = "",
    category: str = "",
    active_only: bool = True,
) -> list[dict[str, Any]]:
    ensure_standard_boq_library_schema(db)
    sql = "SELECT * FROM standard_boq_library WHERE 1=1"
    params: list[Any] = []
    if active_only:
        sql += " AND COALESCE(is_active, 1)=1"
    if search:
        sql += " AND (boq_code LIKE ? OR description LIKE ? OR item_number LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like])
    if category:
        sql += " AND category=?"
        params.append(category)
    sql += " ORDER BY category, sub_category, boq_code, item_number"
    return [dict(r) for r in db.execute(sql, params).fetchall()]


def get_standard_boq_item(db, item_id: int) -> dict[str, Any] | None:
    ensure_standard_boq_library_schema(db)
    row = db.execute(
        "SELECT * FROM standard_boq_library WHERE id=?",
        (item_id,),
    ).fetchone()
    return dict(row) if row else None


def save_standard_boq_item(
    db,
    form_data: dict[str, Any],
    *,
    item_id: int | None,
    username: str,
) -> int:
    ensure_standard_boq_library_schema(db)
    boq_code = str(form_data.get("boq_code") or "").strip().upper()
    description = str(form_data.get("description") or "").strip()
    if not boq_code:
        raise ValueError("BOQ Code is required.")
    if not description:
        raise ValueError("Description is required.")

    item_number = str(form_data.get("item_number") or "").strip()
    detailed_specification = str(form_data.get("detailed_specification") or "").strip()
    unit = str(form_data.get("unit") or "Nos").strip() or "Nos"
    category = str(form_data.get("category") or "").strip()
    sub_category = str(form_data.get("sub_category") or "").strip()
    try:
        standard_rate = float(form_data.get("standard_rate") or 0)
    except (TypeError, ValueError):
        raise ValueError("Standard rate must be a number.") from None
    is_active = 1 if str(form_data.get("is_active", "1")).strip() in ("1", "true", "on") else 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    dup = db.execute(
        "SELECT id FROM standard_boq_library WHERE boq_code=? AND id!=?",
        (boq_code, item_id or 0),
    ).fetchone()
    if dup:
        raise ValueError(f"BOQ Code {boq_code} already exists.")

    if item_id:
        db.execute(
            "UPDATE standard_boq_library SET boq_code=?, item_number=?, description=?, "
            "detailed_specification=?, unit=?, category=?, sub_category=?, standard_rate=?, "
            "is_active=?, modified_by=?, modified_at=? WHERE id=?",
            (
                boq_code,
                item_number,
                description,
                detailed_specification,
                unit,
                category,
                sub_category,
                standard_rate,
                is_active,
                username,
                now,
                item_id,
            ),
        )
        return item_id

    db.execute(
        "INSERT INTO standard_boq_library("
        "boq_code, item_number, description, detailed_specification, unit, "
        "category, sub_category, standard_rate, is_active, created_by, created_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (
            boq_code,
            item_number,
            description,
            detailed_specification,
            unit,
            category,
            sub_category,
            standard_rate,
            is_active,
            username,
            now,
        ),
    )
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


def delete_standard_boq_item(db, item_id: int) -> None:
    ensure_standard_boq_library_schema(db)
    db.execute("DELETE FROM standard_boq_library WHERE id=?", (item_id,))


def library_categories(db) -> list[str]:
    ensure_standard_boq_library_schema(db)
    rows = db.execute(
        "SELECT DISTINCT category FROM standard_boq_library "
        "WHERE category IS NOT NULL AND TRIM(category)!='' ORDER BY category"
    ).fetchall()
    return [r["category"] for r in rows]
