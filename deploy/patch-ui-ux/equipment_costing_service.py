"""Machine-wise equipment costing — fuel, operator, maintenance, tyre, spares; cost per hour/km/day."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from budget_service import ensure_budget_schema
from treasury_service import log_treasury_audit

EQUIPMENT_STATUSES = ("Active", "Inactive", "Under Maintenance", "Disposed")
OWNER_TYPES = ("Company Owned", "Hired Equipment", "Subcontractor")


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


def _compute_cost_metrics(
    fuel_cost: float,
    operator_cost: float,
    maintenance_cost: float,
    tyre_cost: float,
    spare_parts_cost: float,
    operating_hours: float,
    operating_km: float,
    operating_days: float,
) -> dict[str, float | None]:
    total_cost = _round2(
        fuel_cost + operator_cost + maintenance_cost + tyre_cost + spare_parts_cost
    )
    cost_per_hour = (
        _round2(total_cost / operating_hours) if operating_hours > 0 else None
    )
    cost_per_km = _round2(total_cost / operating_km) if operating_km > 0 else None
    cost_per_day = _round2(total_cost / operating_days) if operating_days > 0 else None
    return {
        "total_cost": total_cost,
        "cost_per_hour": cost_per_hour,
        "cost_per_km": cost_per_km,
        "cost_per_day": cost_per_day,
    }


def ensure_equipment_costing_schema(db) -> None:
    """Extend DPR equipment_master and create monthly cost entry lines."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS equipment_master(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reg_no TEXT UNIQUE,
            equipment_name TEXT NOT NULL,
            equipment_type TEXT,
            owner_type TEXT DEFAULT 'Company Owned',
            hourly_rate REAL DEFAULT 0,
            km_rate REAL DEFAULT 0,
            trip_rate REAL DEFAULT 0,
            status TEXT DEFAULT 'Active',
            created_at TEXT
        )
        """
    )
    if _table_exists(db, "equipment_master"):
        cols = [r[1] for r in db.execute("PRAGMA table_info(equipment_master)").fetchall()]
        for column, col_type in (
            ("equipment_code", "TEXT"),
            ("project_id", "INTEGER"),
            ("reg_no", "TEXT"),
            ("equipment_name", "TEXT"),
            ("equipment_type", "TEXT"),
            ("owner_type", "TEXT DEFAULT 'Company Owned'"),
            ("hourly_rate", "REAL DEFAULT 0"),
            ("km_rate", "REAL DEFAULT 0"),
            ("trip_rate", "REAL DEFAULT 0"),
            ("status", "TEXT DEFAULT 'Active'"),
            ("created_at", "TEXT"),
            ("updated_at", "TEXT"),
            ("updated_by", "TEXT"),
        ):
            if column not in cols:
                db.execute(f"ALTER TABLE equipment_master ADD COLUMN {column} {col_type}")

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS equipment_cost_entries(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_id INTEGER NOT NULL,
            project_id INTEGER,
            period_month TEXT NOT NULL,
            fuel_cost REAL DEFAULT 0,
            operator_cost REAL DEFAULT 0,
            maintenance_cost REAL DEFAULT 0,
            tyre_cost REAL DEFAULT 0,
            spare_parts_cost REAL DEFAULT 0,
            operating_hours REAL DEFAULT 0,
            operating_km REAL DEFAULT 0,
            operating_days REAL DEFAULT 0,
            total_cost REAL DEFAULT 0,
            cost_per_hour REAL,
            cost_per_km REAL,
            cost_per_day REAL,
            notes TEXT,
            created_by TEXT,
            updated_at TEXT,
            FOREIGN KEY(equipment_id) REFERENCES equipment_master(id),
            FOREIGN KEY(project_id) REFERENCES projects(id),
            UNIQUE(equipment_id, project_id, period_month)
        )
        """
    )
    if _table_exists(db, "equipment_cost_entries"):
        cols = [r[1] for r in db.execute("PRAGMA table_info(equipment_cost_entries)").fetchall()]
        for column, col_type in (
            ("equipment_id", "INTEGER"),
            ("project_id", "INTEGER"),
            ("period_month", "TEXT"),
            ("fuel_cost", "REAL DEFAULT 0"),
            ("operator_cost", "REAL DEFAULT 0"),
            ("maintenance_cost", "REAL DEFAULT 0"),
            ("tyre_cost", "REAL DEFAULT 0"),
            ("spare_parts_cost", "REAL DEFAULT 0"),
            ("operating_hours", "REAL DEFAULT 0"),
            ("operating_km", "REAL DEFAULT 0"),
            ("operating_days", "REAL DEFAULT 0"),
            ("total_cost", "REAL DEFAULT 0"),
            ("cost_per_hour", "REAL"),
            ("cost_per_km", "REAL"),
            ("cost_per_day", "REAL"),
            ("notes", "TEXT"),
            ("created_by", "TEXT"),
            ("updated_at", "TEXT"),
        ):
            if column not in cols:
                db.execute(f"ALTER TABLE equipment_cost_entries ADD COLUMN {column} {col_type}")


