"""Labour productivity — planned vs actual quantity, labour hours, productivity rate by project and trade."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from treasury_service import log_treasury_audit

TRADES = (
    "Mason",
    "Carpenter",
    "Electrician",
    "Plumber",
    "Steel Fixer",
    "Helper",
    "Painter",
    "Operator",
    "Other",
)
UNITS = ("cum", "sqm", "rmt", "nos", "kg", "mt", "km", "hr")


def _table_exists(db, table: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _round2(value: float) -> float:
    return round(_safe_float(value), 2)


def _round4(value: float) -> float:
    return round(_safe_float(value), 4)


def _compute_metrics(planned: float, actual: float, labour_hours: float) -> dict[str, float | None]:
    variance = _round4(actual - planned)
    productivity_rate = (
        _round4(actual / labour_hours) if labour_hours > 0 else None
    )
    return {
        "variance": variance,
        "productivity_rate": productivity_rate,
    }


def ensure_labour_productivity_schema(db) -> None:
    """Create labour productivity entry table."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS labour_productivity_entries(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            trade TEXT NOT NULL,
            work_date TEXT,
            period_month TEXT,
            planned_quantity REAL DEFAULT 0,
            actual_quantity REAL DEFAULT 0,
            unit TEXT DEFAULT 'cum',
            labour_hours REAL DEFAULT 0,
            notes TEXT,
            created_by TEXT,
            updated_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
        """
    )
    if _table_exists(db, "labour_productivity_entries"):
        cols = [r[1] for r in db.execute("PRAGMA table_info(labour_productivity_entries)").fetchall()]
        for column, col_type in (
            ("project_id", "INTEGER"),
            ("trade", "TEXT"),
            ("work_date", "TEXT"),
            ("period_month", "TEXT"),
            ("planned_quantity", "REAL DEFAULT 0"),
            ("actual_quantity", "REAL DEFAULT 0"),
            ("unit", "TEXT DEFAULT 'cum'"),
            ("labour_hours", "REAL DEFAULT 0"),
            ("notes", "TEXT"),
            ("created_by", "TEXT"),
            ("updated_at", "TEXT"),
        ):
            if column not in cols:
                db.execute(f"ALTER TABLE labour_productivity_entries ADD COLUMN {column} {col_type}")
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_labour_productivity_project "
            "ON labour_productivity_entries(project_id)"
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_labour_productivity_trade "
            "ON labour_productivity_entries(trade)"
        )


def _enrich_entry_row(row: dict) -> dict:
    out = dict(row)
    planned = _safe_float(out.get("planned_quantity"))
    actual = _safe_float(out.get("actual_quantity"))
    hours = _safe_float(out.get("labour_hours"))
    out["planned_quantity"] = _round4(planned)
    out["actual_quantity"] = _round4(actual)
    out["labour_hours"] = _round2(hours)
    out.update(_compute_metrics(planned, actual, hours))
    return out


def list_entries(
    db,
    *,
    project_id: int | None = None,
    trade: str | None = None,
    period_month: str | None = None,
    work_date_from: str | None = None,
    work_date_to: str | None = None,
    search: str | None = None,
) -> list[dict]:
    ensure_labour_productivity_schema(db)
    sql = (
        "SELECT e.*, p.project_name, p.location "
        "FROM labour_productivity_entries e "
        "JOIN projects p ON e.project_id = p.id "
        "WHERE 1=1 "
    )
    params: list[Any] = []
    if project_id:
        sql += "AND e.project_id=? "
        params.append(project_id)
    if trade:
        sql += "AND e.trade=? "
        params.append(trade)
    if period_month:
        sql += "AND e.period_month=? "
        params.append(period_month)
    if work_date_from:
        sql += "AND e.work_date>=? "
        params.append(work_date_from)
    if work_date_to:
        sql += "AND e.work_date<=? "
        params.append(work_date_to)
    if search and search.strip():
        q = f"%{search.strip()}%"
        sql += "AND (e.trade LIKE ? OR e.notes LIKE ? OR p.project_name LIKE ?) "
        params.extend([q, q, q])
    sql += "ORDER BY COALESCE(e.work_date, e.period_month) DESC, e.trade, e.id DESC"
    rows = db.execute(sql, params).fetchall()
    return [_enrich_entry_row(dict(r)) for r in rows]


def get_entry(db, entry_id: int) -> dict | None:
    ensure_labour_productivity_schema(db)
    row = db.execute(
        """
        SELECT e.*, p.project_name, p.location
        FROM labour_productivity_entries e
        JOIN projects p ON e.project_id = p.id
        WHERE e.id=?
        """,
        (entry_id,),
    ).fetchone()
    return _enrich_entry_row(dict(row)) if row else None


def _validate_entry_form(form_data: dict) -> dict:
    project_raw = (form_data.get("project_id") or "").strip()
    if not project_raw:
        raise ValueError("Project is required.")
    project_id = int(project_raw)
    trade = (form_data.get("trade") or "").strip()
    if not trade:
        raise ValueError("Trade is required.")
    work_date = (form_data.get("work_date") or "").strip() or None
    period_month = (form_data.get("period_month") or "").strip() or None
    if not work_date and not period_month:
        raise ValueError("Enter either a work date or a period month (YYYY-MM).")
    if period_month and len(period_month) >= 7:
        period_month = period_month[:7]
    unit = (form_data.get("unit") or "cum").strip()
    if unit not in UNITS:
        unit = "cum"
    planned = _round4(form_data.get("planned_quantity"))
    actual = _round4(form_data.get("actual_quantity"))
    labour_hours = _round2(form_data.get("labour_hours"))
    if labour_hours < 0 or planned < 0 or actual < 0:
        raise ValueError("Quantities and labour hours cannot be negative.")
    notes = (form_data.get("notes") or "").strip() or None
    return {
        "project_id": project_id,
        "trade": trade,
        "work_date": work_date,
        "period_month": period_month,
        "planned_quantity": planned,
        "actual_quantity": actual,
        "unit": unit,
        "labour_hours": labour_hours,
        "notes": notes,
    }


def create_entry(db, form_data: dict, username: str) -> int:
    ensure_labour_productivity_schema(db)
    data = _validate_entry_form(form_data)
    ts = _now_ts()
    db.execute(
        """
        INSERT INTO labour_productivity_entries(
            project_id, trade, work_date, period_month, planned_quantity,
            actual_quantity, unit, labour_hours, notes, created_by, updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            data["project_id"],
            data["trade"],
            data["work_date"],
            data["period_month"],
            data["planned_quantity"],
            data["actual_quantity"],
            data["unit"],
            data["labour_hours"],
            data["notes"],
            username,
            ts,
        ),
    )
    entry_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    log_treasury_audit(
        db,
        "labour_productivity",
        entry_id,
        "create",
        username,
        f"{data['trade']} — planned {data['planned_quantity']} {data['unit']}, "
        f"actual {data['actual_quantity']}, {data['labour_hours']} hrs",
    )
    return entry_id


