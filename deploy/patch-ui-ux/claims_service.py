"""Project claims & variation management — extra items, additional work, client claims, time extensions."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from contract_service import ensure_contract_schema, sync_project_contract_value
from document_numbering_service import integrate_next_number
from treasury_service import log_treasury_audit

CLAIM_TYPES = (
    "Extra Item",
    "Additional Work",
    "Client Claim",
    "Time Extension",
)
CLAIM_STATUSES = ("Submitted", "Under Review", "Approved", "Rejected")
CLAIM_STATUS_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "Submitted": ("Under Review", "Rejected"),
    "Under Review": ("Approved", "Rejected", "Submitted"),
    "Approved": (),
    "Rejected": ("Submitted",),
}


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


def ensure_claims_schema(db) -> None:
    """Idempotent project claims schema."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS project_claims(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            contract_id INTEGER,
            claim_number TEXT NOT NULL,
            claim_type TEXT NOT NULL,
            description TEXT,
            claimed_amount REAL DEFAULT 0,
            approved_amount REAL,
            submitted_date TEXT,
            status TEXT DEFAULT 'Submitted',
            remarks TEXT,
            created_by TEXT,
            updated_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id),
            FOREIGN KEY(contract_id) REFERENCES project_contracts(id)
        )
        """
    )
    if _table_exists(db, "project_claims"):
        cols = [r[1] for r in db.execute("PRAGMA table_info(project_claims)").fetchall()]
        for column, col_type in (
            ("project_id", "INTEGER"),
            ("contract_id", "INTEGER"),
            ("claim_number", "TEXT"),
            ("claim_type", "TEXT"),
            ("description", "TEXT"),
            ("claimed_amount", "REAL DEFAULT 0"),
            ("approved_amount", "REAL"),
            ("submitted_date", "TEXT"),
            ("status", "TEXT DEFAULT 'Submitted'"),
            ("remarks", "TEXT"),
            ("created_by", "TEXT"),
            ("updated_at", "TEXT"),
        ):
            if column not in cols:
                db.execute(f"ALTER TABLE project_claims ADD COLUMN {column} {col_type}")


def _enrich_claim_row(row: dict) -> dict:
    out = dict(row)
    out["claimed_amount"] = _round2(out.get("claimed_amount"))
    approved = out.get("approved_amount")
    out["approved_amount"] = _round2(approved) if approved is not None else None
    return out


def sync_claims_for_project(db, project_id: int) -> None:
    """Push approved claim totals into project_contracts.claims_value and sync contract value."""
    ensure_claims_schema(db)
    ensure_contract_schema(db)
    contracts = db.execute(
        "SELECT id FROM project_contracts WHERE project_id=?",
        (project_id,),
    ).fetchall()
    if not contracts:
        return
    main_row = db.execute(
        "SELECT id FROM project_contracts WHERE project_id=? AND contract_type='Main Agreement' "
        "ORDER BY id LIMIT 1",
        (project_id,),
    ).fetchone()
    main_id = main_row["id"] if main_row else None
    rows = db.execute(
        """
        SELECT contract_id, COALESCE(SUM(COALESCE(approved_amount, claimed_amount)), 0) AS total
        FROM project_claims
        WHERE project_id=? AND status='Approved'
        GROUP BY contract_id
        """,
        (project_id,),
    ).fetchall()
    totals: dict[int, float] = {}
    for row in rows:
        cid = row["contract_id"] if row["contract_id"] is not None else main_id
        if cid:
            totals[cid] = totals.get(cid, 0.0) + _round2(row["total"])
    ts = _now_ts()
    for contract in contracts:
        cid = contract["id"]
        db.execute(
            "UPDATE project_contracts SET claims_value=?, updated_at=? WHERE id=?",
            (totals.get(cid, 0.0), ts, cid),
        )
    sync_project_contract_value(db, project_id)


def list_claims(
    db,
    *,
    project_id: int | None = None,
    contract_id: int | None = None,
    claim_type: str | None = None,
    status: str | None = None,
    search: str | None = None,
) -> list[dict]:
    ensure_claims_schema(db)
    sql = (
        "SELECT pc.*, p.project_name, p.location, "
        "c.contract_number, c.contract_type "
        "FROM project_claims pc "
        "JOIN projects p ON pc.project_id = p.id "
        "LEFT JOIN project_contracts c ON pc.contract_id = c.id "
        "WHERE 1=1 "
    )
    params: list[Any] = []
    if project_id:
        sql += "AND pc.project_id=? "
        params.append(project_id)
    if contract_id:
        sql += "AND pc.contract_id=? "
        params.append(contract_id)
    if claim_type:
        sql += "AND pc.claim_type=? "
        params.append(claim_type)
    if status:
        sql += "AND pc.status=? "
        params.append(status)
    if search and search.strip():
        q = f"%{search.strip()}%"
        sql += "AND (pc.claim_number LIKE ? OR pc.description LIKE ? OR p.project_name LIKE ?) "
        params.extend([q, q, q])
    sql += "ORDER BY COALESCE(pc.submitted_date, pc.updated_at, '') DESC, pc.id DESC"
    rows = db.execute(sql, params).fetchall()
    return [_enrich_claim_row(dict(r)) for r in rows]


def get_claim(db, claim_id: int) -> dict | None:
    ensure_claims_schema(db)
    row = db.execute(
        """
        SELECT pc.*, p.project_name, p.location, p.status AS project_status,
               c.contract_number, c.contract_type
        FROM project_claims pc
        JOIN projects p ON pc.project_id = p.id
        LEFT JOIN project_contracts c ON pc.contract_id = c.id
        WHERE pc.id=?
        """,
        (claim_id,),
    ).fetchone()
    return _enrich_claim_row(dict(row)) if row else None


def list_project_contracts_for_claims(db, project_id: int) -> list[dict]:
    ensure_contract_schema(db)
    rows = db.execute(
        "SELECT id, contract_number, contract_type, status FROM project_contracts "
        "WHERE project_id=? ORDER BY contract_number",
        (project_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _validate_claim_form(form_data: dict, *, auto_number: str | None = None) -> dict:
    project_id = (form_data.get("project_id") or "").strip()
    if not project_id:
        raise ValueError("Select a project.")
    claim_number = (form_data.get("claim_number") or "").strip() or (auto_number or "").strip()
    if not claim_number:
        raise ValueError("Claim number is required.")
    claim_type = (form_data.get("claim_type") or "").strip()
    if claim_type not in CLAIM_TYPES:
        raise ValueError("Select a valid claim type.")
    status = (form_data.get("status") or "Submitted").strip()
    if status not in CLAIM_STATUSES:
        raise ValueError("Select a valid status.")
    contract_raw = (form_data.get("contract_id") or "").strip()
    contract_id = int(contract_raw) if contract_raw else None
    approved_raw = form_data.get("approved_amount")
    approved_amount = _round2(approved_raw) if approved_raw not in (None, "") else None
    return {
        "project_id": int(project_id),
        "contract_id": contract_id,
        "claim_number": claim_number,
        "claim_type": claim_type,
        "description": (form_data.get("description") or "").strip(),
        "claimed_amount": _round2(form_data.get("claimed_amount")),
        "approved_amount": approved_amount,
        "submitted_date": (form_data.get("submitted_date") or "").strip() or None,
        "status": status,
        "remarks": (form_data.get("remarks") or "").strip(),
    }


def create_claim(db, form_data: dict, username: str) -> int:
    ensure_claims_schema(db)
    claim_number = integrate_next_number(db, "bill_no", form_data.get("claim_number"))
    data = _validate_claim_form(form_data, auto_number=claim_number)
    project = db.execute("SELECT id FROM projects WHERE id=?", (data["project_id"],)).fetchone()
    if not project:
        raise ValueError("Project not found.")
    if data["contract_id"]:
        contract = db.execute(
            "SELECT id FROM project_contracts WHERE id=? AND project_id=?",
            (data["contract_id"], data["project_id"]),
        ).fetchone()
        if not contract:
            raise ValueError("Contract not found for this project.")
    ts = _now_ts()
    cur = db.execute(
        """
        INSERT INTO project_claims(
            project_id, contract_id, claim_number, claim_type, description,
            claimed_amount, approved_amount, submitted_date, status, remarks,
            created_by, updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            data["project_id"],
            data["contract_id"],
            data["claim_number"],
            data["claim_type"],
            data["description"],
            data["claimed_amount"],
            data["approved_amount"],
            data["submitted_date"],
            data["status"],
            data["remarks"],
            username,
            ts,
        ),
    )
    claim_id = cur.lastrowid
    if data["status"] == "Approved":
        sync_claims_for_project(db, data["project_id"])
    log_treasury_audit(
        db,
        "project_claim",
        claim_id,
        "created",
        username,
        f"{data['claim_type']} {data['claim_number']} for project #{data['project_id']}",
    )
    return claim_id


