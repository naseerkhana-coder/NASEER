"""Project contract management — agreements, work orders, amendments, variations."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from treasury_service import log_treasury_audit

CONTRACT_TYPES = (
    "Main Agreement",
    "Work Order",
    "Amendment",
    "Variation",
)
CONTRACT_STATUSES = ("Draft", "Active", "Superseded", "Closed")


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


def ensure_contract_schema(db) -> None:
    """Idempotent project contracts schema."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS project_contracts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            contract_number TEXT NOT NULL,
            contract_type TEXT NOT NULL,
            original_value REAL DEFAULT 0,
            revised_value REAL DEFAULT 0,
            extra_items_value REAL DEFAULT 0,
            claims_value REAL DEFAULT 0,
            effective_date TEXT,
            status TEXT DEFAULT 'Active',
            description TEXT,
            document_ref TEXT,
            created_by TEXT,
            updated_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
        """
    )
    if _table_exists(db, "project_contracts"):
        cols = [r[1] for r in db.execute("PRAGMA table_info(project_contracts)").fetchall()]
        for column, col_type in (
            ("project_id", "INTEGER"),
            ("contract_number", "TEXT"),
            ("contract_type", "TEXT"),
            ("original_value", "REAL DEFAULT 0"),
            ("revised_value", "REAL DEFAULT 0"),
            ("extra_items_value", "REAL DEFAULT 0"),
            ("claims_value", "REAL DEFAULT 0"),
            ("effective_date", "TEXT"),
            ("status", "TEXT DEFAULT 'Active'"),
            ("description", "TEXT"),
            ("document_ref", "TEXT"),
            ("created_by", "TEXT"),
            ("updated_at", "TEXT"),
        ):
            if column not in cols:
                db.execute(f"ALTER TABLE project_contracts ADD COLUMN {column} {col_type}")


def _enrich_contract_row(row: dict) -> dict:
    out = dict(row)
    out["original_value"] = _round2(out.get("original_value"))
    out["revised_value"] = _round2(out.get("revised_value"))
    out["extra_items_value"] = _round2(out.get("extra_items_value"))
    out["claims_value"] = _round2(out.get("claims_value"))
    return out


def _compute_revised_total(contracts: list[dict]) -> float:
    """Derive effective revised contract value from contract history."""
    main_rows = [c for c in contracts if c.get("contract_type") == "Main Agreement"]
    active = [c for c in contracts if (c.get("status") or "Active") != "Superseded"]
    if not active:
        active = contracts
    base = 0.0
    if main_rows:
        main = main_rows[0]
        base = _safe_float(main.get("revised_value")) or _safe_float(main.get("original_value"))
    for row in active:
        ctype = row.get("contract_type")
        if ctype == "Main Agreement":
            continue
        if ctype == "Amendment":
            delta = _safe_float(row.get("revised_value")) - _safe_float(row.get("original_value"))
            base += delta
        elif ctype == "Variation":
            base += _safe_float(row.get("extra_items_value")) or _safe_float(row.get("revised_value"))
        elif ctype == "Work Order":
            base += _safe_float(row.get("revised_value")) or _safe_float(row.get("original_value"))
    return _round2(base)


def get_project_contract_summary(db, project_id: int) -> dict:
    """Original vs revised totals, extra items, and claims for a project."""
    ensure_contract_schema(db)
    rows = db.execute(
        """
        SELECT pc.*, p.project_name
        FROM project_contracts pc
        JOIN projects p ON pc.project_id = p.id
        WHERE pc.project_id=?
        ORDER BY COALESCE(pc.effective_date, pc.updated_at, '') ASC, pc.id ASC
        """,
        (project_id,),
    ).fetchall()
    contracts = [_enrich_contract_row(dict(r)) for r in rows]
    main_rows = [c for c in contracts if c["contract_type"] == "Main Agreement"]
    original_total = _round2(
        sum(c["original_value"] for c in main_rows)
        if main_rows
        else sum(c["original_value"] for c in contracts)
    )
    extra_items_total = _round2(sum(c["extra_items_value"] for c in contracts))
    claims_total = _round2(sum(c["claims_value"] for c in contracts))
    revised_total = _compute_revised_total(contracts)
    return {
        "project_id": project_id,
        "contract_count": len(contracts),
        "original_total": original_total,
        "revised_total": revised_total,
        "extra_items_total": extra_items_total,
        "claims_total": claims_total,
        "delta": _round2(revised_total - original_total),
        "contracts": contracts,
    }


def sync_project_contract_value(db, project_id: int) -> float | None:
    """Push revised contract total to projects.approved_total_amount when contracts exist."""
    ensure_contract_schema(db)
    count = db.execute(
        "SELECT COUNT(*) AS c FROM project_contracts WHERE project_id=?",
        (project_id,),
    ).fetchone()["c"]
    if count == 0:
        return None
    summary = get_project_contract_summary(db, project_id)
    revised = summary["revised_total"]
    if revised <= 0:
        return None
    cols = [r[1] for r in db.execute("PRAGMA table_info(projects)").fetchall()]
    if "approved_total_amount" not in cols:
        return revised
    db.execute(
        "UPDATE projects SET approved_total_amount=? WHERE id=?",
        (revised, project_id),
    )
    return revised


def list_contracts(
    db,
    *,
    project_id: int | None = None,
    contract_type: str | None = None,
    status: str | None = None,
    search: str | None = None,
) -> list[dict]:
    ensure_contract_schema(db)
    sql = (
        "SELECT pc.*, p.project_name, p.location, p.status AS project_status "
        "FROM project_contracts pc "
        "JOIN projects p ON pc.project_id = p.id WHERE 1=1 "
    )
    params: list[Any] = []
    if project_id:
        sql += "AND pc.project_id=? "
        params.append(project_id)
    if contract_type:
        sql += "AND pc.contract_type=? "
        params.append(contract_type)
    if status:
        sql += "AND pc.status=? "
        params.append(status)
    if search and search.strip():
        q = f"%{search.strip()}%"
        sql += "AND (pc.contract_number LIKE ? OR pc.description LIKE ? OR p.project_name LIKE ?) "
        params.extend([q, q, q])
    sql += "ORDER BY COALESCE(pc.effective_date, pc.updated_at, '') DESC, pc.id DESC"
    rows = db.execute(sql, params).fetchall()
    return [_enrich_contract_row(dict(r)) for r in rows]


def get_contract(db, contract_id: int) -> dict | None:
    ensure_contract_schema(db)
    row = db.execute(
        """
        SELECT pc.*, p.project_name, p.location, p.status AS project_status,
               p.approved_total_amount, p.budget
        FROM project_contracts pc
        JOIN projects p ON pc.project_id = p.id
        WHERE pc.id=?
        """,
        (contract_id,),
    ).fetchone()
    return _enrich_contract_row(dict(row)) if row else None


def _validate_contract_form(form_data: dict, *, record_id: int | None = None) -> dict:
    project_id = form_data.get("project_id", "").strip()
    if not project_id:
        raise ValueError("Select a project.")
    contract_number = (form_data.get("contract_number") or "").strip()
    if not contract_number:
        raise ValueError("Contract number is required.")
    contract_type = (form_data.get("contract_type") or "").strip()
    if contract_type not in CONTRACT_TYPES:
        raise ValueError("Select a valid contract type.")
    status = (form_data.get("status") or "Active").strip()
    if status not in CONTRACT_STATUSES:
        raise ValueError("Select a valid status.")
    return {
        "project_id": int(project_id),
        "contract_number": contract_number,
        "contract_type": contract_type,
        "original_value": _round2(form_data.get("original_value")),
        "revised_value": _round2(form_data.get("revised_value")),
        "extra_items_value": _round2(form_data.get("extra_items_value")),
        "claims_value": _round2(form_data.get("claims_value")),
        "effective_date": (form_data.get("effective_date") or "").strip() or None,
        "status": status,
        "description": (form_data.get("description") or "").strip(),
        "document_ref": (form_data.get("document_ref") or "").strip(),
    }


def create_contract(db, form_data: dict, username: str) -> int:
    ensure_contract_schema(db)
    data = _validate_contract_form(form_data)
    project = db.execute("SELECT id FROM projects WHERE id=?", (data["project_id"],)).fetchone()
    if not project:
        raise ValueError("Project not found.")
    ts = _now_ts()
    cur = db.execute(
        """
        INSERT INTO project_contracts(
            project_id, contract_number, contract_type, original_value, revised_value,
            extra_items_value, claims_value, effective_date, status, description,
            document_ref, created_by, updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            data["project_id"],
            data["contract_number"],
            data["contract_type"],
            data["original_value"],
            data["revised_value"],
            data["extra_items_value"],
            data["claims_value"],
            data["effective_date"],
            data["status"],
            data["description"],
            data["document_ref"],
            username,
            ts,
        ),
    )
    contract_id = cur.lastrowid
    sync_project_contract_value(db, data["project_id"])
    log_treasury_audit(
        db,
        "project_contract",
        contract_id,
        "created",
        username,
        f"{data['contract_type']} {data['contract_number']} for project #{data['project_id']}",
    )
    return contract_id