def update_entry(db, entry_id: int, form_data: dict, username: str) -> None:
    ensure_labour_productivity_schema(db)
    existing = db.execute(
        "SELECT id FROM labour_productivity_entries WHERE id=?",
        (entry_id,),
    ).fetchone()
    if not existing:
        raise ValueError("Labour productivity entry not found.")
    data = _validate_entry_form(form_data)
    ts = _now_ts()
    db.execute(
        """
        UPDATE labour_productivity_entries SET
            project_id=?, trade=?, work_date=?, period_month=?,
            planned_quantity=?, actual_quantity=?, unit=?,
            labour_hours=?, notes=?, updated_at=?
        WHERE id=?
        """,
        (
            data["project_id"],
            data["trade"],
            data["work_date"],
            data["period_month"],
            data["planned_quantity"],
            data["actual_quantity"],
            data["unit"],
            data["labour_hours"],
            data["notes"],
            ts,
            entry_id,
        ),
    )
    log_treasury_audit(
        db,
        "labour_productivity",
        entry_id,
        "update",
        username,
        f"{data['trade']} — planned {data['planned_quantity']} {data['unit']}, "
        f"actual {data['actual_quantity']}, {data['labour_hours']} hrs",
    )


def get_project_summary(db, project_id: int) -> dict:
    """Aggregate productivity metrics for one project, grouped by trade."""
    ensure_labour_productivity_schema(db)
    project = db.execute(
        "SELECT id, project_name, location, status FROM projects WHERE id=?",
        (project_id,),
    ).fetchone()
    if not project:
        return {}
    trades = get_trade_summary(db, project_id=project_id)
    totals = {
        "planned_quantity": _round4(sum(t["planned_quantity"] for t in trades)),
        "actual_quantity": _round4(sum(t["actual_quantity"] for t in trades)),
        "labour_hours": _round2(sum(t["labour_hours"] for t in trades)),
        "entry_count": sum(t["entry_count"] for t in trades),
    }
    totals.update(_compute_metrics(
        totals["planned_quantity"],
        totals["actual_quantity"],
        totals["labour_hours"],
    ))
    return {
        "project": dict(project),
        "trades": trades,
        "totals": totals,
    }