def _enrich_equipment_row(row: dict) -> dict:
    out = dict(row)
    out["equipment_code"] = (out.get("equipment_code") or out.get("reg_no") or "").strip()
    out["name"] = out.get("equipment_name") or ""
    out["type"] = out.get("equipment_type") or ""
    out["registration_no"] = out.get("reg_no") or ""
    return out


def _enrich_cost_entry_row(row: dict) -> dict:
    out = dict(row)
    metrics = _compute_cost_metrics(
        _safe_float(out.get("fuel_cost")),
        _safe_float(out.get("operator_cost")),
        _safe_float(out.get("maintenance_cost")),
        _safe_float(out.get("tyre_cost")),
        _safe_float(out.get("spare_parts_cost")),
        _safe_float(out.get("operating_hours")),
        _safe_float(out.get("operating_km")),
        _safe_float(out.get("operating_days")),
    )
    out.update(metrics)
    return out


def list_equipment(
    db,
    *,
    project_id: int | None = None,
    status: str | None = None,
    search: str | None = None,
) -> list[dict]:
    ensure_equipment_costing_schema(db)
    sql = (
        "SELECT e.*, p.project_name "
        "FROM equipment_master e "
        "LEFT JOIN projects p ON e.project_id = p.id "
        "WHERE 1=1 "
    )
    params: list[Any] = []
    if project_id:
        sql += "AND e.project_id=? "
        params.append(project_id)
    if status:
        sql += "AND e.status=? "
        params.append(status)
    if search and search.strip():
        q = f"%{search.strip()}%"
        sql += (
            "AND (e.equipment_name LIKE ? OR e.equipment_code LIKE ? OR e.reg_no LIKE ? "
            "OR e.equipment_type LIKE ?) "
        )
        params.extend([q, q, q, q])
    sql += "ORDER BY e.equipment_name, e.reg_no"
    rows = db.execute(sql, params).fetchall()
    return [_enrich_equipment_row(dict(r)) for r in rows]


def _equipment_cost_totals(db, equipment_id: int) -> dict:
    row = db.execute(
        """
        SELECT
            COALESCE(SUM(total_cost), 0) AS total_cost,
            COALESCE(SUM(operating_hours), 0) AS operating_hours,
            COALESCE(SUM(operating_km), 0) AS operating_km,
            COALESCE(SUM(operating_days), 0) AS operating_days,
            COUNT(*) AS entry_count
        FROM equipment_cost_entries
        WHERE equipment_id=?
        """,
        (equipment_id,),
    ).fetchone()
    if not row:
        return {
            "total_cost": 0.0,
            "operating_hours": 0.0,
            "operating_km": 0.0,
            "operating_days": 0.0,
            "entry_count": 0,
            "cost_per_hour": None,
            "cost_per_km": None,
            "cost_per_day": None,
        }
    totals = dict(row)
    metrics = _compute_cost_metrics(
        0,
        0,
        0,
        0,
        0,
        _safe_float(totals.get("operating_hours")),
        _safe_float(totals.get("operating_km")),
        _safe_float(totals.get("operating_days")),
    )
    total_cost = _round2(totals.get("total_cost"))
    cost_per_hour = (
        _round2(total_cost / _safe_float(totals.get("operating_hours")))
        if _safe_float(totals.get("operating_hours")) > 0
        else None
    )
    cost_per_km = (
        _round2(total_cost / _safe_float(totals.get("operating_km")))
        if _safe_float(totals.get("operating_km")) > 0
        else None
    )
    cost_per_day = (
        _round2(total_cost / _safe_float(totals.get("operating_days")))
        if _safe_float(totals.get("operating_days")) > 0
        else None
    )
    return {
        "total_cost": total_cost,
        "operating_hours": _round2(totals.get("operating_hours")),
        "operating_km": _round2(totals.get("operating_km")),
        "operating_days": _round2(totals.get("operating_days")),
        "entry_count": int(totals.get("entry_count") or 0),
        "cost_per_hour": cost_per_hour,
        "cost_per_km": cost_per_km,
        "cost_per_day": cost_per_day,
    }


