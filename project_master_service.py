"""Project Master (MODULE-016) — central project registry for all operational modules."""

from __future__ import annotations

import csv
import io
import json
import re
from io import BytesIO
from typing import Any

from branch_master_service import ensure_branch_master_schema, get_branch_master
from client_master_service import ensure_client_master_schema, get_client_master
from company_master_service import (
    _ensure_column,
    _now_ts,
    _table_exists,
    ensure_company_master_schema,
    get_company,
    list_companies,
)
from employee_master_service import ensure_employee_master_schema, get_employee_master
from project_photos_service import ensure_project_photos_schema

PROJECT_STATUSES = ("Active", "Inactive")
PROJECT_LIFECYCLE_STATUSES = (
    "Planning",
    "Tender",
    "Awarded",
    "Mobilization",
    "Execution",
    "Completed",
    "Closed",
    "Cancelled",
)
PROJECT_TYPES = (
    "Building",
    "Road",
    "Bridge",
    "Industrial",
    "Infrastructure",
    "Residential",
    "Commercial",
    "Government",
    "Maintenance",
    "Other",
)
PRIORITY_LEVELS = ("Low", "Medium", "High", "Critical")
CURRENCIES = ("INR", "USD", "EUR", "GBP", "AED", "SGD")
APPROVAL_STATUSES = ("Draft", "Pending", "Approved", "Rejected")
TEAM_ROLES = (
    "Project Manager",
    "Site Engineer",
    "Project Engineer",
    "Coordinator",
    "Supervisor",
    "QS",
    "Safety Officer",
    "Planning",
    "Accounts",
    "Other",
)

PROJECT_SORT_COLUMNS = (
    "project_code",
    "project_name",
    "project_type",
    "project_status",
    "start_date",
    "project_value",
    "status",
    "created_at",
    "company_id",
    "client_id",
)
PROJECT_EXPORT_COLUMNS = (
    "project_code",
    "project_name",
    "short_name",
    "project_type",
    "project_status",
    "client_code",
    "client_name",
    "company_code",
    "branch_code",
    "project_manager_code",
    "project_manager_name",
    "engineer_code",
    "engineer_name",
    "contract_number",
    "work_order_number",
    "agreement_number",
    "project_value",
    "revised_project_value",
    "currency",
    "start_date",
    "planned_completion_date",
    "actual_completion_date",
    "dlp_end_date",
    "retention_pct",
    "performance_guarantee",
    "emd_amount",
    "priority",
    "city",
    "state",
    "latitude",
    "longitude",
    "status",
    "approval_status",
)
PROJECT_AUDIT_FIELDS = (
    "project_code",
    "project_name",
    "short_name",
    "project_type",
    "client_id",
    "company_id",
    "branch_id",
    "project_manager_id",
    "project_engineer_id",
    "project_coordinator",
    "contract_number",
    "work_order_number",
    "agreement_number",
    "project_value",
    "revised_project_value",
    "start_date",
    "end_date",
    "planned_completion_date",
    "actual_completion_date",
    "dlp_end_date",
    "retention_pct",
    "performance_guarantee",
    "emd_amount",
    "project_status",
    "priority",
    "currency",
    "location",
    "site_address",
    "city",
    "state",
    "district",
    "country",
    "pin_code",
    "latitude",
    "longitude",
    "description",
    "remarks",
    "status",
    "approval_status",
    "budget",
    "quoted_amount",
    "work_order_amount",
)

PROJECT_REFERENCE_TABLES: tuple[tuple[str, str], ...] = (
    ("workers", "project_id"),
    ("attendance", "project_id"),
    ("petty_cash", "project_id"),
    ("boq_master", "project_id"),
    ("boq_items", "project_id"),
    ("dpr_entries", "project_id"),
    ("project_expenses", "project_id"),
    ("material_requests", "project_id"),
    ("purchase_requests", "project_id"),
    ("purchase_orders", "project_id"),
    ("store_receipts", "project_id"),
    ("store_issues", "project_id"),
    ("client_billing_register", "project_id"),
    ("project_photos", "project_id"),
    ("project_client_bill_submissions", "project_id"),
    ("project_guarantees", "project_id"),
    ("cost_plans", "project_id"),
    ("material_transfers", "source_project_id"),
    ("material_transfers", "dest_project_id"),
)

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _form_value(form, key: str, default: str = "") -> str:
    if form is None:
        return default
    if hasattr(form, "get"):
        val = form.get(key, default)
        return str(val).strip() if val is not None else default
    return default


def _form_getlist(form, key: str) -> list[str]:
    if form is None:
        return []
    if hasattr(form, "getlist"):
        return [str(v).strip() for v in form.getlist(key)]
    val = form.get(key)
    if val is None:
        return []
    if isinstance(val, list):
        return [str(v).strip() for v in val]
    return [str(val).strip()]


def _float_or_none(value: str) -> float | None:
    text = (value or "").strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError("Enter a valid numeric amount.") from exc


def generate_project_code(db, project_name: str = "") -> str:
    """Next project code — prefix from name when provided, else PR sequence."""
    prefix = "PR"
    if project_name:
        words = re.findall(r"[A-Za-z]+", project_name)
        if words:
            first = words[0]
            second = words[1] if len(words) > 1 else first
            prefix = (first[:1] + second[:1]).upper()
        if len(prefix) < 2:
            prefix = (project_name[:2] or "PR").upper()
    rows = db.execute(
        "SELECT project_code FROM projects WHERE project_code LIKE ?",
        (f"{prefix}%",),
    ).fetchall()
    max_num = 99
    for row in rows:
        code = str(row[0] if not hasattr(row, "keys") else row["project_code"] or "").strip()
        if code.upper().startswith(prefix.upper()):
            suffix = code[len(prefix) :]
            if suffix.isdigit():
                max_num = max(max_num, int(suffix))
    return f"{prefix}{max_num + 1}"


