"""Worker Master (MODULE-015) — construction labour registry (company + subcontractor workers)."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
from io import BytesIO
from typing import Any

from company_master_service import (
    _ensure_column,
    _now_ts,
    _table_exists,
    validate_pan_number,
    validate_phone,
)
from store_service import TRADE_CATEGORY_OPTIONS

WORKER_STATUSES = ("Active", "Inactive")
APPROVAL_STATUSES = ("Draft", "Pending", "Approved", "Rejected")
WORKER_TYPES = ("Company Worker", "Subcontractor Worker")
WORKER_CATEGORY_MAP = {
    "Company Worker": "Company Staff",
    "Subcontractor Worker": "Sub Contractor Staff",
}
REVERSE_WORKER_CATEGORY = {v: k for k, v in WORKER_CATEGORY_MAP.items()}
DEMO_COMPANY_WORKERS = (
    ("W001", "Ravi K"),
    ("W002", "Manoj S"),
    ("W003", "Velu M"),
)


def _subcontractor_name_sql(db) -> str:
    """Prefer subcontractor master name; fall back to linked vendor name."""
    if _table_exists(db, "vendors"):
        return "COALESCE(NULLIF(TRIM(s.subcontractor_name), ''), NULLIF(TRIM(v.name), ''))"
    return "s.subcontractor_name"


def _subcontractor_vendor_join(db) -> str:
    if _table_exists(db, "vendors"):
        return " LEFT JOIN vendors v ON v.id=s.vendor_id"
    return ""


def ensure_demo_company_workers(db) -> None:
    """Ensure legacy demo workers (W001–W003) exist in Worker Master."""
    if not _table_exists(db, "workers"):
        return
    project_row = db.execute(
        "SELECT id FROM projects WHERE COALESCE(status, 'Active')='Active' ORDER BY id LIMIT 1"
    ).fetchone()
    project_id = None
    if project_row is not None:
        project_id = project_row[0] if not hasattr(project_row, "keys") else project_row["id"]
    for code, name in DEMO_COMPANY_WORKERS:
        hit = db.execute(
            "SELECT id FROM workers WHERE UPPER(TRIM(worker_code))=? LIMIT 1",
            (code.upper(),),
        ).fetchone()
        if hit:
            worker_id = hit[0] if not hasattr(hit, "keys") else hit["id"]
            db.execute(
                """
                UPDATE workers SET worker_name=?, worker_category='Company Staff', status='Active',
                is_deleted=0
                WHERE id=?
                """,
                (name, worker_id),
            )
            continue
        if not project_id:
            continue
        db.execute(
            """
            INSERT INTO workers(
                worker_code, worker_name, worker_category, designation, salary_type,
                salary_amount, project_id, status, is_deleted
            ) VALUES(?,?,?,?,?,?,?,?,0)
            """,
            (code, name, "Company Staff", "Mason", "Daily", 850, project_id, "Active"),
        )
SALARY_TYPES = ("Monthly", "Daily", "Hourly")
ATTENDANCE_MODES = ("Manual", "Biometric", "Face", "Mobile", "Mixed")
GENDER_OPTIONS = ("Male", "Female", "Other", "Prefer not to say")
MEDICAL_FITNESS_OPTIONS = ("Fit", "Unfit", "Pending", "Expired")
PHOTO_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})
AADHAAR_RE = re.compile(r"^\d{12}$")
MOBILE_RE = re.compile(r"^\+?[\d\s\-()]{7,20}$")

WORKER_SORT_COLUMNS = (
    "worker_code",
    "worker_name",
    "trade",
    "worker_category",
    "status",
    "joining_date",
    "created_at",
    "project_id",
    "subcontractor_id",
)
WORKER_EXPORT_COLUMNS = (
    "worker_code",
    "worker_name",
    "worker_type",
    "company_code",
    "subcontractor_code",
    "trade",
    "skill",
    "project_code",
    "mobile",
    "aadhaar_number",
    "pan_number",
    "designation",
    "salary_type",
    "salary_amount",
    "ot_applicable",
    "ot_rate",
    "working_hours",
    "joining_date",
    "status",
    "approval_status",
)
WORKER_AUDIT_FIELDS = (
    "worker_code",
    "worker_name",
    "worker_category",
    "company_id",
    "branch_id",
    "subcontractor_id",
    "project_id",
    "trade",
    "skill",
    "designation",
    "mobile",
    "aadhaar_number",
    "pan_number",
    "salary_type",
    "salary_amount",
    "ot_applicable",
    "ot_rate",
    "working_hours",
    "joining_date",
    "status",
    "approval_status",
    "attendance_mode",
    "attendance_required",
    "allow_multi_project",
    "medical_fitness_status",
    "bank_account",
    "bank_name",
    "ifsc_code",
)
WORKER_REFERENCE_TABLES = (
    ("salary", "worker_id"),
    ("dpr_manpower", "worker_id"),
    ("payroll_lines", "worker_id"),
    ("salary_revisions", "worker_id"),
    ("employee_monthly_timesheets", "worker_id"),
    ("subcontractor_bill_lines", "worker_id"),
)


def worker_upload_dir(base_dir: str, subfolder: str = "workers") -> str:
    path = os.path.join(base_dir, "static", "uploads", subfolder)
    os.makedirs(path, exist_ok=True)
    return path


def normalize_worker_type(value: str) -> str:
    text = (value or "").strip()
    if text in WORKER_TYPES:
        return text
    if text in REVERSE_WORKER_CATEGORY:
        return REVERSE_WORKER_CATEGORY[text]
    if text.lower() in ("company", "company staff", "company worker"):
        return "Company Worker"
    if text.lower() in ("subcontractor", "sub contractor", "sub contractor staff", "subcontractor worker"):
        return "Subcontractor Worker"
    return text or "Company Worker"


def worker_category_from_type(worker_type: str) -> str:
    return WORKER_CATEGORY_MAP.get(normalize_worker_type(worker_type), "Company Staff")


def validate_aadhaar_number(value: str) -> None:
    text = re.sub(r"\s", "", (value or "").strip())
    if text and not AADHAAR_RE.match(text):
        raise ValueError("Enter a valid 12-digit Aadhaar number.")


def validate_worker_mobile(value: str) -> None:
    text = (value or "").strip()
    if not text:
        return
    if not MOBILE_RE.match(text):
        raise ValueError("Enter a valid mobile number.")
    try:
        validate_phone(text)
    except ValueError:
        pass


def ensure_worker_master_permission(db) -> None:
    if not _table_exists(db, "permissions"):
        return
    screen = "worker_master"
    hit = db.execute(
        "SELECT id FROM permissions WHERE screen_name=? AND COALESCE(is_deleted,0)=0 LIMIT 1",
        (screen,),
    ).fetchone()
    if hit:
        return
    now = _now_ts()
    db.execute(
        """
        INSERT INTO permissions(
            permission_code, permission_name, module_name, menu_name, screen_name,
            action, description, status, created_by, created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "SET-WORKER-MASTER",
            "Worker Master",
            "Settings",
            "Settings",
            screen,
            "",
            "Access to Worker Master (construction labour)",
            "Active",
            "system",
            now,
        ),
    )