def list_equipment_with_summary(
    db,
    *,
    project_id: int | None = None,
    status: str | None = None,
    search: str | None = None,
) -> list[dict]:
    equipment = list_equipment(db, project_id=project_id, status=status, search=search)
    enriched: list[dict] = []
    for row in equipment:
        summary = _equipment_cost_totals(db, row["id"])
        enriched.append({**row, **summary})
    return enriched


def get_equipment(db, equipment_id: int) -> dict | None:
    ensure_equipment_costing_schema(db)
    row = db.execute(
        """
        SELECT e.*, p.project_name, p.location
        FROM equipment_master e
        LEFT JOIN projects p ON e.project_id = p.id
        WHERE e.id=?
        """,
        (equipment_id,),
    ).fetchone()
    if not row:
        return None
    out = _enrich_equipment_row(dict(row))
    out.update(_equipment_cost_totals(db, equipment_id))
    return out


def list_cost_entries(db, equipment_id: int, *, project_id: int | None = None) -> list[dict]:
    ensure_equipment_costing_schema(db)
    sql = (
        "SELECT c.*, p.project_name "
        "FROM equipment_cost_entries c "
        "LEFT JOIN projects p ON c.project_id = p.id "
        "WHERE c.equipment_id=? "
    )
    params: list[Any] = [equipment_id]
    if project_id:
        sql += "AND c.project_id=? "
        params.append(project_id)
    sql += "ORDER BY c.period_month DESC, c.id DESC"
    rows = db.execute(sql, params).fetchall()
    return [_enrich_cost_entry_row(dict(r)) for r in rows]


def get_cost_entry(db, cost_id: int) -> dict | None:
    ensure_equipment_costing_schema(db)
    row = db.execute(
        """
        SELECT c.*, p.project_name, e.equipment_name, e.reg_no, e.equipment_type
        FROM equipment_cost_entries c
        LEFT JOIN projects p ON c.project_id = p.id
        JOIN equipment_master e ON c.equipment_id = e.id
        WHERE c.id=?
        """,
        (cost_id,),
    ).fetchone()
    return _enrich_cost_entry_row(dict(row)) if row else None


def _validate_equipment_form(form_data: dict) -> dict:
    name = (form_data.get("name") or form_data.get("equipment_name") or "").strip()
    if not name:
        raise ValueError("Equipment name is required.")
    equipment_code = (form_data.get("equipment_code") or "").strip()
    registration_no = (
        form_data.get("registration_no") or form_data.get("reg_no") or ""
    ).strip()
    if not equipment_code and not registration_no:
        raise ValueError("Equipment code or registration number is required.")
    eq_type = (form_data.get("type") or form_data.get("equipment_type") or "").strip()
    status = (form_data.get("status") or "Active").strip()
    if status not in EQUIPMENT_STATUSES:
        raise ValueError("Select a valid status.")
    project_raw = (form_data.get("project_id") or "").strip()
    project_id = int(project_raw) if project_raw else None
    owner_type = (form_data.get("owner_type") or "Company Owned").strip()
    if owner_type not in OWNER_TYPES:
        owner_type = "Company Owned"
    return {
        "equipment_code": equipment_code or registration_no,
        "equipment_name": name,
        "equipment_type": eq_type,
        "reg_no": registration_no or equipment_code,
        "project_id": project_id,
        "status": status,
        "owner_type": owner_type,
        "hourly_rate": _round2(form_data.get("hourly_rate")),
        "km_rate": _round2(form_data.get("km_rate")),
        "trip_rate": _round2(form_data.get("trip_rate")),
    }