def update_claim(db, claim_id: int, form_data: dict, username: str) -> None:
    ensure_claims_schema(db)
    existing = get_claim(db, claim_id)
    if not existing:
        raise ValueError("Claim not found.")
    data = _validate_claim_form(form_data)
    if data["contract_id"]:
        contract = db.execute(
            "SELECT id FROM project_contracts WHERE id=? AND project_id=?",
            (data["contract_id"], data["project_id"]),
        ).fetchone()
        if not contract:
            raise ValueError("Contract not found for this project.")
    ts = _now_ts()
    db.execute(
        """
        UPDATE project_claims SET
            project_id=?, contract_id=?, claim_number=?, claim_type=?, description=?,
            claimed_amount=?, approved_amount=?, submitted_date=?, status=?, remarks=?,
            updated_at=?
        WHERE id=?
        """,
        (
            data["project_id"],
            data["contract_id"],
            data["claim_number"],
            data["claim_type"],
            data["description"],
            data["claimed_amount"],
            data["approved_amount"],
            data["submitted_date"],
            data["status"],
            data["remarks"],
            ts,
            claim_id,
        ),
    )
    if data["status"] == "Approved" or existing["status"] == "Approved":
        sync_claims_for_project(db, data["project_id"])
        if existing["project_id"] != data["project_id"]:
            sync_claims_for_project(db, existing["project_id"])
    log_treasury_audit(
        db,
        "project_claim",
        claim_id,
        "updated",
        username,
        f"{data['claim_type']} {data['claim_number']}",
    )


