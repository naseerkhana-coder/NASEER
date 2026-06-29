"""Master library schemas and CRUD — WBS, Labour, Machinery, Productivity, Rate."""

from __future__ import annotations

import io
import sqlite3
from datetime import datetime
from typing import Any

import pandas as pd

from import_tenant_helpers import tenant_filter_sql


def _ensure_column(db, table: str, column: str, col_type: str) -> None:
    if not db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone():
        return
    cols = {r[1] for r in db.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def ensure_master_library_schemas(db) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS standard_wbs_library(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wbs_code TEXT NOT NULL,
            parent_code TEXT,
            description TEXT NOT NULL,
            level INTEGER DEFAULT 1,
            unit TEXT,
            planned_quantity REAL DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            customer_id INTEGER,
            created_by TEXT,
            created_at TEXT,
            modified_by TEXT,
            modified_at TEXT
        )
    """)
    db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_wbs_library_code "
        "ON standard_wbs_library(wbs_code, COALESCE(customer_id, -1))"
    )

    db.execute("""
        CREATE TABLE IF NOT EXISTS labour_rate_library(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_code TEXT NOT NULL,
            trade_name TEXT NOT NULL,
            unit TEXT DEFAULT 'Day',
            standard_rate REAL DEFAULT 0,
            category TEXT,
            is_active INTEGER DEFAULT 1,
            customer_id INTEGER,
            created_by TEXT,
            created_at TEXT,
            modified_by TEXT,
            modified_at TEXT
        )
    """)
    db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_labour_library_code "
        "ON labour_rate_library(trade_code, COALESCE(customer_id, -1))"
    )

    db.execute("""
        CREATE TABLE IF NOT EXISTS machinery_rate_library(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_code TEXT NOT NULL,
            equipment_name TEXT NOT NULL,
            unit TEXT DEFAULT 'Hour',
            hourly_rate REAL DEFAULT 0,
            category TEXT,
            is_active INTEGER DEFAULT 1,
            customer_id INTEGER,
            created_by TEXT,
            created_at TEXT,
            modified_by TEXT,
            modified_at TEXT
        )
    """)
    db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_machinery_library_code "
        "ON machinery_rate_library(equipment_code, COALESCE(customer_id, -1))"
    )

    db.execute("""
        CREATE TABLE IF NOT EXISTS productivity_library(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade TEXT NOT NULL,
            unit TEXT,
            output_per_hour REAL DEFAULT 0,
            project_code TEXT,
            remarks TEXT,
            is_active INTEGER DEFAULT 1,
            customer_id INTEGER,
            created_by TEXT,
            created_at TEXT,
            modified_by TEXT,
            modified_at TEXT
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS rate_master_library(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            boq_code TEXT NOT NULL,
            description TEXT,
            unit TEXT,
            labour_rate REAL DEFAULT 0,
            machinery_rate REAL DEFAULT 0,
            material_rate REAL DEFAULT 0,
            total_rate REAL DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            customer_id INTEGER,
            created_by TEXT,
            created_at TEXT,
            modified_by TEXT,
            modified_at TEXT
        )
    """)
    db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_rate_master_boq "
        "ON rate_master_library(boq_code, COALESCE(customer_id, -1))"
    )

    for table in (
        "standard_wbs_library",
        "labour_rate_library",
        "machinery_rate_library",
        "productivity_library",
        "rate_master_library",
    ):
        _ensure_column(db, table, "customer_id", "INTEGER")

    try:
        db.commit()
    except sqlite3.Error:
        pass


def list_wbs_library(db, *, customer_id: int | None = None, search: str = "") -> list[dict[str, Any]]:
    ensure_master_library_schemas(db)
    sql = "SELECT * FROM standard_wbs_library WHERE COALESCE(is_active,1)=1"
    params: list[Any] = []
    tenant_sql, tenant_params = tenant_filter_sql("", customer_id, prefix_and=True)
    sql += tenant_sql
    params.extend(tenant_params)
    if search:
        sql += " AND (wbs_code LIKE ? OR description LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like])
    sql += " ORDER BY wbs_code"
    return [dict(r) for r in db.execute(sql, params).fetchall()]


def list_labour_library(db, *, customer_id: int | None = None, search: str = "") -> list[dict[str, Any]]:
    ensure_master_library_schemas(db)
    sql = "SELECT * FROM labour_rate_library WHERE COALESCE(is_active,1)=1"
    params: list[Any] = []
    tenant_sql, tenant_params = tenant_filter_sql("", customer_id, prefix_and=True)
    sql += tenant_sql
    params.extend(tenant_params)
    if search:
        sql += " AND (trade_code LIKE ? OR trade_name LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like])
    sql += " ORDER BY category, trade_code"
    return [dict(r) for r in db.execute(sql, params).fetchall()]


def list_machinery_library(db, *, customer_id: int | None = None, search: str = "") -> list[dict[str, Any]]:
    ensure_master_library_schemas(db)
    sql = "SELECT * FROM machinery_rate_library WHERE COALESCE(is_active,1)=1"
    params: list[Any] = []
    tenant_sql, tenant_params = tenant_filter_sql("", customer_id, prefix_and=True)
    sql += tenant_sql
    params.extend(tenant_params)
    if search:
        sql += " AND (equipment_code LIKE ? OR equipment_name LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like])
    sql += " ORDER BY category, equipment_code"
    return [dict(r) for r in db.execute(sql, params).fetchall()]


def list_productivity_library(db, *, customer_id: int | None = None, search: str = "") -> list[dict[str, Any]]:
    ensure_master_library_schemas(db)
    sql = "SELECT * FROM productivity_library WHERE COALESCE(is_active,1)=1"
    params: list[Any] = []
    tenant_sql, tenant_params = tenant_filter_sql("", customer_id, prefix_and=True)
    sql += tenant_sql
    params.extend(tenant_params)
    if search:
        sql += " AND trade LIKE ?"
        params.append(f"%{search}%")
    sql += " ORDER BY trade"
    return [dict(r) for r in db.execute(sql, params).fetchall()]


def list_rate_library(db, *, customer_id: int | None = None, search: str = "") -> list[dict[str, Any]]:
    ensure_master_library_schemas(db)
    sql = "SELECT * FROM rate_master_library WHERE COALESCE(is_active,1)=1"
    params: list[Any] = []
    tenant_sql, tenant_params = tenant_filter_sql("", customer_id, prefix_and=True)
    sql += tenant_sql
    params.extend(tenant_params)
    if search:
        sql += " AND (boq_code LIKE ? OR description LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like])
    sql += " ORDER BY boq_code"
    return [dict(r) for r in db.execute(sql, params).fetchall()]


def _export_df(rows: list[dict], columns: list[str], sheet: str) -> io.BytesIO:
    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=columns)
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    df = df[columns]
    buf = io.BytesIO()
    df.to_excel(buf, index=False, sheet_name=sheet)
    buf.seek(0)
    return buf


def export_wbs_library_excel(db, *, customer_id: int | None = None) -> io.BytesIO:
    cols = ["WBS Code", "Parent Code", "Description", "Level", "Unit", "Planned Quantity"]
    rows = [
        {
            "WBS Code": r["wbs_code"],
            "Parent Code": r.get("parent_code") or "",
            "Description": r["description"],
            "Level": r.get("level") or 1,
            "Unit": r.get("unit") or "",
            "Planned Quantity": r.get("planned_quantity") or 0,
        }
        for r in list_wbs_library(db, customer_id=customer_id)
    ]
    return _export_df(rows, cols, "WBS Library")


def export_labour_library_excel(db, *, customer_id: int | None = None) -> io.BytesIO:
    cols = ["Trade Code", "Trade Name", "Unit", "Standard Rate", "Category"]
    rows = [
        {
            "Trade Code": r["trade_code"],
            "Trade Name": r["trade_name"],
            "Unit": r.get("unit") or "Day",
            "Standard Rate": r.get("standard_rate") or 0,
            "Category": r.get("category") or "",
        }
        for r in list_labour_library(db, customer_id=customer_id)
    ]
    return _export_df(rows, cols, "Labour Library")


def export_machinery_library_excel(db, *, customer_id: int | None = None) -> io.BytesIO:
    cols = ["Equipment Code", "Equipment Name", "Unit", "Hourly Rate", "Category"]
    rows = [
        {
            "Equipment Code": r["equipment_code"],
            "Equipment Name": r["equipment_name"],
            "Unit": r.get("unit") or "Hour",
            "Hourly Rate": r.get("hourly_rate") or 0,
            "Category": r.get("category") or "",
        }
        for r in list_machinery_library(db, customer_id=customer_id)
    ]
    return _export_df(rows, cols, "Machinery Library")


def export_productivity_library_excel(db, *, customer_id: int | None = None) -> io.BytesIO:
    cols = ["Trade", "Unit", "Output Per Hour", "Project Code", "Remarks"]
    rows = [
        {
            "Trade": r["trade"],
            "Unit": r.get("unit") or "",
            "Output Per Hour": r.get("output_per_hour") or 0,
            "Project Code": r.get("project_code") or "",
            "Remarks": r.get("remarks") or "",
        }
        for r in list_productivity_library(db, customer_id=customer_id)
    ]
    return _export_df(rows, cols, "Productivity Library")


def export_rate_library_excel(db, *, customer_id: int | None = None) -> io.BytesIO:
    cols = ["BOQ Code", "Description", "Unit", "Labour Rate", "Machinery Rate", "Material Rate", "Total Rate"]
    rows = [
        {
            "BOQ Code": r["boq_code"],
            "Description": r.get("description") or "",
            "Unit": r.get("unit") or "",
            "Labour Rate": r.get("labour_rate") or 0,
            "Machinery Rate": r.get("machinery_rate") or 0,
            "Material Rate": r.get("material_rate") or 0,
            "Total Rate": r.get("total_rate") or 0,
        }
        for r in list_rate_library(db, customer_id=customer_id)
    ]
    return _export_df(rows, cols, "Rate Library")