def ensure_project_master_schema(db) -> None:
    """Extend projects table and child tables for MODULE-016 (idempotent)."""
    ensure_company_master_schema(db)
    ensure_branch_master_schema(db)
    ensure_client_master_schema(db)
    ensure_employee_master_schema(db)
    ensure_project_photos_schema(db)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS projects(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT,
            client_id INTEGER,
            location TEXT,
            start_date TEXT,
            end_date TEXT,
            project_manager TEXT,
            budget REAL,
            status TEXT,
            FOREIGN KEY(client_id) REFERENCES clients(id)
        )
        """
    )
    for col, ctype in (
        ("project_code", "TEXT"),
        ("short_name", "TEXT"),
        ("project_type", "TEXT"),
        ("company_id", "INTEGER"),
        ("branch_id", "INTEGER"),
        ("project_manager_id", "INTEGER"),
        ("project_engineer_id", "INTEGER"),
        ("project_coordinator", "TEXT"),
        ("contract_number", "TEXT"),
        ("work_order_number", "TEXT"),
        ("agreement_number", "TEXT"),
        ("project_value", "REAL"),
        ("revised_project_value", "REAL"),
        ("planned_completion_date", "TEXT"),
        ("actual_completion_date", "TEXT"),
        ("dlp_end_date", "TEXT"),
        ("retention_pct", "REAL"),
        ("performance_guarantee", "REAL"),
        ("emd_amount", "REAL"),
        ("project_status", "TEXT"),
        ("priority", "TEXT"),
        ("currency", "TEXT DEFAULT 'INR'"),
        ("site_address", "TEXT"),
        ("city", "TEXT"),
        ("state", "TEXT"),
        ("district", "TEXT"),
        ("country", "TEXT DEFAULT 'India'"),
        ("pin_code", "TEXT"),
        ("latitude", "REAL"),
        ("longitude", "REAL"),
        ("description", "TEXT"),
        ("remarks", "TEXT"),
        ("approval_status", "TEXT DEFAULT 'Approved'"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT"),
        ("modified_by", "TEXT"),
        ("modified_at", "TEXT"),
        ("approved_by", "TEXT"),
        ("approved_at", "TEXT"),
        ("is_deleted", "INTEGER DEFAULT 0"),
        ("deleted_by", "TEXT"),
        ("deleted_at", "TEXT"),
        ("customer_id", "INTEGER"),
        ("private_client_name", "TEXT"),
        ("gov_department", "TEXT"),
        ("agreement_date", "TEXT"),
        ("completion_time", "TEXT"),
        ("completion_months", "REAL"),
        ("completion_mode", "TEXT"),
        ("quoted_amount", "REAL"),
        ("security_deposit_pct", "REAL"),
        ("guarantee_type", "TEXT"),
        ("work_order_date", "TEXT"),
        ("work_order_amount", "REAL"),
        ("project_contact_person", "TEXT"),
        ("approved_total_amount", "REAL"),
    ):
        _ensure_column(db, "projects", col, ctype)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS project_team(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            staff_id INTEGER,
            user_id INTEGER,
            role_name TEXT NOT NULL,
            is_primary INTEGER DEFAULT 0,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_by TEXT,
            modified_at TEXT,
            is_deleted INTEGER DEFAULT 0,
            FOREIGN KEY(project_id) REFERENCES projects(id),
            FOREIGN KEY(staff_id) REFERENCES staff(id)
        )
        """
    )
    for col, ctype in (
        ("user_id", "INTEGER"),
        ("is_primary", "INTEGER DEFAULT 0"),
        ("remarks", "TEXT"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT"),
        ("modified_by", "TEXT"),
        ("modified_at", "TEXT"),
        ("is_deleted", "INTEGER DEFAULT 0"),
    ):
        _ensure_column(db, "project_team", col, ctype)
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_project_team_project ON project_team(project_id)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_projects_code ON projects(project_code)"
    )
    _migrate_legacy_projects(db)
    try:
        from audit_trail_service import ensure_audit_schema

        ensure_audit_schema(db)
    except Exception:
        pass


def _migrate_legacy_projects(db) -> None:
    if not _table_exists(db, "projects"):
        return
    rows = db.execute(
        """
        SELECT id, project_code, project_name, budget, quoted_amount, work_order_amount,
               approved_total_amount, status, end_date, project_manager
        FROM projects WHERE COALESCE(is_deleted,0)=0
        """
    ).fetchall()
    for row in rows:
        pid = int(row[0])
        code = (row[1] or "").strip() if len(row) > 1 else ""
        name = (row[2] or "").strip() if len(row) > 2 else ""
        if not code and name:
            code = generate_project_code(db, name)
            db.execute("UPDATE projects SET project_code=? WHERE id=?", (code, pid))
        project_value = row[3] or row[4] or row[5] or row[6]
        if project_value:
            db.execute(
                """
                UPDATE projects SET project_value=COALESCE(project_value, ?),
                revised_project_value=COALESCE(revised_project_value, ?)
                WHERE id=?
                """,
                (project_value, project_value, pid),
            )
        lifecycle = db.execute(
            "SELECT project_status FROM projects WHERE id=?", (pid,)
        ).fetchone()
        if lifecycle and not (lifecycle[0] if not hasattr(lifecycle, "keys") else lifecycle["project_status"]):
            legacy_status = str(row[7] or "Execution").strip()
            mapped = _map_legacy_status(legacy_status)
            db.execute("UPDATE projects SET project_status=? WHERE id=?", (mapped, pid))
        end_date = row[8] if len(row) > 8 else None
        if end_date:
            db.execute(
                """
                UPDATE projects SET planned_completion_date=COALESCE(planned_completion_date, ?)
                WHERE id=?
                """,
                (end_date, pid),
            )
        db.execute(
            "UPDATE projects SET currency=COALESCE(NULLIF(TRIM(currency),''), 'INR') WHERE id=?",
            (pid,),
        )
        db.execute(
            "UPDATE projects SET status=COALESCE(NULLIF(TRIM(status),''), 'Active') WHERE id=?",
            (pid,),
        )


def _map_legacy_status(status: str) -> str:
    upper = status.upper()
    mapping = {
        "ACTIVE": "Execution",
        "IN PROGRESS": "Execution",
        "ONGOING": "Execution",
        "COMPLETED": "Completed",
        "CLOSED": "Closed",
        "CANCELLED": "Cancelled",
        "TENDER": "Tender",
        "PLANNING": "Planning",
        "AWARDED": "Awarded",
        "MOBILIZATION": "Mobilization",
    }
    for key, val in mapping.items():
        if key in upper:
            return val
    if status in PROJECT_LIFECYCLE_STATUSES:
        return status
    return "Execution"


