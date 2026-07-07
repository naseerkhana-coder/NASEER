"""Workflow Engine (MODULE-007) — configurable Maker → Checker → Approver master module."""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any

from company_master_service import _ensure_column, _now_ts, _table_exists
from designation_master_service import ensure_designation_master_schema
from workflow_service import (
    DEFAULT_WORKFLOW_MODE,
    DEFAULT_MODULES,
    RECORD_APPROVED,
    RECORD_PENDING_APPROVAL,
    RECORD_PENDING_CHECKER,
    RECORD_REJECTED_APPROVER,
    RECORD_REJECTED_CHECKER,
    STATUS_APPROVED,
    STATUS_PENDING_APPROVAL,
    STATUS_PENDING_CHECKER,
    STATUS_REJECTED_APPROVER,
    STATUS_REJECTED_CHECKER,
    WORKFLOW_MODES,
    WORKFLOW_MODE_LABELS,
    WORKFLOW_STATUS,
    advance_approval,
    create_notification,
    get_approval_history,
    get_approval_request_by_id,
    get_approval_summary,
    get_pending_items,
    get_user_designation_id,
    get_user_workflow_role,
    get_workflow_for_module,
    reopen_transaction,
    resubmit_record,
    seed_workflow_master,
    sync_workflow_designations,
    user_matches_stage,
    workflow_mode_requires_approver,
    workflow_mode_requires_checker,
)

WORKFLOW_STATUSES = ("Active", "Inactive")
STAGE_TYPES = ("Maker", "Checker", "Approver")
WORKFLOW_SORT_COLUMNS = (
    "workflow_code",
    "workflow_name",
    "module_name",
    "module_id",
    "status",
    "created_at",
)
WORKFLOW_AUDIT_FIELDS = (
    "workflow_code",
    "workflow_name",
    "module_name",
    "module_id",
    "description",
    "workflow_mode",
    "status",
)
WORKFLOW_PERMISSION_ROLES = (
    "Workflow Admin",
    "Workflow Manager",
    "Checker",
    "Approver",
    "Viewer",
)

MODULE_007_SEEDS: tuple[dict[str, str], ...] = (
    {"module_id": "purchase_request", "workflow_code": "WF-PR", "workflow_name": "Purchase Request"},
    {"module_id": "material_request", "workflow_code": "WF-MR", "workflow_name": "Material Request"},
    {"module_id": "store_issue", "workflow_code": "WF-SI", "workflow_name": "Store Issue"},
    {"module_id": "store_receipt", "workflow_code": "WF-SR", "workflow_name": "Store Receipt"},
    {"module_id": "petty_cash", "workflow_code": "WF-PC", "workflow_name": "Petty Cash"},
    {"module_id": "payroll", "workflow_code": "WF-PAY", "workflow_name": "Payroll"},
    {"module_id": "monthly_staff_attendance", "workflow_code": "WF-ATT", "workflow_name": "Attendance"},
    {"module_id": "leave_request", "workflow_code": "WF-LV", "workflow_name": "Leave"},
    {"module_id": "project_expenses", "workflow_code": "WF-PEX", "workflow_name": "Project Expense"},
    {"module_id": "head_office_expenses", "workflow_code": "WF-HOX", "workflow_name": "HO Expense"},
    {"module_id": "subcontractor_billing", "workflow_code": "WF-SCB", "workflow_name": "Subcontract Bill"},
    {"module_id": "purchase_order", "workflow_code": "WF-PO", "workflow_name": "Purchase Order Approval"},
)

_DEFAULT_MODULE_LOOKUP = {m["module_id"]: m for m in DEFAULT_MODULES}