def ensure_worker_master_schema(db) -> None:
    """Extend workers and child tables for MODULE-015 (idempotent)."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS workers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_code TEXT,
            worker_name TEXT,
            mobile TEXT,
            aadhaar_number TEXT,
            photo TEXT,
            worker_category TEXT,
            designation TEXT,
            salary_type TEXT,
            salary_amount REAL,
            ot_applicable TEXT,
            working_hours REAL,
            subcontractor_id INTEGER,
            project_id INTEGER,
            joining_date TEXT,
            status TEXT,
            FOREIGN KEY(subcontractor_id) REFERENCES subcontractors(id),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
        """
    )
    for col, ctype in (
        ("worker_code", "TEXT"),
        ("aadhaar_number", "TEXT"),
        ("worker_category", "TEXT DEFAULT 'Company Staff'"),
        ("subcontractor_id", "INTEGER"),
        ("bank_account", "TEXT"),
        ("bank_name", "TEXT"),
        ("ifsc_code", "TEXT"),
        ("branch_name", "TEXT"),
        ("pan_number", "TEXT"),
        ("id_proof", "TEXT"),
        ("aadhaar_document", "TEXT"),
        ("pan_document", "TEXT"),
        ("photo", "TEXT"),
        ("mobile", "TEXT"),
        ("designation", "TEXT"),
        ("salary_type", "TEXT"),
        ("salary_amount", "REAL"),
        ("ot_applicable", "TEXT"),
        ("ot_rate", "REAL"),
        ("working_hours", "REAL"),
        ("joining_date", "TEXT"),
        ("status", "TEXT DEFAULT 'Active'"),
        ("date_of_birth", "TEXT"),
        ("gender", "TEXT"),
        ("company_id", "INTEGER"),
        ("branch_id", "INTEGER"),
        ("trade", "TEXT"),
        ("skill", "TEXT"),
        ("address", "TEXT"),
        ("city", "TEXT"),
        ("state", "TEXT"),
        ("pincode", "TEXT"),
        ("allow_multi_project", "INTEGER DEFAULT 0"),
        ("attendance_mode", "TEXT DEFAULT 'Manual'"),
        ("attendance_required", "INTEGER DEFAULT 1"),
        ("attendance_grace_minutes", "INTEGER DEFAULT 0"),
        ("medical_checkup_date", "TEXT"),
        ("medical_fitness_status", "TEXT"),
        ("medical_remarks", "TEXT"),
        ("emergency_contact_name", "TEXT"),
        ("emergency_contact_mobile", "TEXT"),
        ("emergency_contact_relation", "TEXT"),
        ("face_template_ref", "TEXT"),
        ("approval_status", "TEXT DEFAULT 'Draft'"),
        ("approved_by", "TEXT"),
        ("approved_at", "TEXT"),
        ("remarks", "TEXT"),
        ("customer_id", "INTEGER"),
        ("created_by", "TEXT"),
        ("modified_by", "TEXT"),
        ("created_at", "TEXT"),
        ("modified_at", "TEXT"),
        ("is_deleted", "INTEGER DEFAULT 0"),
        ("deleted_by", "TEXT"),
        ("deleted_at", "TEXT"),
    ):
        _ensure_column(db, "workers", col, ctype)

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS worker_project_assignments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL,
            project_id INTEGER NOT NULL,
            start_date TEXT,
            end_date TEXT,
            is_active INTEGER DEFAULT 1,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_by TEXT,
            modified_at TEXT,
            FOREIGN KEY(worker_id) REFERENCES workers(id),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_worker_project_assignments_worker
        ON worker_project_assignments(worker_id, is_active)
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS worker_emergency_contacts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL,
            contact_name TEXT,
            relationship TEXT,
            mobile TEXT,
            is_primary INTEGER DEFAULT 0,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(worker_id) REFERENCES workers(id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS worker_face_templates(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL,
            template_reference TEXT NOT NULL,
            template_hash TEXT,
            registered_at TEXT,
            registered_by TEXT,
            device_info TEXT,
            is_active INTEGER DEFAULT 1,
            remarks TEXT,
            FOREIGN KEY(worker_id) REFERENCES workers(id)
        )
        """
    )
    _migrate_legacy_worker_assignments(db)
    try:
        from audit_trail_service import ensure_audit_schema

        ensure_audit_schema(db)
    except Exception:
        pass
    ensure_worker_master_permission(db)


def _migrate_legacy_worker_assignments(db) -> None:
    if not _table_exists(db, "worker_project_assignments"):
        return
    rows = db.execute(
        """
        SELECT id, project_id, joining_date FROM workers
        WHERE project_id IS NOT NULL AND COALESCE(is_deleted,0)=0
        """
    ).fetchall()
    now = _now_ts()
    for row in rows:
        wid = int(row[0] if isinstance(row, tuple) else row["id"])
        pid = row[1] if isinstance(row, tuple) else row["project_id"]
        if not pid:
            continue
        hit = db.execute(
            "SELECT id FROM worker_project_assignments WHERE worker_id=? AND project_id=? LIMIT 1",
            (wid, pid),
        ).fetchone()
        if hit:
            continue
        start = (row[2] if isinstance(row, tuple) else row.get("joining_date")) or ""
        db.execute(
            """
            INSERT INTO worker_project_assignments(
                worker_id, project_id, start_date, is_active, created_at, modified_at
            ) VALUES(?,?,?,?,?,?)
            """,
            (wid, pid, start, 1, now, now),
        )


def generate_worker_master_code(db, worker_type: str, subcontractor_id: int | None = None) -> str:
    category = worker_category_from_type(worker_type)
    if category == "Sub Contractor Staff" and subcontractor_id:
        sub = db.execute(
            "SELECT subcontractor_code, subcontractor_name FROM subcontractors WHERE id=?",
            (subcontractor_id,),
        ).fetchone()
        if sub:
            code = sub[0] if isinstance(sub, tuple) else sub["subcontractor_code"]
            name = sub[1] if isinstance(sub, tuple) else sub["subcontractor_name"]
            prefix = "SU"
            if code and len(str(code).strip()) >= 2:
                prefix = str(code).strip().upper()[:2]
            elif name:
                letters = re.sub(r"[^A-Za-z]", "", str(name))
                prefix = (letters[:2] or "SU").upper()
            rows = db.execute(
                "SELECT worker_code FROM workers WHERE worker_code LIKE ? AND COALESCE(is_deleted,0)=0",
                (f"{prefix}%",),
            ).fetchall()
            max_num = 99
            for r in rows:
                wc = str(r[0] if isinstance(r, tuple) else r["worker_code"] or "").strip().upper()
                suffix = wc[len(prefix) :]
                if suffix.isdigit():
                    max_num = max(max_num, int(suffix))
            return f"{prefix}{max_num + 1 if max_num >= 100 else 101}"
    rows = db.execute(
        "SELECT worker_code FROM workers WHERE worker_code LIKE 'WRK%' AND COALESCE(is_deleted,0)=0"
    ).fetchall()
    max_code = 100
    for row in rows:
        code = str(row[0] if isinstance(row, tuple) else row["worker_code"] or "").strip().upper()
        if code.startswith("WRK") and code[3:].isdigit():
            max_code = max(max_code, int(code[3:]))
    return f"WRK{max_code + 1}"


def validate_worker_uniqueness(db, *, worker_code: str, worker_id: int | None = None) -> None:
    code = (worker_code or "").strip().upper()
    if not code:
        raise ValueError("Worker code is required.")
    row = db.execute(
        """
        SELECT id FROM workers
        WHERE UPPER(worker_code)=? AND COALESCE(is_deleted,0)=0
        """,
        (code,),
    ).fetchone()
    if row and (not worker_id or int(row[0]) != int(worker_id)):
        raise ValueError(f"Worker code '{code}' already exists.")


def worker_has_transactions(db, worker_id: int) -> list[str]:
    blockers: list[str] = []
    if _table_exists(db, "attendance"):
        cols = {r[1] for r in db.execute("PRAGMA table_info(attendance)").fetchall()}
        if "worker_id" in cols:
            sql = "SELECT COUNT(*) FROM attendance WHERE worker_id=?"
            params: list[Any] = [worker_id]
            if "worker_source" in cols:
                sql += " AND COALESCE(worker_source,'worker')='worker'"
            row = db.execute(sql, params).fetchone()
            if int(row[0] if row else 0) > 0:
                blockers.append("attendance")
    for table, col in WORKER_REFERENCE_TABLES:
        if not _table_exists(db, table):
            continue
        cols = {r[1] for r in db.execute(f"PRAGMA table_info({table})").fetchall()}
        if col not in cols:
            continue
        row = db.execute(f"SELECT COUNT(*) FROM {table} WHERE {col}=?", (worker_id,)).fetchone()
        if int(row[0] if row else 0) > 0:
            blockers.append(table)
    return blockers


def log_worker_audit(
    db,
    worker_id: int,
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
            record_table="workers",
            record_id=worker_id,
            action=action,
            changed_by=username,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            remarks=remarks,
        )
    except Exception:
        pass


def log_worker_field_changes(
    db,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    username: str,
) -> None:
    if not before or not after:
        return
    worker_id = int(after.get("id") or before.get("id") or 0)
    if not worker_id:
        return
    for field in WORKER_AUDIT_FIELDS:
        old_val = before.get(field)
        new_val = after.get(field)
        if str(old_val or "") != str(new_val or ""):
            log_worker_audit(
                db,
                worker_id,
                "update",
                username,
                field_name=field,
                old_value=str(old_val or ""),
                new_value=str(new_val or ""),
            )


def list_worker_audit_trail(db, worker_id: int, limit: int = 100) -> list[dict[str, Any]]:
    try:
        from audit_trail_service import list_audit_trail

        return list_audit_trail(db, "workers", worker_id, limit=limit)
    except Exception:
        return []


def _parse_child_rows(form, prefix: str, fields: tuple[str, ...]) -> list[dict[str, str]]:
    lists: dict[str, list[str]] = {}
    getlist = getattr(form, "getlist", None)
    for field in fields:
        key = f"{prefix}_{field}[]"
        if getlist:
            lists[field] = getlist(key) or getlist(f"{prefix}_{field}")
        else:
            val = form.get(key) or form.get(f"{prefix}_{field}")
            lists[field] = val if isinstance(val, list) else ([val] if val else [])
    count = max((len(v) for v in lists.values()), default=0)
    rows: list[dict[str, str]] = []
    for idx in range(count):
        row = {f: (lists[f][idx] if idx < len(lists[f]) else "").strip() for f in fields}
        if any(row.values()):
            rows.append(row)
    return rows


def _parse_worker_form(form) -> dict[str, Any]:
    worker_type = normalize_worker_type(form.get("worker_type") or form.get("worker_category") or "")
    category = worker_category_from_type(worker_type)
    subcontractor_raw = form.get("subcontractor_id")
    subcontractor_id = int(subcontractor_raw) if subcontractor_raw and str(subcontractor_raw).isdigit() else None
    company_raw = form.get("company_id")
    company_id = int(company_raw) if company_raw and str(company_raw).isdigit() else None
    branch_raw = form.get("branch_id")
    branch_id = int(branch_raw) if branch_raw and str(branch_raw).isdigit() else None
    project_raw = form.get("project_id")
    project_id = int(project_raw) if project_raw and str(project_raw).isdigit() else None
    allow_multi = 1 if str(form.get("allow_multi_project", "")).lower() in ("1", "on", "true", "yes") else 0
    attendance_required = 1 if str(form.get("attendance_required", "1")).lower() not in ("0", "off", "false", "no") else 0
    try:
        salary_amount = float(form.get("salary_amount") or 0)
    except (TypeError, ValueError):
        salary_amount = 0.0
    try:
        ot_rate = float(form.get("ot_rate") or 0) if form.get("ot_rate") not in (None, "") else None
    except (TypeError, ValueError):
        ot_rate = None
    try:
        working_hours = float(form.get("working_hours") or 0) if form.get("working_hours") not in (None, "") else None
    except (TypeError, ValueError):
        working_hours = None
    try:
        grace = int(form.get("attendance_grace_minutes") or 0)
    except (TypeError, ValueError):
        grace = 0
    attendance_mode = (form.get("attendance_mode") or "Manual").strip()
    if attendance_mode not in ATTENDANCE_MODES:
        attendance_mode = "Manual"
    return {
        "worker_code": (form.get("worker_code") or "").strip().upper(),
        "worker_name": (form.get("worker_name") or "").strip(),
        "worker_type": worker_type,
        "worker_category": category,
        "company_id": company_id,
        "branch_id": branch_id,
        "subcontractor_id": subcontractor_id if category == "Sub Contractor Staff" else None,
        "project_id": project_id,
        "trade": (form.get("trade") or "").strip(),
        "skill": (form.get("skill") or "").strip(),
        "designation": (form.get("designation") or "").strip(),
        "mobile": (form.get("mobile") or "").strip(),
        "aadhaar_number": re.sub(r"\s", "", (form.get("aadhaar_number") or "").strip()),
        "pan_number": (form.get("pan_number") or "").strip().upper(),
        "gender": (form.get("gender") or "").strip(),
        "date_of_birth": (form.get("date_of_birth") or "").strip(),
        "address": (form.get("address") or "").strip(),
        "city": (form.get("city") or "").strip(),
        "state": (form.get("state") or "").strip(),
        "pincode": (form.get("pincode") or "").strip(),
        "salary_type": (form.get("salary_type") or "Daily").strip(),
        "salary_amount": salary_amount,
        "ot_applicable": (form.get("ot_applicable") or "No").strip(),
        "ot_rate": ot_rate,
        "working_hours": working_hours,
        "joining_date": (form.get("joining_date") or "").strip(),
        "status": (form.get("status") or "Active").strip(),
        "bank_account": (form.get("bank_account") or "").strip(),
        "bank_name": (form.get("bank_name") or "").strip(),
        "ifsc_code": (form.get("ifsc_code") or "").strip().upper(),
        "branch_name": (form.get("branch_name") or "").strip(),
        "allow_multi_project": allow_multi,
        "attendance_mode": attendance_mode,
        "attendance_required": attendance_required,
        "attendance_grace_minutes": grace,
        "medical_checkup_date": (form.get("medical_checkup_date") or "").strip(),
        "medical_fitness_status": (form.get("medical_fitness_status") or "").strip(),
        "medical_remarks": (form.get("medical_remarks") or "").strip(),
        "emergency_contact_name": (form.get("emergency_contact_name") or "").strip(),
        "emergency_contact_mobile": (form.get("emergency_contact_mobile") or "").strip(),
        "emergency_contact_relation": (form.get("emergency_contact_relation") or "").strip(),
        "remarks": (form.get("remarks") or "").strip(),
        "assignment_start_date": (form.get("assignment_start_date") or form.get("joining_date") or "").strip(),
    }


def validate_worker_form_data(data: dict[str, Any], *, worker_id: int | None = None) -> None:
    if not data.get("worker_name"):
        raise ValueError("Worker name is required.")
    if not data.get("trade"):
        raise ValueError("Trade is required.")
    if not data.get("worker_type"):
        raise ValueError("Worker type is required.")
    if data["worker_category"] == "Sub Contractor Staff" and not data.get("subcontractor_id"):
        raise ValueError("Subcontractor is required for subcontractor workers.")
    if data["worker_category"] == "Company Staff" and data.get("subcontractor_id"):
        raise ValueError("Company workers cannot be linked to a subcontractor.")
    if data.get("mobile"):
        validate_worker_mobile(data["mobile"])
    if data.get("aadhaar_number"):
        validate_aadhaar_number(data["aadhaar_number"])
    if data.get("pan_number"):
        validate_pan_number(data["pan_number"])
    if data.get("emergency_contact_mobile"):
        validate_worker_mobile(data["emergency_contact_mobile"])
    if data["status"] not in WORKER_STATUSES:
        raise ValueError("Select a valid status.")
    if data.get("salary_type") and data["salary_type"] not in SALARY_TYPES:
        raise ValueError("Select a valid salary type.")
    if data.get("trade") and data["trade"] not in TRADE_CATEGORY_OPTIONS:
        pass
    if data.get("medical_fitness_status") and data["medical_fitness_status"] not in MEDICAL_FITNESS_OPTIONS:
        raise ValueError("Select a valid medical fitness status.")


def _save_worker_emergency_contacts(db, worker_id: int, form, data: dict[str, Any]) -> None:
    now = _now_ts()
    db.execute("DELETE FROM worker_emergency_contacts WHERE worker_id=?", (worker_id,))
    contacts = _parse_child_rows(form, "ec", ("name", "relation", "mobile", "primary"))
    if not contacts and (data.get("emergency_contact_name") or data.get("emergency_contact_mobile")):
        contacts = [
            {
                "name": data.get("emergency_contact_name", ""),
                "relation": data.get("emergency_contact_relation", ""),
                "mobile": data.get("emergency_contact_mobile", ""),
                "primary": "1",
            }
        ]
    primary_name = ""
    primary_mobile = ""
    for idx, c in enumerate(contacts):
        is_primary = 1 if c.get("primary") in ("1", "on", "true") or idx == 0 else 0
        db.execute(
            """
            INSERT INTO worker_emergency_contacts(
                worker_id, contact_name, relationship, mobile, is_primary, created_at, modified_at
            ) VALUES(?,?,?,?,?,?,?)
            """,
            (
                worker_id,
                c.get("name", ""),
                c.get("relation", ""),
                c.get("mobile", ""),
                is_primary,
                now,
                now,
            ),
        )
        if is_primary:
            primary_name = c.get("name", "")
            primary_mobile = c.get("mobile", "")
    if primary_name or primary_mobile:
        db.execute(
            """
            UPDATE workers SET emergency_contact_name=?, emergency_contact_mobile=?
            WHERE id=?
            """,
            (primary_name, primary_mobile, worker_id),
        )


def _sync_project_assignment(
    db,
    worker_id: int,
    project_id: int | None,
    start_date: str,
    username: str,
    *,
    allow_multi: bool,
) -> None:
    if not project_id:
        return
    now = _now_ts()
    if not allow_multi:
        db.execute(
            """
            UPDATE worker_project_assignments SET is_active=0, end_date=?, modified_by=?, modified_at=?
            WHERE worker_id=? AND is_active=1 AND project_id!=?
            """,
            (now[:10], username, now, worker_id, project_id),
        )
        existing = db.execute(
            """
            SELECT id FROM worker_project_assignments
            WHERE worker_id=? AND project_id=? LIMIT 1
            """,
            (worker_id, project_id),
        ).fetchone()
        if existing:
            eid = int(existing[0] if isinstance(existing, tuple) else existing["id"])
            db.execute(
                """
                UPDATE worker_project_assignments SET is_active=1, start_date=COALESCE(NULLIF(?,''), start_date),
                end_date=NULL, modified_by=?, modified_at=? WHERE id=?
                """,
                (start_date, username, now, eid),
            )
        else:
            db.execute(
                """
                INSERT INTO worker_project_assignments(
                    worker_id, project_id, start_date, is_active, created_by, created_at, modified_by, modified_at
                ) VALUES(?,?,?,?,?,?,?,?)
                """,
                (worker_id, project_id, start_date or now[:10], 1, username, now, username, now),
            )
    else:
        db.execute(
            """
            INSERT INTO worker_project_assignments(
                worker_id, project_id, start_date, is_active, created_by, created_at, modified_by, modified_at
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (worker_id, project_id, start_date or now[:10], 1, username, now, username, now),
        )
    db.execute("UPDATE workers SET project_id=? WHERE id=?", (project_id, worker_id))


def _load_worker_children(db, worker_id: int) -> dict[str, Any]:
    if _table_exists(db, "projects"):
        assignment_rows = db.execute(
            """
            SELECT wpa.*, p.project_code, p.project_name
            FROM worker_project_assignments wpa
            LEFT JOIN projects p ON p.id=wpa.project_id
            WHERE wpa.worker_id=? ORDER BY wpa.is_active DESC, wpa.id DESC
            """,
            (worker_id,),
        ).fetchall()
    else:
        assignment_rows = db.execute(
            """
            SELECT wpa.*, NULL AS project_code, NULL AS project_name
            FROM worker_project_assignments wpa
            WHERE wpa.worker_id=? ORDER BY wpa.is_active DESC, wpa.id DESC
            """,
            (worker_id,),
        ).fetchall()
    assignments = [dict(r) for r in assignment_rows]
    contacts = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM worker_emergency_contacts WHERE worker_id=? ORDER BY is_primary DESC, id",
            (worker_id,),
        ).fetchall()
    ]
    face_templates = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM worker_face_templates WHERE worker_id=? ORDER BY is_active DESC, id DESC",
            (worker_id,),
        ).fetchall()
    ]
    return {
        "project_assignments": assignments,
        "emergency_contacts": contacts,
        "face_templates": face_templates,
    }