def get_trade_summary(
    db,
    *,
    project_id: int | None = None,
    period_month: str | None = None,
) -> list[dict]:
    """Trade-wise rollup of planned/actual quantities and productivity."""
    ensure_labour_productivity_schema(db)
    sql = (
        "SELECT trade, unit, "
        "COALESCE(SUM(planned_quantity), 0) AS planned_quantity, "
        "COALESCE(SUM(actual_quantity), 0) AS actual_quantity, "
        "COALESCE(SUM(labour_hours), 0) AS labour_hours, "
        "COUNT(*) AS entry_count "
        "FROM labour_productivity_entries WHERE 1=1 "
    )
    params: list[Any] = []
    if project_id:
        sql += "AND project_id=? "
        params.append(project_id)
    if period_month:
        sql += "AND period_month=? "
        params.append(period_month)
    sql += "GROUP BY trade, unit ORDER BY trade, unit"
    rows = db.execute(sql, params).fetchall()
    out: list[dict] = []
    for row in rows:
        item = dict(row)
        planned = _safe_float(item.get("planned_quantity"))
        actual = _safe_float(item.get("actual_quantity"))
        hours = _safe_float(item.get("labour_hours"))
        item["planned_quantity"] = _round4(planned)
        item["actual_quantity"] = _round4(actual)
        item["labour_hours"] = _round2(hours)
        item["entry_count"] = int(item.get("entry_count") or 0)
        item.update(_compute_metrics(planned, actual, hours))
        out.append(item)
    return out


def get_list_summary(db, entries: list[dict] | None = None) -> dict:
    """Summary cards for list view from filtered entries or all rows."""
    if entries is None:
        entries = list_entries(db)
    if not entries:
        return {
            "entry_count": 0,
            "trade_count": 0,
            "project_count": 0,
            "planned_quantity": 0.0,
            "actual_quantity": 0.0,
            "labour_hours": 0.0,
            "variance": 0.0,
            "productivity_rate": None,
        }
    planned = sum(_safe_float(e.get("planned_quantity")) for e in entries)
    actual = sum(_safe_float(e.get("actual_quantity")) for e in entries)
    hours = sum(_safe_float(e.get("labour_hours")) for e in entries)
    metrics = _compute_metrics(planned, actual, hours)
    return {
        "entry_count": len(entries),
        "trade_count": len({e.get("trade") for e in entries}),
        "project_count": len({e.get("project_id") for e in entries}),
        "planned_quantity": _round4(planned),
        "actual_quantity": _round4(actual),
        "labour_hours": _round2(hours),
        **metrics,
    }