def allowed_claim_status_transitions(current_status: str) -> tuple[str, ...]:
    return CLAIM_STATUS_TRANSITIONS.get(current_status or "Submitted", ())


def update_claim_status(
    db,
    claim_id: int,
    new_status: str,
    username: str,
    *,
    approved_amount: float | None = None,
    remarks: str = "",
) -> int:
    if new_status not in CLAIM_STATUSES:
        raise ValueError(f"Invalid status: {new_status}")
    existing = get_claim(db, claim_id)
    if not existing:
        raise ValueError("Claim not found.")
    current = existing.get("status") or "Submitted"
    if new_status == current:
        raise ValueError("Claim is already in this status.")
    allowed = allowed_claim_status_transitions(current)
    if new_status not in allowed:
        raise ValueError(f"Cannot change status from {current} to {new_status}.")
    ts = _now_ts()
    new_remarks = remarks.strip() if remarks.strip() else existing.get("remarks") or ""
    approved_val = existing.get("approved_amount")
    if new_status == "Approved":
        if approved_amount is not None:
            approved_val = _round2(approved_amount)
        elif approved_val is None:
            approved_val = existing["claimed_amount"]
    db.execute(
        """
        UPDATE project_claims SET status=?, approved_amount=?, remarks=?, updated_at=?
        WHERE id=?
        """,
        (new_status, approved_val, new_remarks, ts, claim_id),
    )
    if new_status == "Approved" or current == "Approved":
        sync_claims_for_project(db, existing["project_id"])
    audit_details = f"{current} → {new_status}"
    if new_remarks:
        audit_details += f": {new_remarks}"
    if new_status == "Approved" and approved_val is not None:
        audit_details += f" (approved ₹{approved_val:,.2f})"
    log_treasury_audit(
        db,
        "project_claim",
        claim_id,
        "status_changed",
        username,
        audit_details,
    )
    return claim_id