def ensure_workflow_engine_schema(db) -> None:
    """Extend workflow tables for MODULE-007 (idempotent)."""
    ensure_designation_master_schema(db)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS workflows(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_code TEXT,
            workflow_name TEXT NOT NULL,
            module_name TEXT NOT NULL,
            module_id TEXT UNIQUE NOT NULL,
            description TEXT,
            workflow_mode TEXT,
            status TEXT DEFAULT 'Active',
            created_by TEXT,
            created_at TEXT,
            modified_by TEXT,
            modified_at TEXT,
            is_deleted INTEGER DEFAULT 0,
            deleted_by TEXT,
            deleted_at TEXT,
            customer_id INTEGER
        )
        """
    )
    for col, ctype in (
        ("workflow_code", "TEXT"),
        ("description", "TEXT"),
        ("workflow_mode", f"TEXT DEFAULT '{DEFAULT_WORKFLOW_MODE}'"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT"),
        ("modified_by", "TEXT"),
        ("modified_at", "TEXT"),
        ("is_deleted", "INTEGER DEFAULT 0"),
        ("deleted_by", "TEXT"),
        ("deleted_at", "TEXT"),
        ("customer_id", "INTEGER"),
    ):
        _ensure_column(db, "workflows", col, ctype)

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS workflow_stages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id INTEGER NOT NULL,
            stage_number INTEGER NOT NULL,
            stage_name TEXT,
            stage_type TEXT NOT NULL,
            designation_id INTEGER,
            role_id INTEGER,
            sequence INTEGER NOT NULL,
            approval_required INTEGER DEFAULT 1,
            reject_allowed INTEGER DEFAULT 1,
            remarks_required INTEGER DEFAULT 0,
            notification_enabled INTEGER DEFAULT 1,
            escalation_enabled INTEGER DEFAULT 0,
            escalation_hours INTEGER DEFAULT 24,
            created_by TEXT,
            created_at TEXT,
            modified_by TEXT,
            modified_at TEXT,
            FOREIGN KEY(workflow_id) REFERENCES workflows(id),
            FOREIGN KEY(designation_id) REFERENCES designations(id)
        )
        """
    )
    for col, ctype in (
        ("role_id", "INTEGER"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT"),
        ("modified_by", "TEXT"),
        ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "workflow_stages", col, ctype)

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS workflow_rules(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id INTEGER NOT NULL,
            rule_key TEXT NOT NULL,
            rule_value TEXT,
            is_active INTEGER DEFAULT 1,
            created_by TEXT,
            created_at TEXT,
            FOREIGN KEY(workflow_id) REFERENCES workflows(id),
            UNIQUE(workflow_id, rule_key)
        )
        """
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS workflow_assignments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id INTEGER NOT NULL,
            stage_type TEXT NOT NULL,
            user_id INTEGER,
            designation_id INTEGER,
            department_id INTEGER,
            company_id INTEGER,
            priority INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Active',
            created_by TEXT,
            created_at TEXT,
            FOREIGN KEY(workflow_id) REFERENCES workflows(id)
        )
        """
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS workflow_escalation_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            approval_request_id INTEGER NOT NULL,
            workflow_id INTEGER,
            stage_type TEXT,
            escalated_at TEXT NOT NULL,
            notified_user_ids TEXT,
            remarks TEXT
        )
        """
    )

    try:
        from audit_trail_service import ensure_audit_schema

        ensure_audit_schema(db)
    except Exception:
        pass

    _migrate_workflow_master_to_engine(db)


def _migrate_workflow_master_to_engine(db) -> None:
    """One-time sync from legacy workflow_master into workflows + stages."""
    if not _table_exists(db, "workflow_master"):
        return
    rows = db.execute(
        "SELECT * FROM workflow_master ORDER BY module_name"
    ).fetchall()
    for row in rows:
        row = dict(row)
        module_id = row.get("module_id")
        if not module_id:
            continue
        existing = db.execute(
            "SELECT id FROM workflows WHERE module_id=?", (module_id,)
        ).fetchone()
        wf_mode = (row.get("workflow_mode") or DEFAULT_WORKFLOW_MODE).strip()
        if wf_mode not in WORKFLOW_MODES:
            wf_mode = DEFAULT_WORKFLOW_MODE
        code = _default_workflow_code(module_id)
        if existing:
            wf_id = int(existing[0])
            db.execute(
                """
                UPDATE workflows SET workflow_name=?, module_name=?, workflow_mode=?,
                status=COALESCE(?, status)
                WHERE id=?
                """,
                (
                    row.get("module_name") or module_id,
                    row.get("module_name") or module_id,
                    wf_mode,
                    row.get("status") or "Active",
                    wf_id,
                ),
            )
        else:
            db.execute(
                """
                INSERT INTO workflows(
                    workflow_code, workflow_name, module_name, module_id,
                    description, workflow_mode, status, created_at
                ) VALUES(?,?,?,?,?,?,?,?)
                """,
                (
                    code,
                    row.get("module_name") or module_id,
                    row.get("module_name") or module_id,
                    module_id,
                    row.get("workflow_role_mapping"),
                    wf_mode,
                    row.get("status") or "Active",
                    _now_ts(),
                ),
            )
            wf_id = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])
        _sync_stages_from_master_row(db, wf_id, row)


def _default_workflow_code(module_id: str) -> str:
    for seed in MODULE_007_SEEDS:
        if seed["module_id"] == module_id:
            return seed["workflow_code"]
    slug = re.sub(r"[^A-Z0-9]", "", module_id.upper())[:6]
    return f"WF-{slug or 'MOD'}"


def _sync_stages_from_master_row(db, workflow_id: int, master_row: dict[str, Any]) -> None:
    db.execute("DELETE FROM workflow_stages WHERE workflow_id=?", (workflow_id,))
    stages = (
        ("Maker", 1, master_row.get("maker_designation_id")),
        ("Checker", 2, master_row.get("checker_designation_id")),
        ("Approver", 3, master_row.get("approver_designation_id")),
    )
    now = _now_ts()
    for stage_type, seq, desig_id in stages:
        if not desig_id and stage_type != "Maker":
            continue
        db.execute(
            """
            INSERT INTO workflow_stages(
                workflow_id, stage_number, stage_name, stage_type, designation_id,
                sequence, approval_required, reject_allowed, remarks_required,
                notification_enabled, escalation_enabled, escalation_hours, created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                workflow_id,
                seq,
                stage_type,
                stage_type,
                desig_id,
                seq,
                1,
                1 if stage_type != "Maker" else 0,
                1 if stage_type != "Maker" else 0,
                1,
                0,
                24,
                now,
            ),
        )