def suggest_labour_hours_from_dpr(
    db,
    project_id: int,
    trade: str,
    work_date: str | None = None,
    period_month: str | None = None,
) -> dict[str, Any]:
    """Stub: aggregate DPR manpower hours for project/trade/date if tables exist."""
    if not _table_exists(db, "dpr_manpower") or not _table_exists(db, "dpr_measurements"):
        return {"available": False, "hours": 0.0, "source": None, "detail_count": 0}
    sql = (
        "SELECT COALESCE(SUM(mp.hours_worked), 0) AS hours, COUNT(*) AS detail_count "
        "FROM dpr_manpower mp "
        "JOIN dpr_measurements m ON mp.measurement_id = m.id "
        "WHERE m.project_id=? AND mp.trade_name=? "
    )
    params: list[Any] = [project_id, trade]
    if work_date:
        sql += "AND m.report_date=? "
        params.append(work_date)
    elif period_month:
        sql += "AND substr(m.report_date, 1, 7)=? "
        params.append(period_month[:7])
    row = db.execute(sql, params).fetchone()
    hours = _round2(row["hours"] if row else 0)
    count = int(row["detail_count"] if row else 0)
    return {
        "available": True,
        "hours": hours,
        "source": "dpr_manpower",
        "detail_count": count,
    }


def suggest_labour_hours_from_timesheets(
    db,
    project_id: int,
    work_date: str | None = None,
    period_month: str | None = None,
) -> dict[str, Any]:
    """Stub: aggregate daily_timesheets total_hours if table exists."""
    if not _table_exists(db, "daily_timesheets"):
        return {"available": False, "hours": 0.0, "source": None, "detail_count": 0}
    sql = (
        "SELECT COALESCE(SUM(total_hours), 0) AS hours, COUNT(*) AS detail_count "
        "FROM daily_timesheets WHERE project_id=? "
    )
    params: list[Any] = [project_id]
    if work_date:
        sql += "AND timesheet_date=? "
        params.append(work_date)
    elif period_month:
        sql += "AND substr(timesheet_date, 1, 7)=? "
        params.append(period_month[:7])
    row = db.execute(sql, params).fetchone()
    hours = _round2(row["hours"] if row else 0)
    count = int(row["detail_count"] if row else 0)
    return {
        "available": True,
        "hours": hours,
        "source": "daily_timesheets",
        "detail_count": count,
    }


def list_entry_audit(db, entry_id: int, limit: int = 15) -> list[dict]:
    rows = db.execute(
        """
        SELECT * FROM treasury_audit_log
        WHERE entity_type='labour_productivity' AND entity_id=?
        ORDER BY created_at DESC LIMIT ?
        """,
        (entry_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def seed_labour_productivity_demo_data(db) -> None:
    if os.environ.get("MAXEK_SKIP_DEMO_SEED"):
        return
    ensure_labour_productivity_schema(db)
    count = db.execute("SELECT COUNT(*) AS c FROM labour_productivity_entries").fetchone()["c"]
    if count > 0:
        return

    project = db.execute(
        "SELECT id FROM projects WHERE project_name LIKE '%Demo Highway%' "
        "OR status='Active' ORDER BY id LIMIT 1"
    ).fetchone()
    if not project:
        return
    project_id = project["id"]
    ts = _now_ts()
    demo_rows = (
        ("Mason", "2026-05", None, 120.0, 108.5, "cum", 840.0, "May — PCC & masonry package."),
        ("Carpenter", "2026-05", None, 45.0, 42.0, "sqm", 520.0, "May — formwork shuttering."),
        ("Helper", "2026-05", None, 200.0, 215.0, "rmt", 960.0, "May — general assistance & bar bending support."),
    )
    for trade, period, work_date, planned, actual, unit, hours, notes in demo_rows:
        db.execute(
            """
            INSERT INTO labour_productivity_entries(
                project_id, trade, work_date, period_month, planned_quantity,
                actual_quantity, unit, labour_hours, notes, created_by, updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                project_id,
                trade,
                work_date,
                period,
                planned,
                actual,
                unit,
                hours,
                notes,
                "demo",
                ts,
            ),
        )
    log_treasury_audit(
        db,
        "labour_productivity",
        project_id,
        "demo_seed",
        "demo",
        f"Seeded 3 labour productivity entries for project #{project_id}",
    )