def update_contract(db, contract_id: int, form_data: dict, username: str) -> None:
    ensure_contract_schema(db)
    existing = get_contract(db, contract_id)
    if not existing:
        raise ValueError("Contract not found.")
    data = _validate_contract_form(form_data, record_id=contract_id)
    ts = _now_ts()
    db.execute(
        """
        UPDATE project_contracts SET
            project_id=?, contract_number=?, contract_type=?, original_value=?,
            revised_value=?, extra_items_value=?, claims_value=?, effective_date=?,
            status=?, description=?, document_ref=?, updated_at=?
        WHERE id=?
        """,
        (
            data["project_id"],
            data["contract_number"],
            data["contract_type"],
            data["original_value"],
            data["revised_value"],
            data["extra_items_value"],
            data["claims_value"],
            data["effective_date"],
            data["status"],
            data["description"],
            data["document_ref"],
            ts,
            contract_id,
        ),
    )
    sync_project_contract_value(db, data["project_id"])
    if existing["project_id"] != data["project_id"]:
        sync_project_contract_value(db, existing["project_id"])
    log_treasury_audit(
        db,
        "project_contract",
        contract_id,
        "updated",
        username,
        f"{data['contract_type']} {data['contract_number']}",
    )


def list_contract_audit(db, contract_id: int, limit: int = 15) -> list[dict]:
    rows = db.execute(
        "SELECT * FROM treasury_audit_log WHERE entity_type='project_contract' "
        "AND entity_id=? ORDER BY created_at DESC LIMIT ?",
        (contract_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def list_project_contract_audit(db, project_id: int, limit: int = 15) -> list[dict]:
    rows = db.execute(
        """
        SELECT * FROM treasury_audit_log
        WHERE entity_type='project_contract'
        AND details LIKE ?
        ORDER BY created_at DESC LIMIT ?
        """,
        (f"%project #{project_id}%", limit),
    ).fetchall()
    contract_ids = [
        r["id"]
        for r in db.execute(
            "SELECT id FROM project_contracts WHERE project_id=?",
            (project_id,),
        ).fetchall()
    ]
    if contract_ids:
        placeholders = ",".join("?" * len(contract_ids))
        rows = db.execute(
            f"SELECT * FROM treasury_audit_log WHERE entity_type='project_contract' "
            f"AND entity_id IN ({placeholders}) ORDER BY created_at DESC LIMIT ?",
            (*contract_ids, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_effective_contract_value(db, project_id: int) -> float:
    """Contract value for profitability — prefers contract register over project fields."""
    ensure_contract_schema(db)
    count = db.execute(
        "SELECT COUNT(*) AS c FROM project_contracts WHERE project_id=?",
        (project_id,),
    ).fetchone()["c"]
    if count > 0:
        return get_project_contract_summary(db, project_id)["revised_total"]
    row = db.execute(
        "SELECT approved_total_amount, quoted_amount, work_order_amount, budget "
        "FROM projects WHERE id=?",
        (project_id,),
    ).fetchone()
    if not row:
        return 0.0
    for key in ("approved_total_amount", "quoted_amount", "work_order_amount", "budget"):
        val = row[key]
        if val is not None and _safe_float(val) > 0:
            return _round2(val)
    return 0.0


def seed_contract_demo_data(db) -> None:
    if os.environ.get("MAXEK_SKIP_DEMO_SEED"):
        return
    ensure_contract_schema(db)
    count = db.execute("SELECT COUNT(*) AS c FROM project_contracts").fetchone()["c"]
    if count > 0:
        return
    project = db.execute(
        "SELECT id, budget FROM projects WHERE project_name LIKE '%Demo Highway%' "
        "OR status='Active' ORDER BY id LIMIT 1"
    ).fetchone()
    if not project:
        return
    project_id = project["id"]
    budget = _safe_float(project["budget"]) or 25_000_000
    ts = _now_ts()
    db.execute(
        """
        INSERT INTO project_contracts(
            project_id, contract_number, contract_type, original_value, revised_value,
            extra_items_value, claims_value, effective_date, status, description,
            document_ref, created_by, updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            project_id,
            "MH-AGR-2026-001",
            "Main Agreement",
            budget,
            budget,
            0,
            0,
            "2026-01-15",
            "Active",
            "Main contract agreement — Demo Highway Phase-1 civil works",
            "AGR/DEMO-HWY/2026",
            "demo",
            ts,
        ),
    )
    main_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.execute(
        """
        INSERT INTO project_contracts(
            project_id, contract_number, contract_type, original_value, revised_value,
            extra_items_value, claims_value, effective_date, status, description,
            document_ref, created_by, updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            project_id,
            "MH-VAR-2026-001",
            "Variation",
            0,
            1_500_000,
            1_500_000,
            0,
            "2026-03-01",
            "Active",
            "Variation Order — additional drainage & kerb works",
            "VAR/DEMO-HWY/001",
            "demo",
            ts,
        ),
    )
    var_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    sync_project_contract_value(db, project_id)
    for cid, label in ((main_id, "Main Agreement"), (var_id, "Variation Order")):
        log_treasury_audit(
            db,
            "project_contract",
            cid,
            "seeded",
            "demo",
            f"Demo {label} for Demo Highway Phase-1 (project #{project_id})",
        )
