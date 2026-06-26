"""Typical BOQ templates and standard cost library for planning automation."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from cost_planning_service import (
    calc_manpower_line,
    calc_material_line,
    calc_machinery_line,
    ensure_cost_planning_tables,
    _now_ts,
    _safe_float,
    _table_exists,
    _ensure_column,
)


def ensure_library_schema(db) -> None:
    """Typical BOQ templates and cost consumption library."""
    ensure_cost_planning_tables(db)

    db.execute("""
        CREATE TABLE IF NOT EXISTS typical_boq_templates(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_code TEXT UNIQUE NOT NULL,
            template_name TEXT NOT NULL,
            category TEXT,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS typical_boq_template_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            line_no INTEGER DEFAULT 1,
            item_description TEXT NOT NULL,
            default_quantity REAL DEFAULT 1,
            unit TEXT,
            default_rate REAL DEFAULT 0,
            FOREIGN KEY(template_id) REFERENCES typical_boq_templates(id) ON DELETE CASCADE
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS typical_cost_library(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_code TEXT UNIQUE NOT NULL,
            activity_name TEXT NOT NULL,
            boq_unit TEXT,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS typical_cost_library_materials(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            library_id INTEGER NOT NULL,
            material_name TEXT NOT NULL,
            material_unit TEXT,
            consumption_per_unit REAL DEFAULT 0,
            default_rate REAL DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY(library_id) REFERENCES typical_cost_library(id) ON DELETE CASCADE
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS typical_cost_library_manpower(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            library_id INTEGER NOT NULL,
            trade_name TEXT NOT NULL,
            hours_per_unit REAL DEFAULT 0,
            default_labour_rate REAL DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY(library_id) REFERENCES typical_cost_library(id) ON DELETE CASCADE
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS typical_cost_library_equipment(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            library_id INTEGER NOT NULL,
            equipment_type TEXT NOT NULL,
            hours_per_unit REAL DEFAULT 0,
            default_hourly_rate REAL DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY(library_id) REFERENCES typical_cost_library(id) ON DELETE CASCADE
        )
    """)
    try:
        db.commit()
    except sqlite3.Error:
        pass


def seed_typical_libraries(db) -> None:
    """Seed demo typical BOQ and cost library if empty."""
    ensure_library_schema(db)
    existing = db.execute("SELECT COUNT(*) AS c FROM typical_boq_templates").fetchone()
    if existing and int(existing["c"] or 0) > 0:
        return

    now = _now_ts()
    templates = [
        (
            "EXC",
            "Excavation in Ordinary Soil",
            "Excavation",
            "Bulk excavation including stacking / lead as per site",
            [
                ("Excavation in ordinary soil up to 1.5m depth", 100, "Cum", 450),
                ("Excavation in hard soil", 50, "Cum", 650),
                ("Disposal of excavated earth within 50m lead", 150, "Cum", 120),
            ],
        ),
        (
            "PCC",
            "Plain Cement Concrete 1:3:6",
            "PCC",
            "PCC below footings / grade slab",
            [
                ("PCC 1:3:6 (M10) 100mm thick", 80, "Cum", 5200),
                ("PCC 1:4:8 levelling course", 40, "Cum", 4800),
            ],
        ),
        (
            "RFT",
            "Reinforcement Steel",
            "Reinforcement",
            "TMT bars including cutting, bending, tying",
            [
                ("Fe500D TMT bars — all diameters", 12, "MT", 62000),
                ("Binding wire", 12, "MT", 85),
            ],
        ),
        (
            "SHT",
            "Shuttering / Formwork",
            "Shuttering",
            "Centering and shuttering for RCC",
            [
                ("Shuttering for footings", 200, "Sqm", 420),
                ("Shuttering for columns", 350, "Sqm", 480),
                ("Shuttering for slabs & beams", 500, "Sqm", 520),
            ],
        ),
        (
            "RCC",
            "Reinforced Cement Concrete",
            "Concrete",
            "RCC M25 / M30 including placing & compaction",
            [
                ("RCC M25 in footings", 60, "Cum", 7800),
                ("RCC M25 in columns", 45, "Cum", 8200),
                ("RCC M30 in slabs", 120, "Cum", 8500),
            ],
        ),
    ]

    for code, name, category, desc, lines in templates:
        db.execute(
            "INSERT INTO typical_boq_templates(template_code, template_name, category, description, "
            "is_active, sort_order, created_at) VALUES(?,?,?,?,1,?,?)",
            (code, name, category, desc, len(lines), now),
        )
        tid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        for idx, (item_desc, qty, unit, rate) in enumerate(lines, start=1):
            db.execute(
                "INSERT INTO typical_boq_template_lines(template_id, line_no, item_description, "
                "default_quantity, unit, default_rate) VALUES(?,?,?,?,?,?)",
                (tid, idx, item_desc, qty, unit, rate),
            )

    cost_items = [
        (
            "PCC-136",
            "PCC 1:3:6",
            "Cum",
            "Standard consumption for PCC 1:3:6 per m³",
            [
                ("Cement", "Bag", 6.4, 380),
                ("Sand", "Cum", 0.45, 1200),
                ("Aggregate 20mm", "Cum", 0.90, 950),
            ],
            [("Mason", 0.8, 450), ("Helper", 1.2, 350)],
            [("Concrete Mixer", 0.15, 800)],
        ),
        (
            "RCC-M25",
            "RCC M25",
            "Cum",
            "Standard consumption for RCC M25 per m³",
            [
                ("Cement", "Bag", 7.8, 380),
                ("Sand", "Cum", 0.42, 1200),
                ("Aggregate 20mm", "Cum", 0.84, 950),
                ("Steel", "Kg", 110, 62),
            ],
            [("Mason", 1.0, 450), ("Bar Bender", 0.5, 500), ("Helper", 1.5, 350)],
            [("Batching Plant", 0.08, 1200), ("Vibrator", 0.12, 400)],
        ),
        (
            "EXC-ORD",
            "Excavation Ordinary",
            "Cum",
            "Excavation productivity norms",
            [],
            [("Excavator Operator", 0.05, 550), ("Helper", 0.15, 350)],
            [("JCB 3DX", 0.08, 1500)],
        ),
    ]

    for code, name, unit, desc, mats, labour, equip in cost_items:
        db.execute(
            "INSERT INTO typical_cost_library(activity_code, activity_name, boq_unit, description, "
            "is_active, sort_order, created_at) VALUES(?,?,?,?,1,?,?)",
            (code, name, unit, desc, len(mats) + len(labour), now),
        )
        lid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        for idx, (mname, munit, cons, rate) in enumerate(mats, start=1):
            db.execute(
                "INSERT INTO typical_cost_library_materials(library_id, material_name, material_unit, "
                "consumption_per_unit, default_rate, sort_order) VALUES(?,?,?,?,?,?)",
                (lid, mname, munit, cons, rate, idx),
            )
        for idx, (trade, hpu, rate) in enumerate(labour, start=1):
            db.execute(
                "INSERT INTO typical_cost_library_manpower(library_id, trade_name, hours_per_unit, "
                "default_labour_rate, sort_order) VALUES(?,?,?,?,?)",
                (lid, trade, hpu, rate, idx),
            )
        for idx, (etype, hpu, rate) in enumerate(equip, start=1):
            db.execute(
                "INSERT INTO typical_cost_library_equipment(library_id, equipment_type, hours_per_unit, "
                "default_hourly_rate, sort_order) VALUES(?,?,?,?,?)",
                (lid, etype, hpu, rate, idx),
            )

    try:
        db.commit()
    except sqlite3.Error:
        pass


def list_boq_templates(db, active_only: bool = True) -> list[dict]:
    ensure_library_schema(db)
    sql = "SELECT * FROM typical_boq_templates "
    if active_only:
        sql += "WHERE is_active=1 "
    sql += "ORDER BY sort_order, template_name"
    return [dict(r) for r in db.execute(sql).fetchall()]


def get_boq_template_lines(db, template_id: int) -> list[dict]:
    rows = db.execute(
        "SELECT * FROM typical_boq_template_lines WHERE template_id=? ORDER BY line_no, id",
        (template_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_cost_library(db, active_only: bool = True) -> list[dict]:
    ensure_library_schema(db)
    sql = "SELECT * FROM typical_cost_library "
    if active_only:
        sql += "WHERE is_active=1 "
    sql += "ORDER BY sort_order, activity_name"
    return [dict(r) for r in db.execute(sql).fetchall()]


def get_cost_library_detail(db, library_id: int) -> dict | None:
    row = db.execute(
        "SELECT * FROM typical_cost_library WHERE id=?",
        (library_id,),
    ).fetchone()
    if not row:
        return None
    data = dict(row)
    data["materials"] = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM typical_cost_library_materials WHERE library_id=? ORDER BY sort_order, id",
            (library_id,),
        ).fetchall()
    ]
    data["manpower"] = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM typical_cost_library_manpower WHERE library_id=? ORDER BY sort_order, id",
            (library_id,),
        ).fetchall()
    ]
    data["equipment"] = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM typical_cost_library_equipment WHERE library_id=? ORDER BY sort_order, id",
            (library_id,),
        ).fetchall()
    ]
    return data


def match_cost_library_for_boq_item(description: str, unit: str) -> str | None:
    """Heuristic match keyword → activity_code."""
    text = (description or "").lower()
    unit_l = (unit or "").lower()
    if "pcc" in text or "plain cement" in text:
        return "PCC-136"
    if "rcc" in text or "reinforced" in text or "concrete" in text:
        if unit_l in ("cum", "m3", "m³"):
            return "RCC-M25"
    if "excavat" in text:
        return "EXC-ORD"
    if "shutter" in text or "formwork" in text:
        return None
    if "steel" in text or "reinfor" in text or "tmt" in text:
        return None
    return None


def auto_apply_cost_library_to_plan(
    db,
    cost_plan_id: int,
    boq_qty: float,
    library_id: int,
    username: str,
) -> None:
    """Fill cost plan lines from typical cost library × BOQ quantity."""
    detail = get_cost_library_detail(db, library_id)
    if not detail:
        raise ValueError("Cost library item not found.")

    now = _now_ts()
    activity_name = detail["activity_name"]
    db.execute(
        "INSERT INTO cost_plan_activities(cost_plan_id, boq_item_id, activity_name, activity_unit, "
        "planned_qty, sort_order, created_by, created_at) "
        "SELECT ?, boq_item_id, ?, ?, ?, 1, ?, ? FROM cost_plans WHERE id=?",
        (cost_plan_id, activity_name, detail.get("boq_unit") or "Cum", boq_qty, username, now, cost_plan_id),
    )
    activity_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    for idx, mat in enumerate(detail.get("materials") or [], start=1):
        cons = _safe_float(mat.get("consumption_per_unit"))
        rate = _safe_float(mat.get("default_rate"))
        pq, pa = calc_material_line(boq_qty, cons, rate)
        db.execute(
            "INSERT INTO cost_plan_materials(cost_plan_id, activity_id, material_name, material_unit, "
            "consumption_factor, rate, planned_qty, planned_amount, sort_order, created_by, created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                cost_plan_id,
                activity_id,
                mat["material_name"],
                mat.get("material_unit") or "Nos",
                cons,
                rate,
                pq,
                pa,
                idx,
                username,
                now,
            ),
        )

    for idx, mp in enumerate(detail.get("manpower") or [], start=1):
        hpu = _safe_float(mp.get("hours_per_unit"))
        rate = _safe_float(mp.get("default_labour_rate"))
        ph, pa = calc_manpower_line(boq_qty, hpu, rate)
        db.execute(
            "INSERT INTO cost_plan_manpower(cost_plan_id, activity_id, trade_name, planned_manpower, "
            "hours_per_unit, labour_rate, planned_hours, planned_amount, sort_order) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (cost_plan_id, activity_id, mp["trade_name"], 0, hpu, rate, ph, pa, idx),
        )

    for idx, eq in enumerate(detail.get("equipment") or [], start=1):
        hpu = _safe_float(eq.get("hours_per_unit"))
        rate = _safe_float(eq.get("default_hourly_rate"))
        ph, pa = calc_machinery_line(boq_qty, hpu, rate)
        db.execute(
            "INSERT INTO cost_plan_machinery(cost_plan_id, activity_id, equipment_type, hours_per_unit, "
            "hourly_rate, planned_hours, planned_amount, sort_order) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (cost_plan_id, activity_id, eq["equipment_type"], hpu, rate, ph, pa, idx),
        )


def suggest_cost_library_id(db, item_description: str, unit: str) -> int | None:
    code = match_cost_library_for_boq_item(item_description, unit)
    if not code:
        return None
    row = db.execute(
        "SELECT id FROM typical_cost_library WHERE activity_code=? AND is_active=1",
        (code,),
    ).fetchone()
    return int(row["id"]) if row else None