def sync_engine_to_workflow_master(db, workflow_id: int) -> None:
    """Push workflows + stages back to workflow_master for runtime compatibility."""
    wf = get_workflow_engine(db, workflow_id)
    if not wf:
        return
    stages = {s["stage_type"]: s for s in wf.get("stages", [])}
    maker_id = stages.get("Maker", {}).get("designation_id")
    checker_id = stages.get("Checker", {}).get("designation_id")
    approver_id = stages.get("Approver", {}).get("designation_id")
    parts = []
    for st in ("Maker", "Checker", "Approver"):
        name = stages.get(st, {}).get("designation_name")
        if name:
            parts.append(name)
    flow = " → ".join(parts) if parts else wf.get("description") or wf["module_name"]
    module_id = wf["module_id"]
    existing = db.execute(
        "SELECT id FROM workflow_master WHERE module_id=?", (module_id,)
    ).fetchone()
    mode = wf.get("workflow_mode") or DEFAULT_WORKFLOW_MODE
    status = wf.get("status") or "Active"
    if existing:
        db.execute(
            """
            UPDATE workflow_master SET module_name=?, workflow_role_mapping=?,
            maker_designation_id=?, checker_designation_id=?, approver_designation_id=?,
            workflow_mode=?, status=? WHERE module_id=?
            """,
            (
                wf["module_name"],
                flow,
                maker_id,
                checker_id,
                approver_id,
                mode,
                status,
                module_id,
            ),
        )
    else:
        db.execute(
            """
            INSERT INTO workflow_master(
                module_name, module_id, workflow_role_mapping,
                maker_designation_id, checker_designation_id, approver_designation_id,
                workflow_mode, status
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                wf["module_name"],
                module_id,
                flow,
                maker_id,
                checker_id,
                approver_id,
                mode,
                status,
            ),
        )


def seed_workflow_engine(db) -> None:
    """Seed MODULE-007 workflows and sync with workflow_master."""
    ensure_workflow_engine_schema(db)
    seed_workflow_master(db)
    sync_workflow_designations(db)
    for seed in MODULE_007_SEEDS:
        module_id = seed["module_id"]
        meta = _DEFAULT_MODULE_LOOKUP.get(module_id, {})
        module_name = meta.get("module_name") or seed["workflow_name"]
        existing = db.execute(
            "SELECT id FROM workflows WHERE module_id=?", (module_id,)
        ).fetchone()
        if existing:
            continue
        db.execute(
            """
            INSERT INTO workflows(
                workflow_code, workflow_name, module_name, module_id,
                description, workflow_mode, status, created_at, created_by
            ) VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (
                seed["workflow_code"],
                seed["workflow_name"],
                module_name,
                module_id,
                meta.get("workflow_role_mapping"),
                DEFAULT_WORKFLOW_MODE,
                "Active",
                _now_ts(),
                "system",
            ),
        )
        wf_id = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])
        master = db.execute(
            "SELECT * FROM workflow_master WHERE module_id=?", (module_id,)
        ).fetchone()
        if master:
            _sync_stages_from_master_row(db, wf_id, dict(master))
        sync_engine_to_workflow_master(db, wf_id)


def log_workflow_engine_audit(
    db,
    workflow_id: int,
    action: str,
    username: str,
    *,
    field_name: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
    remarks: str | None = None,
) -> None:
    try:
        from audit_trail_service import log_audit_event

        log_audit_event(
            db,
            record_table="workflows",
            record_id=workflow_id,
            action=action,
            changed_by=username,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            remarks=remarks,
        )
    except Exception:
        pass


def list_workflow_engine_audit(db, workflow_id: int, limit: int = 100) -> list[dict[str, Any]]:
    try:
        from audit_trail_service import list_audit_trail

        return list_audit_trail(db, "workflows", workflow_id, limit=limit)
    except Exception:
        return []


def workflow_has_usage(db, workflow_id: int) -> bool:
    wf = db.execute(
        "SELECT module_id FROM workflows WHERE id=?", (workflow_id,)
    ).fetchone()
    if not wf:
        return False
    row = db.execute(
        "SELECT COUNT(*) AS c FROM approval_requests WHERE module_id=?",
        (wf["module_id"],),
    ).fetchone()
    return bool(row and int(row["c"]) > 0)


def validate_workflow_stages(stages: list[dict[str, Any]], workflow_mode: str) -> None:
    if not stages:
        raise ValueError("At least one workflow stage is required.")
    if len(stages) > 3:
        raise ValueError("Maximum 3 stages allowed (Maker, Checker, Approver).")
    types = [s.get("stage_type") for s in stages]
    if "Maker" not in types:
        raise ValueError("Maker stage is required.")
    makers = [s for s in stages if s.get("stage_type") == "Maker"]
    checkers = [s for s in stages if s.get("stage_type") == "Checker"]
    approvers = [s for s in stages if s.get("stage_type") == "Approver"]
    if len(makers) != 1:
        raise ValueError("Exactly one Maker stage is required.")
    maker_desig = makers[0].get("designation_id")
    if not maker_desig:
        raise ValueError("Maker designation is required.")
    if workflow_mode_requires_checker(workflow_mode):
        if not checkers:
            raise ValueError("Checker stage is required for this workflow mode.")
        checker_desig = checkers[0].get("designation_id")
        if not checker_desig:
            raise ValueError("Checker designation is required.")
        if checker_desig == maker_desig:
            raise ValueError("Checker cannot be the same designation as Maker.")
    if workflow_mode_requires_approver(workflow_mode):
        if not approvers:
            raise ValueError("Approver stage is required for this workflow mode.")
        approver_desig = approvers[0].get("designation_id")
        if not approver_desig:
            raise ValueError("Approver designation is required.")
        if approver_desig == maker_desig:
            raise ValueError("Approver cannot be the same designation as Maker.")
        if checkers and approvers[0].get("designation_id") == checkers[0].get("designation_id"):
            raise ValueError("Approver cannot be the same designation as Checker.")