def save_equipment(
    db,
    form_data: dict,
    username: str,
    equipment_id: int | None = None,
) -> int:
    ensure_equipment_costing_schema(db)
    data = _validate_equipment_form(form_data)
    ts = _now_ts()
    if equipment_id:
        existing = db.execute(
            "SELECT id FROM equipment_master WHERE id=?", (equipment_id,)
        ).fetchone()
        if not existing:
            raise ValueError("Equipment not found.")
        conflict = db.execute(
            "SELECT id FROM equipment_master WHERE reg_no=? AND id!=?",
            (data["reg_no"], equipment_id),
        ).fetchone()
        if conflict:
            raise ValueError("Registration number already used by another machine.")
        db.execute(
            """
            UPDATE equipment_master SET
                equipment_code=?, equipment_name=?, equipment_type=?, reg_no=?,
                project_id=?, status=?, owner_type=?, hourly_rate=?, km_rate=?,
                trip_rate=?, updated_at=?, updated_by=?
            WHERE id=?
            """,
            (
                data["equipment_code"],
                data["equipment_name"],
                data["equipment_type"],
                data["reg_no"],
                data["project_id"],
                data["status"],
                data["owner_type"],
                data["hourly_rate"],
                data["km_rate"],
                data["trip_rate"],
                ts,
                username,
                equipment_id,
            ),
        )
        log_treasury_audit(
            db,
            "equipment_master",
            equipment_id,
            "updated",
            username,
            f"Equipment {data['equipment_code']} — {data['equipment_name']}",
        )
        return equipment_id

    conflict = db.execute(
        "SELECT id FROM equipment_master WHERE reg_no=?", (data["reg_no"],)
    ).fetchone()
    if conflict:
        raise ValueError("Registration number already exists.")
    cur = db.execute(
        """
        INSERT INTO equipment_master(
            equipment_code, equipment_name, equipment_type, reg_no, project_id,
            status, owner_type, hourly_rate, km_rate, trip_rate, created_at,
            updated_at, updated_by
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            data["equipment_code"],
            data["equipment_name"],
            data["equipment_type"],
            data["reg_no"],
            data["project_id"],
            data["status"],
            data["owner_type"],
            data["hourly_rate"],
            data["km_rate"],
            data["trip_rate"],
            ts,
            ts,
            username,
        ),
    )
    new_id = cur.lastrowid
    log_treasury_audit(
        db,
        "equipment_master",
        new_id,
        "created",
        username,
        f"Equipment {data['equipment_code']} — {data['equipment_name']}",
    )
    return new_id


def _validate_cost_entry_form(form_data: dict, equipment_id: int) -> dict:
    period_month = (form_data.get("period_month") or "").strip()
    if not period_month or len(period_month) < 7:
        raise ValueError("Period month is required (YYYY-MM).")
    period_month = period_month[:7]
    project_raw = (form_data.get("project_id") or "").strip()
    project_id = int(project_raw) if project_raw else None
    fuel = _round2(form_data.get("fuel_cost"))
    operator = _round2(form_data.get("operator_cost"))
    maintenance = _round2(form_data.get("maintenance_cost"))
    tyre = _round2(form_data.get("tyre_cost"))
    spare = _round2(form_data.get("spare_parts_cost"))
    hours = _round2(form_data.get("operating_hours"))
    km = _round2(form_data.get("operating_km"))
    days = _round2(form_data.get("operating_days"))
    metrics = _compute_cost_metrics(fuel, operator, maintenance, tyre, spare, hours, km, days)
    return {
        "equipment_id": equipment_id,
        "project_id": project_id,
        "period_month": period_month,
        "fuel_cost": fuel,
        "operator_cost": operator,
        "maintenance_cost": maintenance,
        "tyre_cost": tyre,
        "spare_parts_cost": spare,
        "operating_hours": hours,
        "operating_km": km,
        "operating_days": days,
        "notes": (form_data.get("notes") or "").strip(),
        **metrics,
    }


def save_cost_entry(
    db,
    equipment_id: int,
    form_data: dict,
    username: str,
    cost_id: int | None = None,
) -> int:
    ensure_equipment_costing_schema(db)
    equipment = db.execute(
        "SELECT id FROM equipment_master WHERE id=?", (equipment_id,)
    ).fetchone()
    if not equipment:
        raise ValueError("Equipment not found.")
    data = _validate_cost_entry_form(form_data, equipment_id)
    ts = _now_ts()
    if cost_id:
        existing = db.execute(
            "SELECT id, equipment_id FROM equipment_cost_entries WHERE id=?",
            (cost_id,),
        ).fetchone()
        if not existing or existing["equipment_id"] != equipment_id:
            raise ValueError("Cost entry not found.")
        db.execute(
            """
            UPDATE equipment_cost_entries SET
                project_id=?, period_month=?, fuel_cost=?, operator_cost=?,
                maintenance_cost=?, tyre_cost=?, spare_parts_cost=?,
                operating_hours=?, operating_km=?, operating_days=?,
                total_cost=?, cost_per_hour=?, cost_per_km=?, cost_per_day=?,
                notes=?, updated_at=?
            WHERE id=?
            """,
            (
                data["project_id"],
                data["period_month"],
                data["fuel_cost"],
                data["operator_cost"],
                data["maintenance_cost"],
                data["tyre_cost"],
                data["spare_parts_cost"],
                data["operating_hours"],
                data["operating_km"],
                data["operating_days"],
                data["total_cost"],
                data["cost_per_hour"],
                data["cost_per_km"],
                data["cost_per_day"],
                data["notes"],
                ts,
                cost_id,
            ),
        )
        log_treasury_audit(
            db,
            "equipment_cost_entry",
            cost_id,
            "updated",
            username,
            f"Cost entry {data['period_month']} for equipment #{equipment_id}",
        )
        if data["project_id"]:
            sync_equipment_costs_to_project_budget(db, data["project_id"])
        return cost_id

    try:
        cur = db.execute(
            """
            INSERT INTO equipment_cost_entries(
                equipment_id, project_id, period_month, fuel_cost, operator_cost,
                maintenance_cost, tyre_cost, spare_parts_cost, operating_hours,
                operating_km, operating_days, total_cost, cost_per_hour, cost_per_km,
                cost_per_day, notes, created_by, updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                equipment_id,
                data["project_id"],
                data["period_month"],
                data["fuel_cost"],
                data["operator_cost"],
                data["maintenance_cost"],
                data["tyre_cost"],
                data["spare_parts_cost"],
                data["operating_hours"],
                data["operating_km"],
                data["operating_days"],
                data["total_cost"],
                data["cost_per_hour"],
                data["cost_per_km"],
                data["cost_per_day"],
                data["notes"],
                username,
                ts,
            ),
        )
    except Exception as exc:
        if "UNIQUE" in str(exc):
            raise ValueError(
                "A cost entry already exists for this machine, project, and month."
            ) from exc
        raise
    new_id = cur.lastrowid
    log_treasury_audit(
        db,
        "equipment_cost_entry",
        new_id,
        "created",
        username,
        f"Cost entry {data['period_month']} for equipment #{equipment_id}",
    )
    if data["project_id"]:
        sync_equipment_costs_to_project_budget(db, data["project_id"])
    return new_id