def save_worker_master(
    db,
    form,
    username: str,
    worker_id: int | None = None,
    *,
    customer_id: int | None = None,
) -> int:
    data = _parse_worker_form(form)
    validate_worker_form_data(data, worker_id=worker_id)
    if not worker_id and not data["worker_code"]:
        data["worker_code"] = generate_worker_master_code(
            db, data["worker_type"], data.get("subcontractor_id")
        )
    validate_worker_uniqueness(db, worker_code=data["worker_code"], worker_id=worker_id)
    if data["project_id"] and not data.get("assignment_start_date") and not data.get("joining_date"):
        raise ValueError("Project assignment start date is required when assigning a project.")

    now = _now_ts()
    core = (
        data["worker_code"],
        data["worker_name"],
        data["worker_category"],
        data["company_id"],
        data["branch_id"],
        data["subcontractor_id"],
        data["project_id"],
        data["trade"],
        data["skill"],
        data["designation"],
        data["mobile"],
        data["aadhaar_number"],
        data["pan_number"],
        data["gender"],
        data["date_of_birth"],
        data["address"],
        data["city"],
        data["state"],
        data["pincode"],
        data["salary_type"],
        data["salary_amount"],
        data["ot_applicable"],
        data["ot_rate"],
        data["working_hours"],
        data["joining_date"],
        data["status"],
        data["bank_account"],
        data["bank_name"],
        data["ifsc_code"],
        data["branch_name"],
        data["allow_multi_project"],
        data["attendance_mode"],
        data["attendance_required"],
        data["attendance_grace_minutes"],
        data["medical_checkup_date"],
        data["medical_fitness_status"],
        data["medical_remarks"],
        data["emergency_contact_name"],
        data["emergency_contact_mobile"],
        data["emergency_contact_relation"],
        data["remarks"],
    )
    if worker_id:
        existing = get_worker_master(db, worker_id, include_deleted=True)
        if not existing:
            raise ValueError("Worker not found.")
        db.execute(
            """
            UPDATE workers SET worker_code=?, worker_name=?, worker_category=?, company_id=?, branch_id=?,
            subcontractor_id=?, project_id=?, trade=?, skill=?, designation=?, mobile=?, aadhaar_number=?,
            pan_number=?, gender=?, date_of_birth=?, address=?, city=?, state=?, pincode=?, salary_type=?,
            salary_amount=?, ot_applicable=?, ot_rate=?, working_hours=?, joining_date=?, status=?,
            bank_account=?, bank_name=?, ifsc_code=?, branch_name=?, allow_multi_project=?, attendance_mode=?,
            attendance_required=?, attendance_grace_minutes=?, medical_checkup_date=?, medical_fitness_status=?,
            medical_remarks=?, emergency_contact_name=?, emergency_contact_mobile=?, emergency_contact_relation=?,
            remarks=?, modified_by=?, modified_at=? WHERE id=?
            """,
            (*core, username, now, worker_id),
        )
        if customer_id is not None:
            db.execute("UPDATE workers SET customer_id=? WHERE id=?", (customer_id, worker_id))
        if data["project_id"]:
            _sync_project_assignment(
                db,
                worker_id,
                data["project_id"],
                data["assignment_start_date"],
                username,
                allow_multi=bool(data["allow_multi_project"]),
            )
        _save_worker_emergency_contacts(db, worker_id, form, data)
        log_worker_field_changes(
            db, existing, get_worker_master(db, worker_id, include_deleted=True), username
        )
        return worker_id

    approval_status = (form.get("approval_status") or "Draft").strip()
    if approval_status not in APPROVAL_STATUSES:
        approval_status = "Draft"
    cur = db.execute(
        """
        INSERT INTO workers(
            worker_code, worker_name, worker_category, company_id, branch_id, subcontractor_id, project_id,
            trade, skill, designation, mobile, aadhaar_number, pan_number, gender, date_of_birth, address,
            city, state, pincode, salary_type, salary_amount, ot_applicable, ot_rate, working_hours,
            joining_date, status, bank_account, bank_name, ifsc_code, branch_name, allow_multi_project,
            attendance_mode, attendance_required, attendance_grace_minutes, medical_checkup_date,
            medical_fitness_status, medical_remarks, emergency_contact_name, emergency_contact_mobile,
            emergency_contact_relation, remarks, approval_status, created_by, created_at, modified_by, modified_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (*core, approval_status, username, now, username, now),
    )
    new_id = int(cur.lastrowid)
    if customer_id is not None:
        db.execute("UPDATE workers SET customer_id=? WHERE id=?", (customer_id, new_id))
    if data["project_id"]:
        _sync_project_assignment(
            db,
            new_id,
            data["project_id"],
            data["assignment_start_date"],
            username,
            allow_multi=bool(data["allow_multi_project"]),
        )
    _save_worker_emergency_contacts(db, new_id, form, data)
    log_worker_audit(db, new_id, "create", username, remarks=f"Created worker {data['worker_code']}")
    return new_id


def get_worker_master(db, worker_id: int, *, include_deleted: bool = False) -> dict[str, Any] | None:
    if _table_exists(db, "companies") and _table_exists(db, "company_branches"):
        sql = (
            "SELECT w.*, c.company_code, c.company_name, b.branch_name, "
            "s.subcontractor_code, "
            f"{_subcontractor_name_sql(db)} AS subcontractor_name, "
            "p.project_code, p.project_name "
            "FROM workers w "
            "LEFT JOIN companies c ON c.id=w.company_id "
            "LEFT JOIN company_branches b ON b.id=w.branch_id "
            "LEFT JOIN subcontractors s ON s.id=w.subcontractor_id "
            f"{_subcontractor_vendor_join(db)} "
            "LEFT JOIN projects p ON p.id=w.project_id "
            "WHERE w.id=?"
        )
    elif _table_exists(db, "subcontractors") and _table_exists(db, "projects"):
        sql = (
            "SELECT w.*, NULL AS company_code, NULL AS company_name, NULL AS branch_name, "
            "s.subcontractor_code, "
            f"{_subcontractor_name_sql(db)} AS subcontractor_name, "
            "p.project_code, p.project_name "
            "FROM workers w "
            "LEFT JOIN subcontractors s ON s.id=w.subcontractor_id "
            f"{_subcontractor_vendor_join(db)} "
            "LEFT JOIN projects p ON p.id=w.project_id "
            "WHERE w.id=?"
        )
    else:
        sql = (
            "SELECT w.*, NULL AS company_code, NULL AS company_name, NULL AS branch_name, "
            "NULL AS subcontractor_code, NULL AS subcontractor_name, "
            "NULL AS project_code, NULL AS project_name "
            "FROM workers w WHERE w.id=?"
        )
    if not include_deleted:
        sql += " AND COALESCE(w.is_deleted,0)=0"
    row = db.execute(sql, (worker_id,)).fetchone()
    if not row:
        return None
    data = dict(row)
    data["worker_type"] = REVERSE_WORKER_CATEGORY.get(data.get("worker_category") or "", "Company Worker")
    children = _load_worker_children(db, worker_id)
    data.update(children)
    active = next((a for a in children["project_assignments"] if a.get("is_active")), None)
    if active:
        data["active_project_id"] = active.get("project_id")
        data["active_project_name"] = active.get("project_name")
    try:
        from document_management_service import list_module_documents

        data["documents"] = list_module_documents(db, "worker_master", worker_id)
    except Exception:
        data["documents"] = []
    return data


def list_workers_master(
    db,
    *,
    search: str = "",
    status: str = "",
    worker_type: str = "",
    trade: str = "",
    subcontractor_id: int | None = None,
    project_id: int | None = None,
    company_id: int | None = None,
    approval_status: str = "",
    include_deleted: bool = False,
    page: int = 1,
    per_page: int = 25,
    sort_by: str = "worker_name",
    sort_dir: str = "asc",
) -> dict[str, Any]:
    if not _table_exists(db, "workers"):
        return {"items": [], "total": 0, "page": 1, "per_page": per_page, "pages": 0}
    if _table_exists(db, "companies") and _table_exists(db, "subcontractors") and _table_exists(db, "projects"):
        sql = (
            "SELECT w.*, c.company_code, s.subcontractor_code, "
            f"{_subcontractor_name_sql(db)} AS subcontractor_name, "
            "p.project_code, p.project_name FROM workers w "
            "LEFT JOIN companies c ON c.id=w.company_id "
            "LEFT JOIN subcontractors s ON s.id=w.subcontractor_id "
            f"{_subcontractor_vendor_join(db)} "
            "LEFT JOIN projects p ON p.id=w.project_id WHERE 1=1"
        )
    else:
        sql = (
            "SELECT w.*, NULL AS company_code, NULL AS subcontractor_code, NULL AS subcontractor_name, "
            "NULL AS project_code, NULL AS project_name FROM workers w WHERE 1=1"
        )
    count_sql = "SELECT COUNT(*) FROM workers w WHERE 1=1"
    params: list[Any] = []
    if not include_deleted:
        sql += " AND COALESCE(w.is_deleted,0)=0"
        count_sql += " AND COALESCE(w.is_deleted,0)=0"
    if status:
        sql += " AND w.status=?"
        count_sql += " AND w.status=?"
        params.append(status)
    if worker_type:
        cat = worker_category_from_type(worker_type)
        sql += " AND w.worker_category=?"
        count_sql += " AND w.worker_category=?"
        params.append(cat)
    if trade:
        sql += " AND w.trade=?"
        count_sql += " AND w.trade=?"
        params.append(trade)
    if subcontractor_id:
        sql += " AND w.subcontractor_id=?"
        count_sql += " AND w.subcontractor_id=?"
        params.append(subcontractor_id)
    if project_id:
        sql += " AND w.project_id=?"
        count_sql += " AND w.project_id=?"
        params.append(project_id)
    if company_id:
        sql += " AND w.company_id=?"
        count_sql += " AND w.company_id=?"
        params.append(company_id)
    if approval_status:
        sql += " AND w.approval_status=?"
        count_sql += " AND w.approval_status=?"
        params.append(approval_status)
    if search:
        like = f"%{search.strip()}%"
        sql += " AND (w.worker_code LIKE ? OR w.worker_name LIKE ? OR w.mobile LIKE ? OR w.trade LIKE ?)"
        count_sql += " AND (w.worker_code LIKE ? OR w.worker_name LIKE ? OR w.mobile LIKE ? OR w.trade LIKE ?)"
        params.extend([like, like, like, like])
    sort_col = sort_by if sort_by in WORKER_SORT_COLUMNS else "worker_name"
    direction = "DESC" if str(sort_dir).lower() == "desc" else "ASC"
    sql += f" ORDER BY w.{sort_col} {direction}"
    page = max(1, int(page or 1))
    per_page = max(1, min(int(per_page or 25), 500))
    offset = (page - 1) * per_page
    total_row = db.execute(count_sql, params).fetchone()
    total = int(total_row[0] if total_row else 0)
    rows = db.execute(sql + " LIMIT ? OFFSET ?", (*params, per_page, offset)).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        data["worker_type"] = REVERSE_WORKER_CATEGORY.get(data.get("worker_category") or "", "Company Worker")
        items.append(data)
    pages = (total + per_page - 1) // per_page if per_page else 0
    return {"items": items, "total": total, "page": page, "per_page": per_page, "pages": pages}


def soft_delete_worker_master(db, worker_id: int, username: str) -> None:
    row = get_worker_master(db, worker_id, include_deleted=True)
    if not row:
        raise ValueError("Worker not found.")
    if row.get("is_deleted"):
        return
    blockers = worker_has_transactions(db, worker_id)
    if blockers:
        raise ValueError(
            "Cannot delete worker with linked records in: " + ", ".join(blockers) + ". Deactivate instead."
        )
    now = _now_ts()
    db.execute(
        "UPDATE workers SET is_deleted=1, deleted_by=?, deleted_at=?, status='Inactive', modified_by=?, modified_at=? WHERE id=?",
        (username, now, username, now, worker_id),
    )
    log_worker_audit(db, worker_id, "delete", username, remarks="Worker soft-deleted")


def activate_worker_master(db, worker_id: int, username: str) -> None:
    if not get_worker_master(db, worker_id, include_deleted=True):
        raise ValueError("Worker not found.")
    now = _now_ts()
    db.execute(
        "UPDATE workers SET status='Active', modified_by=?, modified_at=? WHERE id=?",
        (username, now, worker_id),
    )
    log_worker_audit(db, worker_id, "activate", username, field_name="status", new_value="Active")


def deactivate_worker_master(db, worker_id: int, username: str) -> None:
    if not get_worker_master(db, worker_id, include_deleted=True):
        raise ValueError("Worker not found.")
    now = _now_ts()
    db.execute(
        "UPDATE workers SET status='Inactive', modified_by=?, modified_at=? WHERE id=?",
        (username, now, worker_id),
    )
    log_worker_audit(db, worker_id, "deactivate", username, field_name="status", new_value="Inactive")


def approve_worker_master(db, worker_id: int, username: str) -> None:
    if not get_worker_master(db, worker_id):
        raise ValueError("Worker not found.")
    now = _now_ts()
    db.execute(
        """
        UPDATE workers SET approval_status='Approved', approved_by=?, approved_at=?,
        modified_by=?, modified_at=? WHERE id=?
        """,
        (username, now, username, now, worker_id),
    )
    log_worker_audit(db, worker_id, "approve", username, remarks="Worker approved")


def reject_worker_master(db, worker_id: int, username: str, remarks: str = "") -> None:
    if not get_worker_master(db, worker_id):
        raise ValueError("Worker not found.")
    now = _now_ts()
    db.execute(
        "UPDATE workers SET approval_status='Rejected', modified_by=?, modified_at=? WHERE id=?",
        (username, now, worker_id),
    )
    log_worker_audit(db, worker_id, "reject", username, remarks=remarks or "Worker rejected")


def user_can_worker_master(
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
        from user_permission_service import empty_permission_actions, ensure_user_tab_permissions_schema, normalize_permission_actions

        ensure_user_tab_permissions_schema(db)
        row = db.execute(
            """
            SELECT granted, action_flags FROM user_tab_permissions
            WHERE user_id=? AND granted=1 AND endpoint='worker_master'
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


def register_face_template(
    db,
    worker_id: int,
    template_reference: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Store face template reference only — no recognition processing."""
    ref = (template_reference or "").strip()
    if not ref:
        raise ValueError("Template reference is required.")
    if not get_worker_master(db, worker_id):
        raise ValueError("Worker not found.")
    meta = metadata or {}
    template_hash = hashlib.sha256(ref.encode("utf-8")).hexdigest()
    dup = db.execute(
        """
        SELECT wft.id, w.worker_code, w.worker_name FROM worker_face_templates wft
        JOIN workers w ON w.id=wft.worker_id
        WHERE wft.template_hash=? AND wft.worker_id!=? AND COALESCE(wft.is_active,1)=1
        LIMIT 1
        """,
        (template_hash, worker_id),
    ).fetchone()
    if dup:
        code = dup[1] if isinstance(dup, tuple) else dup["worker_code"]
        raise ValueError(f"Face template reference already registered for worker {code}.")
    now = _now_ts()
    registered_by = str(meta.get("registered_by") or meta.get("username") or "system")
    device_info = str(meta.get("device_info") or meta.get("device") or "")
    db.execute(
        "UPDATE worker_face_templates SET is_active=0 WHERE worker_id=?",
        (worker_id,),
    )
    cur = db.execute(
        """
        INSERT INTO worker_face_templates(
            worker_id, template_reference, template_hash, registered_at, registered_by, device_info, is_active
        ) VALUES(?,?,?,?,?,?,1)
        """,
        (worker_id, ref, template_hash, now, registered_by, device_info),
    )
    template_id = int(cur.lastrowid)
    db.execute(
        "UPDATE workers SET face_template_ref=?, modified_at=? WHERE id=?",
        (ref, now, worker_id),
    )
    log_worker_audit(
        db,
        worker_id,
        "face_register",
        registered_by,
        field_name="face_template_ref",
        new_value=ref[:120],
        remarks="Face template reference stored",
    )
    return {"ok": True, "worker_id": worker_id, "template_id": template_id, "template_reference": ref}


def get_face_template_reference(db, worker_id: int) -> str | None:
    row = db.execute(
        """
        SELECT template_reference FROM worker_face_templates
        WHERE worker_id=? AND COALESCE(is_active,1)=1
        ORDER BY id DESC LIMIT 1
        """,
        (worker_id,),
    ).fetchone()
    if row:
        return str(row[0] if isinstance(row, tuple) else row["template_reference"] or "")
    worker = get_worker_master(db, worker_id, include_deleted=True)
    if worker and worker.get("face_template_ref"):
        return str(worker["face_template_ref"])
    return None


def validate_worker_for_attendance(db, worker_id: int) -> dict[str, Any]:
    worker = get_worker_master(db, worker_id)
    if not worker:
        return {"ok": False, "error": "Worker not found", "worker_id": worker_id}
    active = worker.get("status") == "Active" and not worker.get("is_deleted")
    project_id = worker.get("active_project_id") or worker.get("project_id")
    return {
        "ok": active,
        "worker_id": worker_id,
        "worker_code": worker.get("worker_code"),
        "worker_name": worker.get("worker_name"),
        "status": worker.get("status"),
        "trade": worker.get("trade"),
        "worker_type": worker.get("worker_type"),
        "subcontractor_id": worker.get("subcontractor_id"),
        "subcontractor_name": worker.get("subcontractor_name"),
        "project_id": project_id,
        "project_code": worker.get("project_code"),
        "project_name": worker.get("project_name") or worker.get("active_project_name"),
        "attendance_mode": worker.get("attendance_mode"),
        "attendance_required": bool(worker.get("attendance_required")),
        "face_template_ref": get_face_template_reference(db, worker_id),
        "approval_status": worker.get("approval_status"),
    }


def list_workers_for_project(db, project_id: int) -> list[dict[str, Any]]:
    if not project_id:
        return []
    if _table_exists(db, "subcontractors"):
        sql = """
        SELECT w.id, w.worker_code, w.worker_name, w.trade, w.skill, w.status, w.worker_category,
        w.subcontractor_id, COALESCE(NULLIF(TRIM(s.subcontractor_name), ''), NULLIF(TRIM(v.name), '')) AS subcontractor_name
        FROM workers w
        LEFT JOIN subcontractors s ON s.id=w.subcontractor_id
        LEFT JOIN vendors v ON v.id=s.vendor_id
        WHERE COALESCE(w.is_deleted,0)=0 AND w.status='Active'
        AND (
            w.project_id=? OR EXISTS (
                SELECT 1 FROM worker_project_assignments wpa
                WHERE wpa.worker_id=w.id AND wpa.project_id=? AND COALESCE(wpa.is_active,0)=1
            )
        )
        ORDER BY w.worker_name
        """
    else:
        sql = """
        SELECT w.id, w.worker_code, w.worker_name, w.trade, w.skill, w.status, w.worker_category,
        w.subcontractor_id, NULL AS subcontractor_name
        FROM workers w
        WHERE COALESCE(w.is_deleted,0)=0 AND w.status='Active'
        AND (
            w.project_id=? OR EXISTS (
                SELECT 1 FROM worker_project_assignments wpa
                WHERE wpa.worker_id=w.id AND wpa.project_id=? AND COALESCE(wpa.is_active,0)=1
            )
        )
        ORDER BY w.worker_name
        """
    rows = db.execute(sql, (project_id, project_id)).fetchall()
    return [dict(r) for r in rows]


def list_companies_for_worker_form(db) -> list[dict[str, Any]]:
    if not _table_exists(db, "companies"):
        return []
    rows = db.execute(
        "SELECT id, company_code, company_name FROM companies WHERE COALESCE(is_deleted,0)=0 AND status='Active' ORDER BY company_name"
    ).fetchall()
    return [dict(r) for r in rows]


def list_subcontractors_for_worker_form(db) -> list[dict[str, Any]]:
    if not _table_exists(db, "subcontractors"):
        return []
    rows = db.execute(
        """
        SELECT id, subcontractor_code, subcontractor_name FROM subcontractors
        WHERE COALESCE(is_deleted,0)=0 AND status='Active' ORDER BY subcontractor_name
        """
    ).fetchall()
    return [dict(r) for r in rows]


def list_projects_for_worker_form(db) -> list[dict[str, Any]]:
    if not _table_exists(db, "projects"):
        return []
    rows = db.execute(
        "SELECT id, project_code, project_name FROM projects ORDER BY project_name"
    ).fetchall()
    return [dict(r) for r in rows]


def workers_for_export(db, *, include_deleted: bool = False, **filters) -> list[dict[str, Any]]:
    listing = list_workers_master(db, include_deleted=include_deleted, per_page=10000, **filters)
    rows: list[dict[str, Any]] = []
    for item in listing["items"]:
        row = {col: item.get(col, "") for col in WORKER_EXPORT_COLUMNS}
        row["worker_type"] = item.get("worker_type") or REVERSE_WORKER_CATEGORY.get(
            item.get("worker_category") or "", ""
        )
        row["company_code"] = item.get("company_code") or ""
        row["subcontractor_code"] = item.get("subcontractor_code") or ""
        row["project_code"] = item.get("project_code") or ""
        rows.append(row)
    return rows


def export_workers_excel(db, **filters) -> BytesIO:
    from openpyxl import Workbook

    rows = workers_for_export(db, **filters)
    wb = Workbook()
    ws = wb.active
    ws.title = "Workers"
    headers = list(WORKER_EXPORT_COLUMNS)
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h, "") for h in headers])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def export_workers_csv(db, **filters) -> str:
    rows = workers_for_export(db, **filters)
    si = io.StringIO()
    writer = csv.writer(si)
    headers = list(WORKER_EXPORT_COLUMNS)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row.get(h, "") for h in headers])
    return si.getvalue()


def export_workers_pdf(db, *, report_title: str = "Worker Master Report", **filters) -> BytesIO:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas

    rows = workers_for_export(db, **filters)
    buf = BytesIO()
    page_size = landscape(A4)
    c = canvas.Canvas(buf, pagesize=page_size)
    _, height = page_size
    y = height - 40
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, f"MAXEK ERP — {report_title}")
    y -= 24
    c.setFont("Helvetica", 9)
    for row in rows[:300]:
        line = (
            f"{row.get('worker_code')} | {row.get('worker_name')} | {row.get('trade')} | "
            f"{row.get('worker_type')} | {row.get('status')} | {row.get('project_code') or '—'}"
        )
        if y < 40:
            c.showPage()
            y = height - 40
            c.setFont("Helvetica", 9)
        c.drawString(40, y, line[:150])
        y -= 14
    c.save()
    buf.seek(0)
    return buf


def worker_report(db, report_key: str, **filters) -> list[dict[str, Any]]:
    key = (report_key or "register").lower().strip()
    if key == "active":
        filters["status"] = "Active"
    elif key == "inactive":
        filters["status"] = "Inactive"
    listing = list_workers_master(db, per_page=5000, **filters)
    items = listing["items"]
    if key == "trade_wise":
        trade = filters.get("trade") or ""
        if trade:
            items = [i for i in items if i.get("trade") == trade]
        return items
    if key == "skill_wise":
        skill = filters.get("skill") or ""
        if skill:
            items = [i for i in items if skill.lower() in (i.get("skill") or "").lower()]
        return items
    if key == "project_wise":
        pid = filters.get("project_id")
        if pid:
            return list_workers_for_project(db, int(pid))
        enriched: list[dict[str, Any]] = []
        for item in items:
            row = dict(item)
            row["report_project"] = item.get("project_name") or "Unassigned"
            enriched.append(row)
        return enriched
    if key == "subcontractor_wise":
        sid = filters.get("subcontractor_id")
        if sid:
            listing = list_workers_master(db, subcontractor_id=int(sid), per_page=5000, **filters)
            return listing["items"]
        return [i for i in items if i.get("subcontractor_id")]
    return items


def worker_import_template() -> BytesIO:
    from bulk_import_service import build_xlsx_template

    return build_xlsx_template(
        list(WORKER_EXPORT_COLUMNS),
        [
            "WRK101",
            "Ramesh Kumar",
            "Company Worker",
            "CO001",
            "",
            "Brick Work",
            "Skilled",
            "PRJ001",
            "9876543210",
            "123456789012",
            "ABCDE1234F",
            "Mason",
            "Daily",
            "800",
            "Yes",
            "100",
            "8",
            "2026-01-01",
            "Active",
            "Approved",
        ],
    )


def ai_validate_worker(
    db,
    *,
    worker_id: int | None = None,
    form: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Rules-based validation hooks — duplicate detection, missing info, face ref reuse."""
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    data = dict(form or {})
    if worker_id and not data:
        row = get_worker_master(db, worker_id)
        if row:
            data = row
    name = (data.get("worker_name") or "").strip()
    mobile = re.sub(r"\D", "", data.get("mobile") or "")
    aadhaar = re.sub(r"\s", "", data.get("aadhaar_number") or "")
    code = (data.get("worker_code") or "").strip().upper()
    if name and mobile:
        dup = db.execute(
            """
            SELECT id, worker_code FROM workers
            WHERE REPLACE(REPLACE(REPLACE(mobile,' ',''),'-',''),'+','') LIKE ?
            AND COALESCE(is_deleted,0)=0 AND (? IS NULL OR id!=?)
            LIMIT 1
            """,
            (f"%{mobile[-10:]}%", worker_id, worker_id),
        ).fetchone()
        if dup:
            wc = dup[1] if isinstance(dup, tuple) else dup["worker_code"]
            issues.append({"field": "mobile", "message": f"Possible duplicate worker (mobile match: {wc})."})
    if name and aadhaar:
        dup = db.execute(
            """
            SELECT id, worker_code FROM workers
            WHERE aadhaar_number=? AND COALESCE(is_deleted,0)=0 AND (? IS NULL OR id!=?)
            LIMIT 1
            """,
            (aadhaar, worker_id, worker_id),
        ).fetchone()
        if dup:
            wc = dup[1] if isinstance(dup, tuple) else dup["worker_code"]
            issues.append({"field": "aadhaar_number", "message": f"Duplicate Aadhaar linked to worker {wc}."})
    if code:
        try:
            validate_worker_uniqueness(db, worker_code=code, worker_id=worker_id)
        except ValueError as exc:
            issues.append({"field": "worker_code", "message": str(exc)})
    if not data.get("trade"):
        warnings.append({"field": "trade", "message": "Trade is not specified."})
    if not data.get("mobile"):
        warnings.append({"field": "mobile", "message": "Mobile number is missing."})
    if not data.get("aadhaar_number"):
        warnings.append({"field": "aadhaar_number", "message": "Aadhaar is missing for identity validation."})
    face_ref = data.get("face_template_ref") or data.get("template_reference")
    if face_ref:
        th = hashlib.sha256(str(face_ref).encode("utf-8")).hexdigest()
        dup_face = db.execute(
            """
            SELECT w.worker_code FROM worker_face_templates wft
            JOIN workers w ON w.id=wft.worker_id
            WHERE wft.template_hash=? AND (? IS NULL OR wft.worker_id!=?)
            LIMIT 1
            """,
            (th, worker_id, worker_id),
        ).fetchone()
        if dup_face:
            wc = dup_face[0] if isinstance(dup_face, tuple) else dup_face["worker_code"]
            issues.append({"field": "face_template_ref", "message": f"Face template ref reused by worker {wc}."})
    return {"ok": len(issues) == 0, "issues": issues, "warnings": warnings}