def _parse_workflow_form(form: dict[str, Any]) -> dict[str, Any]:
    mode = (form.get("workflow_mode") or DEFAULT_WORKFLOW_MODE).strip()
    if mode not in WORKFLOW_MODES:
        mode = DEFAULT_WORKFLOW_MODE
    return {
        "workflow_code": (form.get("workflow_code") or "").strip(),
        "workflow_name": (form.get("workflow_name") or "").strip(),
        "module_name": (form.get("module_name") or "").strip(),
        "module_id": (form.get("module_id") or "").strip().lower().replace(" ", "_"),
        "description": (form.get("description") or "").strip(),
        "workflow_mode": mode,
        "status": (form.get("status") or "Active").strip(),
    }


def _parse_stages_from_form(form: dict[str, Any]) -> list[dict[str, Any]]:
    raw = form.get("stages")
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    stages: list[dict[str, Any]] = []
    for stage_type, seq in (("Maker", 1), ("Checker", 2), ("Approver", 3)):
        desig_key = f"{stage_type.lower()}_designation_id"
        desig = form.get(desig_key)
        if desig in (None, "", "0") and stage_type == "Maker":
            continue
        if desig in (None, "", "0") and stage_type != "Maker":
            continue
        stages.append(
            {
                "stage_type": stage_type,
                "stage_number": seq,
                "stage_name": stage_type,
                "sequence": seq,
                "designation_id": int(desig) if desig else None,
                "approval_required": form.get(f"{stage_type.lower()}_approval_required", "1") in ("1", 1, True, "on"),
                "reject_allowed": form.get(f"{stage_type.lower()}_reject_allowed", "1") in ("1", 1, True, "on"),
                "remarks_required": form.get(f"{stage_type.lower()}_remarks_required") in ("1", 1, True, "on"),
                "notification_enabled": form.get(f"{stage_type.lower()}_notification_enabled", "1") not in ("0", 0, False, ""),
                "escalation_enabled": form.get(f"{stage_type.lower()}_escalation_enabled") in ("1", 1, True, "on"),
                "escalation_hours": int(form.get(f"{stage_type.lower()}_escalation_hours") or 24),
            }
        )
    return stages


def save_workflow_engine(
    db,
    form: dict[str, Any],
    username: str,
    workflow_id: int | None = None,
    *,
    customer_id: int | None = None,
) -> int:
    data = _parse_workflow_form(form)
    if not data["workflow_name"]:
        raise ValueError("Workflow name is required.")
    if not data["module_id"]:
        raise ValueError("Module ID is required.")
    if not data["module_name"]:
        data["module_name"] = data["workflow_name"]
    if not data["workflow_code"]:
        data["workflow_code"] = _default_workflow_code(data["module_id"])
    stages = _parse_stages_from_form(form)
    validate_workflow_stages(stages, data["workflow_mode"])
    now = _now_ts()
    dup = db.execute(
        """
        SELECT id FROM workflows
        WHERE module_id=? AND COALESCE(is_deleted,0)=0
        """,
        (data["module_id"],),
    ).fetchone()
    if dup and (not workflow_id or int(dup[0]) != int(workflow_id)):
        raise ValueError(f"Workflow for module '{data['module_id']}' already exists.")
    code_dup = db.execute(
        """
        SELECT id FROM workflows
        WHERE UPPER(workflow_code)=UPPER(?) AND COALESCE(is_deleted,0)=0
        """,
        (data["workflow_code"],),
    ).fetchone()
    if code_dup and (not workflow_id or int(code_dup[0]) != int(workflow_id)):
        raise ValueError(f"Workflow code '{data['workflow_code']}' is already in use.")
    before = get_workflow_engine(db, workflow_id) if workflow_id else None
    if workflow_id:
        db.execute(
            """
            UPDATE workflows SET workflow_code=?, workflow_name=?, module_name=?, module_id=?,
            description=?, workflow_mode=?, status=?, modified_by=?, modified_at=?
            WHERE id=? AND COALESCE(is_deleted,0)=0
            """,
            (
                data["workflow_code"],
                data["workflow_name"],
                data["module_name"],
                data["module_id"],
                data["description"],
                data["workflow_mode"],
                data["status"],
                username,
                now,
                workflow_id,
            ),
        )
        wf_id = workflow_id
        db.execute("DELETE FROM workflow_stages WHERE workflow_id=?", (wf_id,))
    else:
        db.execute(
            """
            INSERT INTO workflows(
                workflow_code, workflow_name, module_name, module_id, description,
                workflow_mode, status, created_by, created_at, customer_id
            ) VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (
                data["workflow_code"],
                data["workflow_name"],
                data["module_name"],
                data["module_id"],
                data["description"],
                data["workflow_mode"],
                data["status"],
                username,
                now,
                customer_id,
            ),
        )
        wf_id = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])
    for stage in stages:
        db.execute(
            """
            INSERT INTO workflow_stages(
                workflow_id, stage_number, stage_name, stage_type, designation_id,
                sequence, approval_required, reject_allowed, remarks_required,
                notification_enabled, escalation_enabled, escalation_hours,
                created_by, created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                wf_id,
                stage["stage_number"],
                stage.get("stage_name") or stage["stage_type"],
                stage["stage_type"],
                stage.get("designation_id"),
                stage["sequence"],
                1 if stage.get("approval_required", True) else 0,
                1 if stage.get("reject_allowed", True) else 0,
                1 if stage.get("remarks_required") else 0,
                1 if stage.get("notification_enabled", True) else 0,
                1 if stage.get("escalation_enabled") else 0,
                int(stage.get("escalation_hours") or 24),
                username,
                now,
            ),
        )
    sync_engine_to_workflow_master(db, wf_id)
    after = get_workflow_engine(db, wf_id)
    if before:
        for field in WORKFLOW_AUDIT_FIELDS:
            if str(before.get(field) or "") != str(after.get(field) or ""):
                log_workflow_engine_audit(
                    db,
                    wf_id,
                    "update",
                    username,
                    field_name=field,
                    old_value=str(before.get(field) or ""),
                    new_value=str(after.get(field) or ""),
                )
    else:
        log_workflow_engine_audit(db, wf_id, "create", username)
    return wf_id