def delete_cost_entry(db, cost_id: int, username: str) -> None:
    ensure_equipment_costing_schema(db)
    row = db.execute(
        "SELECT id, equipment_id, project_id, period_month FROM equipment_cost_entries WHERE id=?",
        (cost_id,),
    ).fetchone()
    if not row:
        raise ValueError("Cost entry not found.")
    project_id = row["project_id"]
    db.execute("DELETE FROM equipment_cost_entries WHERE id=?", (cost_id,))
    log_treasury_audit(
        db,
        "equipment_cost_entry",
        cost_id,
        "deleted",
        username,
        f"Deleted cost entry {row['period_month']} for equipment #{row['equipment_id']}",
    )
    if project_id:
        sync_equipment_costs_to_project_budget(db, project_id)


def get_equipment_costing_summary(db, equipment_rows: list[dict] | None = None) -> dict:
    rows = equipment_rows if equipment_rows is not None else list_equipment_with_summary(db)
    return {
        "machine_count": len(rows),
        "total_cost": _round2(sum(_safe_float(r.get("total_cost")) for r in rows)),
        "active_count": sum(1 for r in rows if (r.get("status") or "") == "Active"),
        "with_costs_count": sum(1 for r in rows if int(r.get("entry_count") or 0) > 0),
    }