def validate_project_uniqueness(
    db,
    *,
    project_code: str,
    project_id: int | None = None,
) -> None:
    code = (project_code or "").strip().upper()
    if not code:
        raise ValueError("Project code is required.")
    row = db.execute(
        """
        SELECT id FROM projects
        WHERE UPPER(project_code)=? AND COALESCE(is_deleted,0)=0
        """,
        (code,),
    ).fetchone()
    if row and (not project_id or int(row[0]) != int(project_id)):
        raise ValueError(f"Project code '{project_code}' already exists.")


def validate_project_form_data(db, data: dict[str, Any], *, project_id: int | None = None) -> None:
    if not (data.get("project_name") or "").strip():
        raise ValueError("Project name is required.")
    if not (data.get("project_code") or "").strip():
        raise ValueError("Project code is required.")
    if not data.get("client_id"):
        raise ValueError("Client is required.")
    if not data.get("company_id"):
        raise ValueError("Company is required.")
    if not data.get("branch_id"):
        raise ValueError("Branch is required.")
    if not data.get("project_manager_id"):
        raise ValueError("Project manager is required.")
    for date_field in (
        "start_date",
        "end_date",
        "planned_completion_date",
        "actual_completion_date",
        "dlp_end_date",
        "agreement_date",
        "work_order_date",
    ):
        val = (data.get(date_field) or "").strip()
        if val and not DATE_RE.match(val):
            raise ValueError(f"Enter {date_field.replace('_', ' ')} as YYYY-MM-DD.")
    for num_field in (
        "project_value",
        "revised_project_value",
        "retention_pct",
        "performance_guarantee",
        "emd_amount",
        "latitude",
        "longitude",
    ):
        val = data.get(num_field)
        if val is not None and val != "":
            try:
                float(val)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid numeric value for {num_field.replace('_', ' ')}.") from exc
    lifecycle = (data.get("project_status") or "Execution").strip()
    if lifecycle not in PROJECT_LIFECYCLE_STATUSES:
        raise ValueError("Select a valid project status.")
    status = (data.get("status") or "Active").strip()
    if status not in PROJECT_STATUSES:
        raise ValueError("Select a valid record status.")
    ptype = (data.get("project_type") or "").strip()
    if ptype and ptype not in PROJECT_TYPES:
        raise ValueError("Select a valid project type.")
    priority = (data.get("priority") or "").strip()
    if priority and priority not in PRIORITY_LEVELS:
        raise ValueError("Select a valid priority.")
    currency = (data.get("currency") or "INR").strip()
    if currency not in CURRENCIES:
        raise ValueError("Select a valid currency.")
    if not get_client_master(db, int(data["client_id"])):
        raise ValueError("Selected client was not found.")
    if not get_company(db, int(data["company_id"])):
        raise ValueError("Selected company was not found.")
    if not get_branch_master(db, int(data["branch_id"])):
        raise ValueError("Selected branch was not found.")
    if not get_employee_master(db, int(data["project_manager_id"])):
        raise ValueError("Selected project manager was not found.")
    engineer_id = data.get("project_engineer_id")
    if engineer_id and not get_employee_master(db, int(engineer_id)):
        raise ValueError("Selected project engineer was not found.")


def _parse_project_form(form) -> dict[str, Any]:
    client_id = _form_value(form, "client_id")
    company_id = _form_value(form, "company_id")
    branch_id = _form_value(form, "branch_id")
    pm_id = _form_value(form, "project_manager_id")
    eng_id = _form_value(form, "project_engineer_id")
    return {
        "project_code": _form_value(form, "project_code").upper(),
        "project_name": _form_value(form, "project_name"),
        "short_name": _form_value(form, "short_name"),
        "project_type": _form_value(form, "project_type") or "Infrastructure",
        "client_id": int(client_id) if client_id.isdigit() else None,
        "company_id": int(company_id) if company_id.isdigit() else None,
        "branch_id": int(branch_id) if branch_id.isdigit() else None,
        "project_manager_id": int(pm_id) if pm_id.isdigit() else None,
        "project_engineer_id": int(eng_id) if eng_id.isdigit() else None,
        "project_coordinator": _form_value(form, "project_coordinator"),
        "contract_number": _form_value(form, "contract_number"),
        "work_order_number": _form_value(form, "work_order_number"),
        "agreement_number": _form_value(form, "agreement_number"),
        "project_value": _float_or_none(_form_value(form, "project_value")),
        "revised_project_value": _float_or_none(_form_value(form, "revised_project_value")),
        "start_date": _form_value(form, "start_date"),
        "end_date": _form_value(form, "end_date"),
        "planned_completion_date": _form_value(form, "planned_completion_date"),
        "actual_completion_date": _form_value(form, "actual_completion_date"),
        "dlp_end_date": _form_value(form, "dlp_end_date"),
        "retention_pct": _float_or_none(_form_value(form, "retention_pct")),
        "performance_guarantee": _float_or_none(_form_value(form, "performance_guarantee")),
        "emd_amount": _float_or_none(_form_value(form, "emd_amount")),
        "project_status": _form_value(form, "project_status") or "Execution",
        "priority": _form_value(form, "priority") or "Medium",
        "currency": _form_value(form, "currency") or "INR",
        "location": _form_value(form, "location"),
        "site_address": _form_value(form, "site_address"),
        "city": _form_value(form, "city"),
        "state": _form_value(form, "state"),
        "district": _form_value(form, "district"),
        "country": _form_value(form, "country") or "India",
        "pin_code": _form_value(form, "pin_code"),
        "latitude": _float_or_none(_form_value(form, "latitude")),
        "longitude": _float_or_none(_form_value(form, "longitude")),
        "description": _form_value(form, "description"),
        "remarks": _form_value(form, "remarks"),
        "status": _form_value(form, "status") or "Active",
        "agreement_date": _form_value(form, "agreement_date"),
        "work_order_date": _form_value(form, "work_order_date"),
        "work_order_amount": _float_or_none(_form_value(form, "work_order_amount")),
        "quoted_amount": _float_or_none(_form_value(form, "quoted_amount")),
        "gov_department": _form_value(form, "gov_department"),
        "project_contact_person": _form_value(form, "project_contact_person"),
    }


def log_project_audit(
    db,
    project_id: int,
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
            record_table="projects",
            record_id=project_id,
            action=action,
            changed_by=username,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            remarks=remarks,
        )
    except Exception:
        pass