def soft_delete_workflow_engine(db, workflow_id: int, username: str) -> None:
    if workflow_has_usage(db, workflow_id):
        raise ValueError("Workflow cannot be deleted once used in approvals. Deactivate instead.")
    now = _now_ts()
    wf = get_workflow_engine(db, workflow_id)
    if not wf:
        raise ValueError("Workflow not found.")
    db.execute(
        """
        UPDATE workflows SET is_deleted=1, deleted_by=?, deleted_at=?, status='Inactive'
        WHERE id=?
        """,
        (username, now, workflow_id),
    )
    db.execute(
        "UPDATE workflow_master SET status='Inactive' WHERE module_id=?",
        (wf["module_id"],),
    )
    log_workflow_engine_audit(db, workflow_id, "soft_delete", username)


def activate_workflow_engine(db, workflow_id: int, username: str) -> None:
    now = _now_ts()
    db.execute(
        "UPDATE workflows SET status='Active', modified_by=?, modified_at=? WHERE id=?",
        (username, now, workflow_id),
    )
    sync_engine_to_workflow_master(db, workflow_id)
    log_workflow_engine_audit(db, workflow_id, "activate", username)


def deactivate_workflow_engine(db, workflow_id: int, username: str) -> None:
    now = _now_ts()
    wf = get_workflow_engine(db, workflow_id)
    if not wf:
        raise ValueError("Workflow not found.")
    db.execute(
        "UPDATE workflows SET status='Inactive', modified_by=?, modified_at=? WHERE id=?",
        (username, now, workflow_id),
    )
    db.execute(
        "UPDATE workflow_master SET status='Inactive' WHERE module_id=?",
        (wf["module_id"],),
    )
    log_workflow_engine_audit(db, workflow_id, "deactivate", username)