def sync_equipment_costs_to_project_budget(
    db, project_id: int, fiscal_year: str | None = None
) -> None:
    """Stub: push summed equipment cost entries into project_budgets Equipment actual_cost."""
    ensure_equipment_costing_schema(db)
    ensure_budget_schema(db)
    row = db.execute(
        """
        SELECT COALESCE(SUM(total_cost), 0) AS total
        FROM equipment_cost_entries
        WHERE project_id=?
        """,
        (project_id,),
    ).fetchone()
    actual = _round2(row["total"] if row else 0)
    if actual <= 0:
        return
    fy = fiscal_year or None
    fy_sql = "fiscal_year IS NULL" if fy is None else "fiscal_year = ?"
    fy_args: tuple[Any, ...] = () if fy is None else (fy,)
    existing = db.execute(
        f"SELECT id, actual_cost FROM project_budgets "
        f"WHERE project_id=? AND category='Equipment' AND {fy_sql}",
        (project_id, *fy_args),
    ).fetchone()
    ts = _now_ts()
    if existing:
        new_actual = max(_safe_float(existing["actual_cost"]), actual)
        if new_actual != _safe_float(existing["actual_cost"]):
            db.execute(
                "UPDATE project_budgets SET actual_cost=?, updated_at=? WHERE id=?",
                (new_actual, ts, existing["id"]),
            )
            log_treasury_audit(
                db,
                "project_budget",
                existing["id"],
                "equipment_cost_sync",
                "system",
                f"Equipment actual_cost synced to ₹{new_actual:,.2f} for project #{project_id}",
            )
    else:
        db.execute(
            """
            INSERT INTO project_budgets(
                project_id, category, budget_amount, committed_cost, actual_cost,
                fiscal_year, updated_at
            ) VALUES(?,?,?,?,?,?,?)
            """,
            (project_id, "Equipment", 0, 0, actual, fy, ts),
        )
        budget_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        log_treasury_audit(
            db,
            "project_budget",
            budget_id,
            "equipment_cost_sync",
            "system",
            f"Equipment budget row created with actual ₹{actual:,.2f} for project #{project_id}",
        )