def log_project_field_changes(
    db,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    username: str,
) -> None:
    if not before or not after:
        return
    project_id = int(after.get("id") or before.get("id") or 0)
    if not project_id:
        return
    for field in PROJECT_AUDIT_FIELDS:
        old_val = before.get(field)
        new_val = after.get(field)
        if str(old_val or "") != str(new_val or ""):
            log_project_audit(
                db,
                project_id,
                "update",
                username,
                field_name=field,
                old_value=str(old_val or ""),
                new_value=str(new_val or ""),
            )


def list_project_audit_trail(db, project_id: int, limit: int = 100) -> list[dict[str, Any]]:
    try:
        from audit_trail_service import list_audit_trail

        return list_audit_trail(db, "projects", project_id, limit=limit)
    except Exception:
        return []


def _project_select_sql() -> str:
    return (
        "SELECT p.*, "
        "c.client_code, c.client_name, c.company_name AS client_company_name, "
        "co.company_code, co.company_name AS linked_company_name, "
        "b.branch_code, b.branch_name, "
        "pm.employee_code AS project_manager_code, pm.staff_name AS project_manager_name, "
        "pe.employee_code AS engineer_code, pe.staff_name AS engineer_name "
        "FROM projects p "
        "LEFT JOIN clients c ON p.client_id = c.id "
        "LEFT JOIN companies co ON p.company_id = co.id "
        "LEFT JOIN company_branches b ON p.branch_id = b.id "
        "LEFT JOIN staff pm ON p.project_manager_id = pm.id "
        "LEFT JOIN staff pe ON p.project_engineer_id = pe.id "
    )


def list_project_team(db, project_id: int) -> list[dict[str, Any]]:
    if not _table_exists(db, "project_team"):
        return []
    if _table_exists(db, "users"):
        sql = """
        SELECT pt.*, s.employee_code, s.staff_name, u.username
        FROM project_team pt
        LEFT JOIN staff s ON pt.staff_id = s.id
        LEFT JOIN users u ON pt.user_id = u.id
        WHERE pt.project_id=? AND COALESCE(pt.is_deleted,0)=0
        ORDER BY pt.is_primary DESC, pt.role_name, pt.id
        """
    else:
        sql = """
        SELECT pt.*, s.employee_code, s.staff_name, NULL AS username
        FROM project_team pt
        LEFT JOIN staff s ON pt.staff_id = s.id
        WHERE pt.project_id=? AND COALESCE(pt.is_deleted,0)=0
        ORDER BY pt.is_primary DESC, pt.role_name, pt.id
        """
    rows = db.execute(sql, (project_id,)).fetchall()
    return [dict(r) for r in rows]