def get_workflow_stages(db, workflow_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        """
        SELECT ws.*, d.designation_name
        FROM workflow_stages ws
        LEFT JOIN designations d ON ws.designation_id = d.id
        WHERE ws.workflow_id=?
        ORDER BY ws.sequence ASC, ws.stage_number ASC
        """,
        (workflow_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_workflow_engine(db, workflow_id: int | None, *, include_deleted: bool = False) -> dict[str, Any] | None:
    if not workflow_id:
        return None
    sql = "SELECT * FROM workflows WHERE id=?"
    if not include_deleted:
        sql += " AND COALESCE(is_deleted,0)=0"
    row = db.execute(sql, (workflow_id,)).fetchone()
    if not row:
        return None
    item = dict(row)
    item["stages"] = get_workflow_stages(db, workflow_id)
    item["has_usage"] = workflow_has_usage(db, workflow_id)
    item["workflow_mode_label"] = WORKFLOW_MODE_LABELS.get(
        item.get("workflow_mode") or DEFAULT_WORKFLOW_MODE,
        item.get("workflow_mode"),
    )
    return item


def list_workflows_engine(
    db,
    *,
    search: str = "",
    status: str = "",
    module_id: str = "",
    include_deleted: bool = False,
    page: int = 1,
    per_page: int = 25,
    sort_by: str = "workflow_name",
    sort_dir: str = "asc",
) -> dict[str, Any]:
    if not _table_exists(db, "workflows"):
        return {"items": [], "total": 0, "page": 1, "per_page": per_page, "pages": 0}
    sql = "SELECT w.* FROM workflows w WHERE 1=1"
    count_sql = "SELECT COUNT(*) FROM workflows w WHERE 1=1"
    params: list[Any] = []
    if not include_deleted:
        sql += " AND COALESCE(w.is_deleted,0)=0"
        count_sql += " AND COALESCE(w.is_deleted,0)=0"
    if status:
        sql += " AND w.status=?"
        count_sql += " AND w.status=?"
        params.append(status)
    if module_id:
        sql += " AND w.module_id=?"
        count_sql += " AND w.module_id=?"
        params.append(module_id)
    if search:
        clause = (
            " AND (w.workflow_code LIKE ? OR w.workflow_name LIKE ? "
            "OR w.module_name LIKE ? OR w.module_id LIKE ? OR w.description LIKE ?)"
        )
        sql += clause
        count_sql += clause
        like = f"%{search}%"
        params.extend([like, like, like, like, like])
    sort_col = sort_by if sort_by in WORKFLOW_SORT_COLUMNS else "workflow_name"
    sort_col = f"w.{sort_col}"
    direction = "DESC" if str(sort_dir).lower() == "desc" else "ASC"
    sql += f" ORDER BY {sort_col} {direction}, w.id DESC"
    per_page = max(1, min(int(per_page or 25), 500))
    page = max(1, int(page or 1))
    offset = (page - 1) * per_page
    sql += " LIMIT ? OFFSET ?"
    total = int(db.execute(count_sql, params).fetchone()[0])
    rows = db.execute(sql, [*params, per_page, offset]).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["stages"] = get_workflow_stages(db, item["id"])
        item["has_usage"] = workflow_has_usage(db, item["id"])
        items.append(item)
    pages = (total + per_page - 1) // per_page if total else 0
    return {"items": items, "total": total, "page": page, "per_page": per_page, "pages": pages}


def workflow_engine_dashboard(db, user_id: int | None, *, is_admin: bool = False) -> dict[str, Any]:
    summary = get_approval_summary(db)
    pending_checker = summary.get("pending_checker", 0)
    pending_approval = summary.get("pending_approval", 0)
    wf_role = get_user_workflow_role(db, user_id) if user_id else None
    return {
        "summary": summary,
        "workflow_count": db.execute(
            "SELECT COUNT(*) FROM workflows WHERE COALESCE(is_deleted,0)=0 AND status='Active'"
        ).fetchone()[0],
        "pending_checker": pending_checker,
        "pending_approval": pending_approval,
        "total_pending": pending_checker + pending_approval,
        "user_role": wf_role,
        "is_admin": is_admin,
    }


def list_workflow_queue(
    db,
    queue: str,
    user_id: int,
    *,
    is_admin: bool = False,
    module_id: str | None = None,
    page: int = 1,
    per_page: int = 25,
) -> dict[str, Any]:
    role_map = {
        "pending": "checker",
        "approval": "approver",
        "checker": "checker",
        "approver": "approver",
        "maker": "maker",
        "rejected": "maker",
        "approved": "maker",
    }
    role_type = role_map.get(queue, "checker")
    items = get_pending_items(db, user_id, role_type, is_admin=is_admin)
    if queue == "rejected":
        items = [
            i
            for i in items
            if i.get("workflow_status")
            in (STATUS_REJECTED_CHECKER, STATUS_REJECTED_APPROVER)
        ]
    elif queue == "approved":
        items = [i for i in items if i.get("workflow_status") == STATUS_APPROVED]
    elif queue in ("pending", "checker"):
        items = [i for i in items if i.get("workflow_status") == STATUS_PENDING_CHECKER]
    elif queue in ("approval", "approver"):
        items = [i for i in items if i.get("workflow_status") == STATUS_PENDING_APPROVAL]
    if module_id:
        items = [i for i in items if i.get("module_id") == module_id]
    total = len(items)
    per_page = max(1, min(int(per_page or 25), 200))
    page = max(1, int(page or 1))
    offset = (page - 1) * per_page
    page_items = items[offset : offset + per_page]
    enriched = []
    for item in page_items:
        row = dict(item)
        row["status_label"] = WORKFLOW_STATUS.get(
            row.get("workflow_status"), row.get("workflow_status")
        )
        row["reference_no"] = f"{(row.get('module_id') or 'WF').upper()[:6]}-{row.get('record_id')}"
        enriched.append(row)
    pages = (total + per_page - 1) // per_page if total else 0
    return {
        "items": enriched,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
        "queue": queue,
    }


def workflow_action(
    db,
    approval_id: int,
    user_id: int,
    action: str,
    comments: str = "",
    *,
    is_admin: bool = False,
) -> tuple[bool, str]:
    """Approve, reject, verify, or return to maker."""
    action = (action or "").strip().lower()
    if action == "return_to_maker":
        req = get_approval_request_by_id(db, approval_id)
        if not req:
            return False, "Approval request not found."
        status = req.get("workflow_status")
        if status not in (STATUS_PENDING_CHECKER, STATUS_PENDING_APPROVAL):
            return False, "Only pending items can be returned to maker."
        if status == STATUS_PENDING_CHECKER:
            ok, msg = advance_approval(db, approval_id, user_id, "reject", comments or "Returned to maker", is_admin)
        else:
            ok, msg = advance_approval(db, approval_id, user_id, "reject", comments or "Returned to maker", is_admin)
        if ok and req.get("maker_user_id"):
            create_notification(
                db,
                req["maker_user_id"],
                "Returned to Maker",
                "returned_to_maker",
                req.get("module_id"),
                req.get("record_id"),
                req.get("record_table"),
            )
        return ok, msg
    if action in ("verify", "approve", "reject"):
        return advance_approval(db, approval_id, user_id, action, comments, is_admin)
    if action == "reopen":
        return reopen_transaction(db, approval_id, user_id, comments, is_admin)
    if action == "resubmit":
        req = get_approval_request_by_id(db, approval_id)
        if not req:
            return False, "Approval request not found."
        resubmit_record(
            db,
            req["module_id"],
            req["record_id"],
            req["record_table"],
            user_id,
        )
        return True, "Resubmitted to checker."
    return False, f"Unsupported action: {action}"


def list_workflow_history(
    db,
    *,
    module_id: str | None = None,
    workflow_status: str | None = None,
    user_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    query = (
        "SELECT ar.*, wm.module_name, w.workflow_code, w.workflow_name "
        "FROM approval_requests ar "
        "LEFT JOIN workflow_master wm ON ar.module_id = wm.module_id "
        "LEFT JOIN workflows w ON ar.module_id = w.module_id "
        "WHERE 1=1"
    )
    params: list[Any] = []
    if module_id:
        query += " AND ar.module_id=?"
        params.append(module_id)
    if workflow_status:
        query += " AND ar.workflow_status=?"
        params.append(workflow_status)
    if user_id:
        query += " AND ar.maker_user_id=?"
        params.append(user_id)
    query += " ORDER BY ar.created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = db.execute(query, params).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["status_label"] = WORKFLOW_STATUS.get(
            item.get("workflow_status"), item.get("workflow_status")
        )
        item["history"] = get_approval_history(
            db, item["module_id"], item["record_id"], item["record_table"]
        )
        result.append(item)
    return result


def workflow_engine_report(
    db,
    report_key: str,
    *,
    user_id: int | None = None,
    module_id: str | None = None,
) -> list[dict[str, Any]]:
    key = (report_key or "").strip().lower()
    if key == "status_summary":
        rows = db.execute(
            """
            SELECT workflow_status, COUNT(*) AS cnt
            FROM approval_requests GROUP BY workflow_status
            """
        ).fetchall()
        return [
            {
                "workflow_status": r["workflow_status"],
                "status_label": WORKFLOW_STATUS.get(r["workflow_status"], r["workflow_status"]),
                "count": r["cnt"],
            }
            for r in rows
        ]
    if key == "approval_pending":
        return list_workflow_history(
            db,
            module_id=module_id,
            workflow_status=STATUS_PENDING_CHECKER,
            limit=500,
        )
    if key == "approval_pending_approver":
        return list_workflow_history(
            db,
            module_id=module_id,
            workflow_status=STATUS_PENDING_APPROVAL,
            limit=500,
        )
    if key == "approval_history":
        return list_workflow_history(db, module_id=module_id, limit=500)
    if key == "rejected":
        items = list_workflow_history(db, module_id=module_id, limit=500)
        return [
            i
            for i in items
            if i.get("workflow_status")
            in (STATUS_REJECTED_CHECKER, STATUS_REJECTED_APPROVER)
        ]
    if key == "user_pending" and user_id:
        return list_workflow_history(db, user_id=user_id, limit=200)
    if key == "workflows":
        listing = list_workflows_engine(db, per_page=500)
        return listing["items"]
    return []


def process_workflow_escalations(db) -> int:
    """Send escalation reminders for stuck approvals (notification only)."""
    if not _table_exists(db, "workflow_stages"):
        return 0
    now = datetime.now()
    count = 0
    stages = db.execute(
        """
        SELECT ws.*, w.module_id FROM workflow_stages ws
        JOIN workflows w ON ws.workflow_id = w.id
        WHERE ws.escalation_enabled=1 AND COALESCE(w.is_deleted,0)=0 AND w.status='Active'
        """
    ).fetchall()
    for stage in stages:
        stage = dict(stage)
        hours = int(stage.get("escalation_hours") or 24)
        cutoff = (now - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        status = (
            STATUS_PENDING_CHECKER
            if stage["stage_type"] == "Checker"
            else STATUS_PENDING_APPROVAL
        )
        if stage["stage_type"] not in ("Checker", "Approver"):
            continue
        pending = db.execute(
            """
            SELECT ar.id, ar.module_id, ar.record_id, ar.record_table, ar.created_at
            FROM approval_requests ar
            WHERE ar.module_id=? AND ar.workflow_status=?
            AND COALESCE(ar.checker_action_at, ar.created_at) < ?
            """,
            (stage["module_id"], status, cutoff),
        ).fetchall()
        for req in pending:
            req = dict(req)
            already = db.execute(
                """
                SELECT id FROM workflow_escalation_log
                WHERE approval_request_id=? AND stage_type=?
                AND escalated_at > ?
                """,
                (req["id"], stage["stage_type"], cutoff),
            ).fetchone()
            if already:
                continue
            desig_id = stage.get("designation_id")
            user_rows = db.execute(
                "SELECT id FROM users WHERE designation_id=? AND status='Active'",
                (desig_id,),
            ).fetchall() if desig_id else []
            notified = []
            for u in user_rows:
                uid = u["id"]
                create_notification(
                    db,
                    uid,
                    f"Escalation: pending {stage['stage_type']} approval",
                    "escalation_reminder",
                    req["module_id"],
                    req["record_id"],
                    req["record_table"],
                )
                notified.append(uid)
            db.execute(
                """
                INSERT INTO workflow_escalation_log(
                    approval_request_id, workflow_id, stage_type, escalated_at, notified_user_ids, remarks
                ) VALUES(?,?,?,?,?,?)
                """,
                (
                    req["id"],
                    stage["workflow_id"],
                    stage["stage_type"],
                    _now_ts(),
                    json.dumps(notified),
                    f"Pending over {hours}h",
                ),
            )
            count += 1
    return count


def ai_workflow_insights(db) -> dict[str, Any]:
    """Predict delays, stuck approvals, workload — graceful fallback without ai_service."""
    try:
        from ai_service import analyze_workflow_patterns  # type: ignore

        return analyze_workflow_patterns(db)
    except Exception:
        pass
    summary = get_approval_summary(db)
    stuck = db.execute(
        """
        SELECT COUNT(*) AS c FROM approval_requests
        WHERE workflow_status IN (?, ?)
        AND datetime(created_at) < datetime('now', '-48 hours')
        """,
        (STATUS_PENDING_CHECKER, STATUS_PENDING_APPROVAL),
    ).fetchone()
    stuck_count = int(stuck["c"]) if stuck else 0
    by_module = db.execute(
        """
        SELECT module_id, COUNT(*) AS cnt FROM approval_requests
        WHERE workflow_status IN (?, ?)
        GROUP BY module_id ORDER BY cnt DESC LIMIT 5
        """,
        (STATUS_PENDING_CHECKER, STATUS_PENDING_APPROVAL),
    ).fetchall()
    workload = [
        {"module_id": r["module_id"], "pending_count": r["cnt"]}
        for r in by_module
    ]
    delays_predicted = stuck_count > 0
    return {
        "source": "rules_engine",
        "summary": summary,
        "stuck_approvals": stuck_count,
        "delay_risk": "high" if stuck_count > 10 else "medium" if stuck_count > 0 else "low",
        "delays_predicted": delays_predicted,
        "workload_by_module": workload,
        "recommendations": [r for r in [
            "Review pending checker queue" if summary.get("pending_checker") else None,
            "Review pending approver queue" if summary.get("pending_approval") else None,
            "Escalate items pending over 48 hours" if stuck_count else None,
        ] if r],
    }


def user_can_workflow_engine(
    db,
    user_id: int | None,
    action: str,
    *,
    is_admin: bool = False,
) -> bool:
    if is_admin:
        return True
    if not user_id:
        return False
    wf_role = get_user_workflow_role(db, user_id)
    action_map = {
        "deactivate": "edit",
        "activate": "edit",
        "configure": "edit",
        "verify": "approve",
        "return": "reject",
    }
    check = action_map.get(action, action)
    admin_roles = {"Workflow Admin", "Administrator"}
    manager_roles = {"Workflow Manager", "Workflow Admin", "Administrator"}
    if check in ("create", "edit", "delete", "import", "configure") and wf_role in admin_roles | manager_roles:
        return True
    if check in ("approve", "verify", "reject", "return") and wf_role in (
        "Checker",
        "Approver",
        "Workflow Admin",
        "Administrator",
    ):
        return True
    if check == "view" and wf_role in WORKFLOW_PERMISSION_ROLES + ("Maker", "Administrator"):
        return True
    try:
        from user_permission_service import (
            empty_permission_actions,
            ensure_user_tab_permissions_schema,
            normalize_permission_actions,
        )

        ensure_user_tab_permissions_schema(db)
        row = db.execute(
            """
            SELECT granted, action_flags FROM user_tab_permissions
            WHERE user_id=? AND granted=1 AND endpoint='workflow_engine'
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        if not row:
            return wf_role in ("Checker", "Approver", "Maker") and check in (
                "view",
                "approve",
                "verify",
                "reject",
            )
        raw_flags = row["action_flags"] if hasattr(row, "keys") else row[1]
        actions = normalize_permission_actions(
            json.loads(raw_flags) if raw_flags else empty_permission_actions()
        )
        if check == "import":
            return bool(actions.get("import") or actions.get("create"))
        if check == "delete":
            return bool(actions.get("delete") or actions.get("edit"))
        if check in ("approve", "verify"):
            return bool(actions.get("approve") or actions.get("verify") or actions.get("edit"))
        if check == "reject":
            return bool(actions.get("reject") or actions.get("approve"))
        return bool(actions.get(check))
    except Exception:
        return wf_role in ("Checker", "Approver") and check in ("view", "approve", "verify", "reject")


def export_workflows_csv(db, **filters) -> str:
    listing = list_workflows_engine(db, per_page=10000, **filters)
    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow(
        [
            "workflow_code",
            "workflow_name",
            "module_id",
            "module_name",
            "workflow_mode",
            "status",
            "maker_designation",
            "checker_designation",
            "approver_designation",
        ]
    )
    for item in listing["items"]:
        stages = {s["stage_type"]: s.get("designation_name", "") for s in item.get("stages", [])}
        writer.writerow(
            [
                item.get("workflow_code"),
                item.get("workflow_name"),
                item.get("module_id"),
                item.get("module_name"),
                item.get("workflow_mode"),
                item.get("status"),
                stages.get("Maker", ""),
                stages.get("Checker", ""),
                stages.get("Approver", ""),
            ]
        )
    return si.getvalue()


def export_workflows_excel(db, **filters) -> BytesIO:
    from openpyxl import Workbook

    listing = list_workflows_engine(db, per_page=10000, **filters)
    wb = Workbook()
    ws = wb.active
    ws.title = "Workflows"
    headers = [
        "workflow_code",
        "workflow_name",
        "module_id",
        "module_name",
        "workflow_mode",
        "status",
        "maker_designation",
        "checker_designation",
        "approver_designation",
    ]
    ws.append(headers)
    for item in listing["items"]:
        stages = {s["stage_type"]: s.get("designation_name", "") for s in item.get("stages", [])}
        ws.append(
            [
                item.get("workflow_code"),
                item.get("workflow_name"),
                item.get("module_id"),
                item.get("module_name"),
                item.get("workflow_mode"),
                item.get("status"),
                stages.get("Maker", ""),
                stages.get("Checker", ""),
                stages.get("Approver", ""),
            ]
        )
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