def list_equipment_audit(db, equipment_id: int, limit: int = 15) -> list[dict]:
    cost_ids = [
        r["id"]
        for r in db.execute(
            "SELECT id FROM equipment_cost_entries WHERE equipment_id=?",
            (equipment_id,),
        ).fetchall()
    ]
    if cost_ids:
        placeholders = ",".join("?" * len(cost_ids))
        rows = db.execute(
            f"""
            SELECT * FROM treasury_audit_log
            WHERE (
                (entity_type='equipment_master' AND entity_id=?)
                OR (entity_type='equipment_cost_entry' AND entity_id IN ({placeholders}))
            )
            ORDER BY created_at DESC LIMIT ?
            """,
            (equipment_id, *cost_ids, limit),
        ).fetchall()
    else:
        rows = db.execute(
            """
            SELECT * FROM treasury_audit_log
            WHERE entity_type='equipment_master' AND entity_id=?
            ORDER BY created_at DESC LIMIT ?
            """,
            (equipment_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def seed_equipment_costing_demo_data(db) -> None:
    if os.environ.get("MAXEK_SKIP_DEMO_SEED"):
        return
    ensure_equipment_costing_schema(db)
    count = db.execute("SELECT COUNT(*) AS c FROM equipment_cost_entries").fetchone()["c"]
    if count > 0:
        return

    project = db.execute(
        "SELECT id FROM projects WHERE project_name LIKE '%Demo Highway%' "
        "OR status='Active' ORDER BY id LIMIT 1"
    ).fetchone()
    if not project:
        return
    project_id = project["id"]

    excavator = db.execute(
        "SELECT id FROM equipment_master WHERE reg_no='EX-01' OR equipment_type='Excavator' "
        "ORDER BY id LIMIT 1"
    ).fetchone()
    tipper = db.execute(
        "SELECT id FROM equipment_master WHERE reg_no='TK-01' OR equipment_type='Truck' "
        "ORDER BY id LIMIT 1"
    ).fetchone()
    ts = _now_ts()
    if not excavator:
        db.execute(
            """
            INSERT INTO equipment_master(
                equipment_code, reg_no, equipment_name, equipment_type, owner_type,
                hourly_rate, status, project_id, created_at, updated_at, updated_by
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "EX-01",
                "EX-01",
                "Excavator",
                "Excavator",
                "Company Owned",
                2500.0,
                "Active",
                project_id,
                ts,
                ts,
                "demo",
            ),
        )
        excavator = {"id": db.execute("SELECT last_insert_rowid()").fetchone()[0]}
    if not tipper:
        db.execute(
            """
            INSERT INTO equipment_master(
                equipment_code, reg_no, equipment_name, equipment_type, owner_type,
                km_rate, trip_rate, status, project_id, created_at, updated_at, updated_by
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "TK-01",
                "TK-01",
                "Tipper Truck",
                "Truck",
                "Hired Equipment",
                45.0,
                1500.0,
                "Active",
                project_id,
                ts,
                ts,
                "demo",
            ),
        )
        tipper = {"id": db.execute("SELECT last_insert_rowid()").fetchone()[0]}
    if not excavator or not tipper:
        return

    db.execute(
        "UPDATE equipment_master SET equipment_code=COALESCE(equipment_code, reg_no), project_id=? "
        "WHERE id IN (?, ?)",
        (project_id, excavator["id"], tipper["id"]),
    )

    demo_entries = (
        (
            excavator["id"],
            project_id,
            "2026-05",
            185_000,
            95_000,
            42_000,
            18_000,
            28_000,
            220,
            0,
            26,
            "May — excavation package; diesel spike on long haul.",
        ),
        (
            tipper["id"],
            project_id,
            "2026-05",
            142_000,
            72_000,
            25_000,
            35_000,
            12_000,
            0,
            4_800,
            26,
            "May — tipper fleet for muck disposal; tyre replacement on TK-01.",
        ),
    )
    for (
        eq_id,
        pid,
        period,
        fuel,
        operator,
        maint,
        tyre,
        spare,
        hours,
        km,
        days,
        notes,
    ) in demo_entries:
        metrics = _compute_cost_metrics(fuel, operator, maint, tyre, spare, hours, km, days)
        db.execute(
            """
            INSERT INTO equipment_cost_entries(
                equipment_id, project_id, period_month, fuel_cost, operator_cost,
                maintenance_cost, tyre_cost, spare_parts_cost, operating_hours,
                operating_km, operating_days, total_cost, cost_per_hour, cost_per_km,
                cost_per_day, notes, created_by, updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                eq_id,
                pid,
                period,
                fuel,
                operator,
                maint,
                tyre,
                spare,
                hours,
                km,
                days,
                metrics["total_cost"],
                metrics["cost_per_hour"],
                metrics["cost_per_km"],
                metrics["cost_per_day"],
                notes,
                "demo",
                ts,
            ),
        )
        entry_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        log_treasury_audit(
            db,
            "equipment_cost_entry",
            entry_id,
            "seeded",
            "demo",
            f"Demo equipment cost ({period}) for project #{project_id}",
        )

    sync_equipment_costs_to_project_budget(db, project_id)