def _save_project_team(db, project_id: int, form, username: str) -> None:
    now = _now_ts()
    ids = _form_getlist(form, "team_id[]")
    staff_ids = _form_getlist(form, "team_staff_id[]")
    user_ids = _form_getlist(form, "team_user_id[]")
    roles = _form_getlist(form, "team_role[]")
    remarks_list = _form_getlist(form, "team_remarks[]")
    primary_idx = _form_value(form, "team_primary_index")
    seen: set[int] = set()
    max_len = max(len(staff_ids), len(roles), len(ids), 1)
    for idx in range(max_len):
        role = roles[idx] if idx < len(roles) else ""
        staff_raw = staff_ids[idx] if idx < len(staff_ids) else ""
        user_raw = user_ids[idx] if idx < len(user_ids) else ""
        if not role and not staff_raw and not user_raw:
            continue
        if role and role not in TEAM_ROLES:
            role = "Other"
        staff_id = int(staff_raw) if staff_raw.isdigit() else None
        user_id = int(user_raw) if user_raw.isdigit() else None
        if not staff_id and not user_id:
            continue
        remark = remarks_list[idx] if idx < len(remarks_list) else ""
        is_primary = 1 if str(idx) == str(primary_idx) else 0
        tid_raw = ids[idx] if idx < len(ids) else ""
        if tid_raw.isdigit():
            tid = int(tid_raw)
            seen.add(tid)
            db.execute(
                """
                UPDATE project_team SET staff_id=?, user_id=?, role_name=?, is_primary=?,
                remarks=?, modified_by=?, modified_at=? WHERE id=? AND project_id=?
                """,
                (staff_id, user_id, role or "Other", is_primary, remark, username, now, tid, project_id),
            )
        else:
            cur = db.execute(
                """
                INSERT INTO project_team(project_id, staff_id, user_id, role_name, is_primary,
                remarks, created_by, created_at, modified_by, modified_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    project_id,
                    staff_id,
                    user_id,
                    role or "Other",
                    is_primary,
                    remark,
                    username,
                    now,
                    username,
                    now,
                ),
            )
            seen.add(int(cur.lastrowid))
    existing = db.execute(
        "SELECT id FROM project_team WHERE project_id=? AND COALESCE(is_deleted,0)=0",
        (project_id,),
    ).fetchall()
    for row in existing:
        rid = int(row[0])
        if rid not in seen and max_len > 0:
            db.execute(
                "UPDATE project_team SET is_deleted=1, modified_by=?, modified_at=? WHERE id=?",
                (username, now, rid),
            )


def list_projects_master(
    db,
    *,
    search: str = "",
    company_id: int | None = None,
    branch_id: int | None = None,
    client_id: int | None = None,
    project_status: str = "",
    project_type: str = "",
    status: str = "",
    include_deleted: bool = False,
    page: int = 1,
    per_page: int = 25,
    sort_by: str = "project_name",
    sort_dir: str = "asc",
) -> dict[str, Any]:
    if not _table_exists(db, "projects"):
        return {"items": [], "total": 0, "page": 1, "per_page": per_page, "pages": 0}
    sql = _project_select_sql() + " WHERE 1=1"
    count_sql = (
        "SELECT COUNT(*) FROM projects p "
        "LEFT JOIN clients c ON p.client_id = c.id WHERE 1=1"
    )
    params: list[Any] = []
    if not include_deleted:
        sql += " AND COALESCE(p.is_deleted,0)=0"
        count_sql += " AND COALESCE(p.is_deleted,0)=0"
    if company_id:
        sql += " AND p.company_id=?"
        count_sql += " AND p.company_id=?"
        params.append(company_id)
    if branch_id:
        sql += " AND p.branch_id=?"
        count_sql += " AND p.branch_id=?"
        params.append(branch_id)
    if client_id:
        sql += " AND p.client_id=?"
        count_sql += " AND p.client_id=?"
        params.append(client_id)
    if project_status:
        sql += " AND p.project_status=?"
        count_sql += " AND p.project_status=?"
        params.append(project_status)
    if project_type:
        sql += " AND p.project_type=?"
        count_sql += " AND p.project_type=?"
        params.append(project_type)
    if status:
        sql += " AND p.status=?"
        count_sql += " AND p.status=?"
        params.append(status)
    if search:
        clause = (
            " AND (p.project_name LIKE ? OR p.project_code LIKE ? OR p.short_name LIKE ? "
            "OR c.client_name LIKE ? OR c.client_code LIKE ? OR p.city LIKE ? "
            "OR p.contract_number LIKE ? OR p.work_order_number LIKE ? OR p.location LIKE ?)"
        )
        sql += clause
        count_sql += clause
        like = f"%{search}%"
        params.extend([like] * 9)
    sort_col = sort_by if sort_by in PROJECT_SORT_COLUMNS else "project_name"
    sort_col = f"p.{sort_col}"
    direction = "DESC" if str(sort_dir).lower() == "desc" else "ASC"
    sql += f" ORDER BY {sort_col} {direction}, p.id DESC"
    per_page = max(1, min(int(per_page or 25), 10000))
    page = max(1, int(page or 1))
    offset = (page - 1) * per_page
    sql += " LIMIT ? OFFSET ?"
    total = int(db.execute(count_sql, params).fetchone()[0])
    rows = db.execute(sql, [*params, per_page, offset]).fetchall()
    items = [dict(r) for r in rows]
    pages = (total + per_page - 1) // per_page if total else 0
    return {"items": items, "total": total, "page": page, "per_page": per_page, "pages": pages}


def list_projects_for_module(db, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Lightweight project list for other modules (BOQ, DPR, etc.)."""
    f = filters or {}
    listing = list_projects_master(
        db,
        search=str(f.get("search") or f.get("q") or ""),
        company_id=f.get("company_id"),
        branch_id=f.get("branch_id"),
        client_id=f.get("client_id"),
        project_status=str(f.get("project_status") or ""),
        project_type=str(f.get("project_type") or ""),
        status=str(f.get("status") or "Active"),
        include_deleted=bool(f.get("include_deleted")),
        page=int(f.get("page") or 1),
        per_page=int(f.get("per_page") or f.get("limit") or 500),
        sort_by=str(f.get("sort_by") or "project_name"),
        sort_dir=str(f.get("sort_dir") or "asc"),
    )
    out: list[dict[str, Any]] = []
    for item in listing["items"]:
        out.append(
            {
                "id": item.get("id"),
                "project_code": item.get("project_code"),
                "project_name": item.get("project_name"),
                "short_name": item.get("short_name"),
                "client_id": item.get("client_id"),
                "client_name": item.get("client_name"),
                "company_id": item.get("company_id"),
                "branch_id": item.get("branch_id"),
                "project_status": item.get("project_status"),
                "status": item.get("status"),
                "start_date": item.get("start_date"),
                "planned_completion_date": item.get("planned_completion_date"),
                "project_value": item.get("project_value"),
            }
        )
    return out


def get_project_master(db, project_id: int, *, include_deleted: bool = False) -> dict[str, Any] | None:
    if not project_id or not _table_exists(db, "projects"):
        return None
    sql = _project_select_sql() + " WHERE p.id=?"
    if not include_deleted:
        sql += " AND COALESCE(p.is_deleted,0)=0"
    row = db.execute(sql, (project_id,)).fetchone()
    if not row:
        return None
    data = dict(row)
    data["team"] = list_project_team(db, project_id)
    data["dashboard"] = get_project_dashboard_summary(db, project_id)
    try:
        from document_management_service import list_module_documents

        data["document_count"] = len(list_module_documents(db, "project_master", project_id))
    except Exception:
        data["document_count"] = 0
    if _table_exists(db, "project_photos"):
        photo_row = db.execute(
            "SELECT COUNT(*) FROM project_photos WHERE project_id=?",
            (project_id,),
        ).fetchone()
        data["photo_count"] = int(photo_row[0] if photo_row else 0)
    else:
        data["photo_count"] = 0
    return data


def _sync_legacy_financial_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Keep legacy columns in sync for operational modules."""
    pv = data.get("project_value")
    if pv is not None:
        data["budget"] = pv
        data["approved_total_amount"] = data.get("revised_project_value") or pv
        if data.get("quoted_amount") is None:
            data["quoted_amount"] = pv
        if data.get("work_order_amount") is None:
            data["work_order_amount"] = pv
    return data


def save_project_master(
    db,
    form,
    username: str,
    project_id: int | None = None,
    *,
    customer_id: int | None = None,
) -> int:
    data = _parse_project_form(form)
    if not data["project_code"]:
        data["project_code"] = generate_project_code(db, data["project_name"])
    validate_project_form_data(db, data, project_id=project_id)
    validate_project_uniqueness(db, project_code=data["project_code"], project_id=project_id)
    data = _sync_legacy_financial_fields(data)
    pm = get_employee_master(db, int(data["project_manager_id"]))
    data["project_manager"] = (pm or {}).get("staff_name") or ""
    now = _now_ts()
    core = (
        data["project_code"],
        data["project_name"],
        data["short_name"],
        data["project_type"],
        data["client_id"],
        data["company_id"],
        data["branch_id"],
        data["project_manager_id"],
        data["project_engineer_id"],
        data["project_coordinator"],
        data["contract_number"],
        data["work_order_number"],
        data["agreement_number"],
        data["project_value"],
        data["revised_project_value"],
        data["start_date"],
        data["end_date"],
        data["planned_completion_date"],
        data["actual_completion_date"],
        data["dlp_end_date"],
        data["retention_pct"],
        data["performance_guarantee"],
        data["emd_amount"],
        data["project_status"],
        data["priority"],
        data["currency"],
        data["location"],
        data["site_address"],
        data["city"],
        data["state"],
        data["district"],
        data["country"],
        data["pin_code"],
        data["latitude"],
        data["longitude"],
        data["description"],
        data["remarks"],
        data["status"],
        data["project_manager"],
        data.get("budget"),
        data.get("approved_total_amount"),
        data.get("quoted_amount"),
        data.get("work_order_amount"),
        data["agreement_date"],
        data["work_order_date"],
        data["gov_department"],
        data["project_contact_person"],
    )
    if project_id:
        existing = get_project_master(db, project_id, include_deleted=True)
        if not existing:
            raise ValueError("Project not found.")
        db.execute(
            """
            UPDATE projects SET project_code=?, project_name=?, short_name=?, project_type=?,
            client_id=?, company_id=?, branch_id=?, project_manager_id=?, project_engineer_id=?,
            project_coordinator=?, contract_number=?, work_order_number=?, agreement_number=?,
            project_value=?, revised_project_value=?, start_date=?, end_date=?,
            planned_completion_date=?, actual_completion_date=?, dlp_end_date=?,
            retention_pct=?, performance_guarantee=?, emd_amount=?, project_status=?,
            priority=?, currency=?, location=?, site_address=?, city=?, state=?, district=?,
            country=?, pin_code=?, latitude=?, longitude=?, description=?, remarks=?, status=?,
            project_manager=?, budget=?, approved_total_amount=?, quoted_amount=?,
            work_order_amount=?, agreement_date=?, work_order_date=?, gov_department=?,
            project_contact_person=?, modified_by=?, modified_at=? WHERE id=?
            """,
            (*core, username, now, project_id),
        )
        if customer_id is not None:
            db.execute("UPDATE projects SET customer_id=? WHERE id=?", (customer_id, project_id))
        _save_project_team(db, project_id, form, username)
        log_project_field_changes(
            db,
            existing,
            get_project_master(db, project_id, include_deleted=True),
            username,
        )
        return project_id
    approval_status = _form_value(form, "approval_status") or "Draft"
    if approval_status not in APPROVAL_STATUSES:
        approval_status = "Draft"
    cur = db.execute(
        """
        INSERT INTO projects(
            project_code, project_name, short_name, project_type, client_id, company_id, branch_id,
            project_manager_id, project_engineer_id, project_coordinator, contract_number,
            work_order_number, agreement_number, project_value, revised_project_value,
            start_date, end_date, planned_completion_date, actual_completion_date, dlp_end_date,
            retention_pct, performance_guarantee, emd_amount, project_status, priority, currency,
            location, site_address, city, state, district, country, pin_code, latitude, longitude,
            description, remarks, status, project_manager, budget, approved_total_amount,
            quoted_amount, work_order_amount, agreement_date, work_order_date, gov_department,
            project_contact_person, approval_status, created_by, created_at, modified_by, modified_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (*core, approval_status, username, now, username, now),
    )
    new_id = int(cur.lastrowid)
    if customer_id is not None:
        db.execute("UPDATE projects SET customer_id=? WHERE id=?", (customer_id, new_id))
    _save_project_team(db, new_id, form, username)
    log_project_audit(
        db,
        new_id,
        "create",
        username,
        remarks=f"Created project {data['project_code']}",
    )
    return new_id


def project_has_transactions(db, project_id: int) -> bool:
    """True when operational modules reference this project."""
    if not project_id:
        return False
    for table, column in PROJECT_REFERENCE_TABLES:
        if not _table_exists(db, table):
            continue
        try:
            row = db.execute(
                f"SELECT 1 FROM {table} WHERE {column}=? LIMIT 1",
                (project_id,),
            ).fetchone()
            if row:
                return True
        except Exception:
            continue
    return False


def get_project_dashboard_summary(db, project_id: int) -> dict[str, Any]:
    """Aggregate counts from linked operational tables (read-only hooks)."""
    summary: dict[str, Any] = {"project_id": project_id}
    counters: list[tuple[str, str, str]] = [
        ("boq_count", "boq_master", "project_id"),
        ("dpr_count", "dpr_entries", "project_id"),
        ("worker_count", "workers", "project_id"),
        ("expense_count", "project_expenses", "project_id"),
        ("billing_count", "client_billing_register", "project_id"),
        ("photo_count", "project_photos", "project_id"),
        ("purchase_count", "purchase_orders", "project_id"),
        ("material_request_count", "material_requests", "project_id"),
    ]
    for key, table, col in counters:
        summary[key] = 0
        if _table_exists(db, table):
            try:
                row = db.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {col}=?",
                    (project_id,),
                ).fetchone()
                summary[key] = int(row[0] if row else 0)
            except Exception:
                summary[key] = 0
    project_row = db.execute(
        "SELECT project_code, project_name, project_status, project_value, revised_project_value, "
        "start_date, planned_completion_date FROM projects WHERE id=?",
        (project_id,),
    ).fetchone()
    if project_row:
        summary["project_code"] = project_row[0]
        summary["project_name"] = project_row[1]
        summary["project_status"] = project_row[2]
        summary["project_value"] = project_row[3]
        summary["revised_project_value"] = project_row[4]
        summary["start_date"] = project_row[5]
        summary["planned_completion_date"] = project_row[6]
    if _table_exists(db, "project_team"):
        team_row = db.execute(
            "SELECT COUNT(*) FROM project_team WHERE project_id=? AND COALESCE(is_deleted,0)=0",
            (project_id,),
        ).fetchone()
        summary["team_size"] = int(team_row[0] if team_row else 0)
    else:
        summary["team_size"] = 0
    summary["has_transactions"] = project_has_transactions(db, project_id)
    return summary