def list_claim_audit(db, claim_id: int, limit: int = 15) -> list[dict]:
    rows = db.execute(
        "SELECT * FROM treasury_audit_log WHERE entity_type='project_claim' "
        "AND entity_id=? ORDER BY created_at DESC LIMIT ?",
        (claim_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def list_project_claim_audit(db, project_id: int, limit: int = 15) -> list[dict]:
    claim_ids = [
        r["id"]
        for r in db.execute(
            "SELECT id FROM project_claims WHERE project_id=?",
            (project_id,),
        ).fetchall()
    ]
    if not claim_ids:
        return []
    placeholders = ",".join("?" * len(claim_ids))
    rows = db.execute(
        f"SELECT * FROM treasury_audit_log WHERE entity_type='project_claim' "
        f"AND entity_id IN ({placeholders}) ORDER BY created_at DESC LIMIT ?",
        (*claim_ids, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get_claims_summary(db, claims: list[dict] | None = None) -> dict:
    rows = claims if claims is not None else list_claims(db)
    approved_total = _round2(
        sum(
            (c.get("approved_amount") if c.get("approved_amount") is not None else c["claimed_amount"])
            for c in rows
            if c.get("status") == "Approved"
        )
    )
    pending_total = _round2(
        sum(c["claimed_amount"] for c in rows if c.get("status") in ("Submitted", "Under Review"))
    )
    return {
        "claim_count": len(rows),
        "approved_total": approved_total,
        "pending_total": pending_total,
        "under_review_count": sum(1 for c in rows if c.get("status") == "Under Review"),
        "approved_count": sum(1 for c in rows if c.get("status") == "Approved"),
    }


def seed_claims_demo_data(db) -> None:
    if os.environ.get("MAXEK_SKIP_DEMO_SEED"):
        return
    ensure_claims_schema(db)
    ensure_contract_schema(db)
    count = db.execute("SELECT COUNT(*) AS c FROM project_claims").fetchone()["c"]
    if count > 0:
        return
    project = db.execute(
        "SELECT id FROM projects WHERE project_name LIKE '%Demo Highway%' "
        "OR status='Active' ORDER BY id LIMIT 1"
    ).fetchone()
    if not project:
        return
    project_id = project["id"]
    contract = db.execute(
        "SELECT id FROM project_contracts WHERE project_id=? ORDER BY id LIMIT 1",
        (project_id,),
    ).fetchone()
    contract_id = contract["id"] if contract else None
    ts = _now_ts()
    db.execute(
        """
        INSERT INTO project_claims(
            project_id, contract_id, claim_number, claim_type, description,
            claimed_amount, approved_amount, submitted_date, status, remarks,
            created_by, updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            project_id,
            contract_id,
            "CLM-DEMO-2026-001",
            "Extra Item",
            "Extra item — additional culvert wing walls beyond BOQ scope",
            850_000,
            None,
            "2026-04-10",
            "Under Review",
            "Submitted with site measurement sheets and photos.",
            "demo",
            ts,
        ),
    )
    review_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.execute(
        """
        INSERT INTO project_claims(
            project_id, contract_id, claim_number, claim_type, description,
            claimed_amount, approved_amount, submitted_date, status, remarks,
            created_by, updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            project_id,
            contract_id,
            "CLM-DEMO-2026-002",
            "Additional Work",
            "Additional work — traffic diversion and barricading for monsoon season",
            420_000,
            380_000,
            "2026-03-15",
            "Approved",
            "Client approved at negotiated amount.",
            "demo",
            ts,
        ),
    )
    approved_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    sync_claims_for_project(db, project_id)
    for cid, label in ((review_id, "Under Review"), (approved_id, "Approved")):
        log_treasury_audit(
            db,
            "project_claim",
            cid,
            "seeded",
            "demo",
            f"Demo claim ({label}) for Demo Highway (project #{project_id})",
        )