def soft_delete_project_master(db, project_id: int, username: str) -> None:
    if not project_id:
        raise ValueError("Invalid project.")
    row = get_project_master(db, project_id, include_deleted=True)
    if not row:
        raise ValueError("Project not found.")
    if row.get("is_deleted"):
        return
    if project_has_transactions(db, project_id):
        raise ValueError(
            "Project cannot be deleted while BOQ, DPR, purchase, workers, billing, "
            "or other operational records reference it. Deactivate instead."
        )
    now = _now_ts()
    db.execute(
        """
        UPDATE projects SET is_deleted=1, deleted_by=?, deleted_at=?,
        modified_by=?, modified_at=? WHERE id=?
        """,
        (username, now, username, now, project_id),
    )
    log_project_audit(
        db,
        project_id,
        "soft_delete",
        username,
        remarks=f"Soft-deleted project {row.get('project_code')}",
    )


def activate_project_master(db, project_id: int, username: str) -> None:
    if not get_project_master(db, project_id):
        raise ValueError("Project not found.")
    now = _now_ts()
    db.execute(
        "UPDATE projects SET status='Active', modified_by=?, modified_at=? WHERE id=?",
        (username, now, project_id),
    )
    log_project_audit(
        db,
        project_id,
        "activate",
        username,
        field_name="status",
        old_value="Inactive",
        new_value="Active",
    )


def deactivate_project_master(db, project_id: int, username: str) -> None:
    if not get_project_master(db, project_id):
        raise ValueError("Project not found.")
    now = _now_ts()
    db.execute(
        "UPDATE projects SET status='Inactive', modified_by=?, modified_at=? WHERE id=?",
        (username, now, project_id),
    )
    log_project_audit(
        db,
        project_id,
        "deactivate",
        username,
        field_name="status",
        old_value="Active",
        new_value="Inactive",
    )


def approve_project_master(db, project_id: int, username: str) -> None:
    if not get_project_master(db, project_id):
        raise ValueError("Project not found.")
    now = _now_ts()
    db.execute(
        """
        UPDATE projects SET approval_status='Approved', approved_by=?, approved_at=?,
        modified_by=?, modified_at=? WHERE id=?
        """,
        (username, now, username, now, project_id),
    )
    log_project_audit(db, project_id, "approve", username, remarks="Project approved")


def reject_project_master(db, project_id: int, username: str, remarks: str = "") -> None:
    if not get_project_master(db, project_id):
        raise ValueError("Project not found.")
    now = _now_ts()
    db.execute(
        "UPDATE projects SET approval_status='Rejected', modified_by=?, modified_at=? WHERE id=?",
        (username, now, project_id),
    )
    log_project_audit(db, project_id, "reject", username, remarks=remarks or "Project rejected")


def user_can_project_master(
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
    action_map = {"deactivate": "edit", "activate": "edit"}
    check = action_map.get(action, action)
    try:
        from user_permission_service import empty_permission_actions, normalize_permission_actions

        row = db.execute(
            """
            SELECT granted, action_flags FROM user_tab_permissions
            WHERE user_id=? AND granted=1 AND endpoint='project_master'
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        if not row:
            return False
        raw_flags = row["action_flags"] if hasattr(row, "keys") else row[1]
        actions = normalize_permission_actions(
            json.loads(raw_flags) if raw_flags else empty_permission_actions()
        )
        if check == "import":
            return bool(actions.get("import") or actions.get("create"))
        if check == "delete":
            return bool(actions.get("delete") or actions.get("edit"))
        return bool(actions.get(check))
    except Exception:
        return False


def projects_for_export(db, *, include_deleted: bool = False, **filters) -> list[dict[str, Any]]:
    listing = list_projects_master(db, include_deleted=include_deleted, per_page=10000, **filters)
    rows: list[dict[str, Any]] = []
    for item in listing["items"]:
        row = {col: item.get(col, "") for col in PROJECT_EXPORT_COLUMNS}
        row["client_code"] = item.get("client_code") or ""
        row["client_name"] = item.get("client_name") or ""
        row["company_code"] = item.get("company_code") or ""
        row["branch_code"] = item.get("branch_code") or ""
        row["project_manager_code"] = item.get("project_manager_code") or ""
        row["project_manager_name"] = item.get("project_manager_name") or ""
        row["engineer_code"] = item.get("engineer_code") or ""
        row["engineer_name"] = item.get("engineer_name") or ""
        rows.append(row)
    return rows


def export_projects_excel(db, **filters) -> BytesIO:
    from openpyxl import Workbook

    rows = projects_for_export(db, **filters)
    wb = Workbook()
    ws = wb.active
    ws.title = "Projects"
    headers = list(PROJECT_EXPORT_COLUMNS)
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h, "") for h in headers])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def export_projects_csv(db, **filters) -> str:
    rows = projects_for_export(db, **filters)
    si = io.StringIO()
    writer = csv.writer(si)
    headers = list(PROJECT_EXPORT_COLUMNS)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row.get(h, "") for h in headers])
    return si.getvalue()


def export_projects_pdf(db, *, report_title: str = "Project Master Report", **filters) -> BytesIO:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    rows = projects_for_export(db, **filters)
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), title=report_title)
    styles = getSampleStyleSheet()
    story = [Paragraph(report_title, styles["Title"]), Spacer(1, 12)]
    headers = ["Code", "Name", "Client", "Status", "Value", "Manager"]
    table_data = [headers]
    for row in rows[:200]:
        table_data.append(
            [
                str(row.get("project_code") or ""),
                str(row.get("project_name") or "")[:40],
                str(row.get("client_name") or "")[:30],
                str(row.get("project_status") or ""),
                str(row.get("project_value") or ""),
                str(row.get("project_manager_name") or "")[:25],
            ]
        )
    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    buf.seek(0)
    return buf


def project_report(db, report_key: str, **filters) -> list[dict[str, Any]]:
    key = (report_key or "register").lower().strip()
    if key == "summary":
        listing = list_projects_master(db, per_page=5000, **filters)
        return [
            {
                "project_code": r.get("project_code"),
                "project_name": r.get("project_name"),
                "client_name": r.get("client_name"),
                "project_status": r.get("project_status"),
                "project_value": r.get("project_value"),
                "status": r.get("status"),
            }
            for r in listing["items"]
        ]
    if key == "status":
        listing = list_projects_master(db, per_page=5000, **filters)
        buckets: dict[str, int] = {s: 0 for s in PROJECT_LIFECYCLE_STATUSES}
        for r in listing["items"]:
            st = str(r.get("project_status") or "Execution")
            buckets[st] = buckets.get(st, 0) + 1
        return [{"project_status": k, "count": v} for k, v in buckets.items() if v]
    if key == "value":
        listing = list_projects_master(db, per_page=5000, **filters)
        return sorted(
            [
                {
                    "project_code": r.get("project_code"),
                    "project_name": r.get("project_name"),
                    "project_value": r.get("project_value") or 0,
                    "revised_project_value": r.get("revised_project_value") or 0,
                    "currency": r.get("currency"),
                }
                for r in listing["items"]
            ],
            key=lambda x: float(x.get("project_value") or 0),
            reverse=True,
        )
    if key == "manager":
        listing = list_projects_master(db, per_page=5000, **filters)
        return [
            {
                "project_code": r.get("project_code"),
                "project_name": r.get("project_name"),
                "project_manager_code": r.get("project_manager_code"),
                "project_manager_name": r.get("project_manager_name"),
                "project_status": r.get("project_status"),
            }
            for r in listing["items"]
            if r.get("project_manager_id")
        ]
    if key == "timeline":
        listing = list_projects_master(db, per_page=5000, **filters)
        return sorted(
            [
                {
                    "project_code": r.get("project_code"),
                    "project_name": r.get("project_name"),
                    "start_date": r.get("start_date"),
                    "planned_completion_date": r.get("planned_completion_date"),
                    "actual_completion_date": r.get("actual_completion_date"),
                    "dlp_end_date": r.get("dlp_end_date"),
                    "project_status": r.get("project_status"),
                }
                for r in listing["items"]
            ],
            key=lambda x: str(x.get("start_date") or ""),
        )
    listing = list_projects_master(db, per_page=5000, **filters)
    return listing["items"]


def project_import_template() -> BytesIO:
    from bulk_import_service import build_xlsx_template

    return build_xlsx_template(
        [
            "Project Code",
            "Project Name",
            "Short Name",
            "Project Type",
            "Client Code",
            "Company Code",
            "Branch Code",
            "Project Manager Code",
            "Engineer Code",
            "Contract Number",
            "Work Order Number",
            "Agreement Number",
            "Project Value",
            "Revised Value",
            "Currency",
            "Start Date",
            "Planned Completion",
            "Project Status",
            "Priority",
            "City",
            "State",
            "Latitude",
            "Longitude",
            "Status",
        ],
        [
            "PR101",
            "NH-44 Bridge Package",
            "NH44 Bridge",
            "Bridge",
            "CLT101",
            "CMP001",
            "BR001",
            "EMP101",
            "EMP102",
            "CNT-2026-001",
            "WO-2026-001",
            "AGR-2026-001",
            "50000000",
            "52000000",
            "INR",
            "2026-04-01",
            "2027-03-31",
            "Execution",
            "High",
            "Chennai",
            "Tamil Nadu",
            "13.0827",
            "80.2707",
            "Active",
        ],
    )


def project_health_check(db, project_id: int) -> dict[str, Any]:
    project = get_project_master(db, project_id)
    if not project:
        return {"ok": False, "issues": ["Project not found."]}
    issues: list[str] = []
    if not project.get("start_date"):
        issues.append("Start date is not set.")
    if not project.get("planned_completion_date"):
        issues.append("Planned completion date is missing.")
    if not project.get("project_value"):
        issues.append("Project value is not recorded.")
    if project.get("project_status") == "Execution" and not project.get("team"):
        issues.append("No project team members assigned.")
    dash = project.get("dashboard") or {}
    if dash.get("dpr_count", 0) == 0 and project.get("project_status") == "Execution":
        issues.append("No DPR entries recorded yet.")
    return {"ok": len(issues) == 0, "issues": issues, "project_id": project_id}


def risk_flags(db, project_id: int) -> list[dict[str, Any]]:
    project = get_project_master(db, project_id)
    if not project:
        return []
    flags: list[dict[str, Any]] = []
    if project.get("project_status") in ("Execution", "Mobilization"):
        if not project.get("project_engineer_id"):
            flags.append({"code": "NO_ENGINEER", "severity": "medium", "message": "Project engineer not assigned."})
        if project.get("retention_pct") and float(project["retention_pct"]) > 10:
            flags.append({"code": "HIGH_RETENTION", "severity": "low", "message": "Retention exceeds 10%."})
    if project.get("status") == "Inactive" and project.get("project_status") == "Execution":
        flags.append({"code": "STATUS_MISMATCH", "severity": "high", "message": "Record inactive but lifecycle is Execution."})
    return flags


def delay_prediction_stub(db, project_id: int) -> dict[str, Any]:
    project = get_project_master(db, project_id)
    if not project:
        return {"project_id": project_id, "prediction": "unknown", "note": "Project not found."}
    planned = project.get("planned_completion_date")
    actual = project.get("actual_completion_date")
    status = project.get("project_status")
    if status in ("Completed", "Closed"):
        return {"project_id": project_id, "prediction": "on_track", "confidence": 0.9, "note": "Project closed."}
    if planned and not actual and status == "Execution":
        return {
            "project_id": project_id,
            "prediction": "review_required",
            "confidence": 0.5,
            "note": "Rule stub: compare planned completion with latest DPR progress manually.",
        }
    return {"project_id": project_id, "prediction": "insufficient_data", "confidence": 0.3, "note": "AI stub only."}


def cost_prediction_stub(db, project_id: int) -> dict[str, Any]:
    dash = get_project_dashboard_summary(db, project_id)
    base = float(dash.get("project_value") or 0)
    expenses = dash.get("expense_count", 0)
    return {
        "project_id": project_id,
        "estimated_final_cost": base,
        "expense_entries": expenses,
        "note": "Rule stub: no ML — uses registered project value only.",
    }


def progress_analysis_stub(db, project_id: int) -> dict[str, Any]:
    dash = get_project_dashboard_summary(db, project_id)
    return {
        "project_id": project_id,
        "boq_count": dash.get("boq_count", 0),
        "dpr_count": dash.get("dpr_count", 0),
        "worker_count": dash.get("worker_count", 0),
        "note": "Rule stub: progress derived from linked record counts only.",
    }


def list_branches_for_project_form(db, company_id: int | None = None) -> list[dict[str, Any]]:
    if not company_id or not _table_exists(db, "company_branches"):
        return []
    rows = db.execute(
        """
        SELECT id, branch_code, branch_name FROM company_branches
        WHERE company_id=? AND COALESCE(is_deleted,0)=0 AND status='Active'
        ORDER BY branch_name
        """,
        (company_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_staff_for_project_form(db) -> list[dict[str, Any]]:
    if not _table_exists(db, "staff"):
        return []
    rows = db.execute(
        """
        SELECT id, employee_code, staff_name FROM staff
        WHERE COALESCE(is_deleted,0)=0 AND COALESCE(status,'Active')='Active'
        ORDER BY staff_name
        """,
    ).fetchall()
    return [dict(r) for r in rows]


def list_clients_for_project_form(db) -> list[dict[str, Any]]:
    if not _table_exists(db, "clients"):
        return []
    rows = db.execute(
        """
        SELECT id, client_code, client_name, company_name FROM clients
        WHERE COALESCE(is_deleted,0)=0 AND COALESCE(status,'Active')='Active'
        ORDER BY client_name
        """,
    ).fetchall()
    return [dict(r) for r in rows]
