"""ERP context builder — aggregates domain data with graceful degradation."""

from __future__ import annotations

import json
from typing import Any

from user_context_service import load_user_context


def _safe_call(fn, *args, default=None, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception:
        return default


def _table_exists(db, table: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _sanitize_record(record: dict[str, Any] | None, *, exclude: tuple[str, ...] = ("password",)) -> dict[str, Any] | None:
    if not record:
        return None
    cleaned = dict(record)
    for key in exclude:
        cleaned.pop(key, None)
    return cleaned


def build_company_context(db, company_id: int | None) -> dict[str, Any] | None:
    if not company_id:
        return None
    try:
        from company_master_service import get_company

        company = _safe_call(get_company, db, int(company_id), default=None)
        return _sanitize_record(company)
    except ImportError:
        if _table_exists(db, "companies"):
            row = db.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone()
            return dict(row) if row else None
    return None


def build_user_context(db, user_id: int | None) -> dict[str, Any] | None:
    if not user_id:
        return None
    try:
        from user_management_service import get_user_master

        user = _safe_call(get_user_master, db, int(user_id), default=None)
        return _sanitize_record(user, exclude=("password", "password_hash"))
    except ImportError:
        if _table_exists(db, "users"):
            row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            return _sanitize_record(dict(row) if row else None, exclude=("password",))
    return None


def build_project_context(db, project_id: int | None) -> dict[str, Any] | None:
    if not project_id:
        return None
    try:
        from project_master_service import get_project_master, get_project_dashboard_summary

        project = _safe_call(get_project_master, db, int(project_id), default=None)
        if not project:
            return None
        summary = _safe_call(get_project_dashboard_summary, db, int(project_id), default={})
        return {"project": project, "dashboard_summary": summary or {}}
    except ImportError:
        if _table_exists(db, "projects"):
            row = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            return {"project": dict(row)} if row else None
    return None


def build_client_context(db, client_id: int | None) -> dict[str, Any] | None:
    if not client_id:
        return None
    try:
        from client_master_service import get_client_master

        client = _safe_call(get_client_master, db, int(client_id), default=None)
        return _sanitize_record(client)
    except ImportError:
        if _table_exists(db, "clients"):
            row = db.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
            return dict(row) if row else None
    return None


def build_vendor_context(db, vendor_id: int | None) -> dict[str, Any] | None:
    if not vendor_id:
        return None
    try:
        from vendor_master_service import get_vendor_master

        vendor = _safe_call(get_vendor_master, db, int(vendor_id), default=None)
        return _sanitize_record(vendor)
    except ImportError:
        if _table_exists(db, "vendors"):
            row = db.execute("SELECT * FROM vendors WHERE id=?", (vendor_id,)).fetchone()
            return dict(row) if row else None
    return None


def build_document_context(db, document_id: int | None) -> dict[str, Any] | None:
    if not document_id:
        return None
    try:
        from document_management_service import get_document

        document = _safe_call(get_document, db, int(document_id), default=None)
        if not document:
            return None
        # Omit large binary paths from AI context
        trimmed = dict(document)
        trimmed.pop("file_path", None)
        trimmed.pop("storage_path", None)
        return trimmed
    except ImportError:
        if _table_exists(db, "documents"):
            row = db.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
            return dict(row) if row else None
    return None


def build_hr_context(db, user_id: int | None, company_id: int | None) -> dict[str, Any]:
    payload: dict[str, Any] = {"employees_sample": [], "departments_sample": []}
    try:
        from employee_master_service import list_employees_master
        from department_master_service import list_departments_master

        employees = _safe_call(
            list_employees_master,
            db,
            {"company_id": company_id, "per_page": 5},
            default={"items": []},
        )
        departments = _safe_call(
            list_departments_master,
            db,
            {"company_id": company_id, "per_page": 5},
            default={"items": []},
        )
        payload["employees_sample"] = (employees or {}).get("items", [])[:5]
        payload["departments_sample"] = (departments or {}).get("items", [])[:5]
    except ImportError:
        if _table_exists(db, "staff"):
            rows = db.execute("SELECT id, employee_code, staff_name, department, status FROM staff LIMIT 5").fetchall()
            payload["employees_sample"] = [dict(row) for row in rows]
    if user_id:
        user = build_user_context(db, user_id)
        if user:
            payload["requesting_user"] = user
    return payload


def build_inventory_context(db, company_id: int | None, project_id: int | None) -> dict[str, Any]:
    payload: dict[str, Any] = {"store_signals": []}
    for table, label in (
        ("material_requests", "material_requests"),
        ("purchase_orders", "purchase_orders"),
        ("store_receipts", "store_receipts"),
        ("store_issues", "store_issues"),
    ):
        if not _table_exists(db, table):
            continue
        sql = f"SELECT COUNT(*) AS total FROM {table}"
        params: list[Any] = []
        if project_id and _column_exists(db, table, "project_id"):
            sql += " WHERE project_id=?"
            params.append(project_id)
        count_row = db.execute(sql, tuple(params)).fetchone()
        payload["store_signals"].append(
            {"table": label, "count": int(count_row["total"] if count_row else 0)}
        )
    payload["company_id"] = company_id
    payload["project_id"] = project_id
    return payload


def build_finance_context(db, company_id: int | None) -> dict[str, Any]:
    payload: dict[str, Any] = {"accounts_signals": []}
    try:
        from accounts_service import accounts_hub_stats

        stats = _safe_call(accounts_hub_stats, db, default={})
        if stats:
            payload["accounts_hub"] = stats
    except ImportError:
        pass
    for table in ("account_expenses", "payment_vouchers", "receipt_vouchers"):
        if _table_exists(db, table):
            row = db.execute(f"SELECT COUNT(*) AS total FROM {table}").fetchone()
            payload["accounts_signals"].append(
                {"table": table, "count": int(row["total"] if row else 0)}
            )
    payload["company_id"] = company_id
    return payload


def build_crm_context(db, company_id: int | None) -> dict[str, Any]:
    payload: dict[str, Any] = {"clients_sample": []}
    try:
        from client_master_service import list_clients_master

        listing = _safe_call(
            list_clients_master,
            db,
            {"company_id": company_id, "per_page": 5},
            default={"items": []},
        )
        payload["clients_sample"] = (listing or {}).get("items", [])[:5]
    except ImportError:
        if _table_exists(db, "clients"):
            rows = db.execute("SELECT id, client_name, company_name, status FROM clients LIMIT 5").fetchall()
            payload["clients_sample"] = [dict(row) for row in rows]
    return payload


def _column_exists(db, table: str, column: str) -> bool:
    if not _table_exists(db, table):
        return False
    cols = {row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
    return column in cols


def build_erp_context(
    db,
    *,
    user_id: int | None = None,
    company_id: int | None = None,
    branch_id: int | None = None,
    project_id: int | None = None,
    client_id: int | None = None,
    vendor_id: int | None = None,
    document_id: int | None = None,
    session_data: dict[str, Any] | None = None,
    hints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Assemble structured ERP context across domains.

    Missing tables or services degrade gracefully to partial context.
    """
    session_data = session_data or {}
    hints = hints or {}

    if company_id is None:
        company_id = session_data.get("company_id")
    if branch_id is None:
        branch_id = session_data.get("branch_id")
    if project_id is None:
        project_id = session_data.get("selected_project_id") or session_data.get("project_id")
    if user_id is None:
        user_id = session_data.get("user_id")

    work_context = _safe_call(load_user_context, db, int(user_id), default=None) if user_id else None

    context: dict[str, Any] = {
        "company": build_company_context(db, company_id),
        "user": build_user_context(db, user_id),
        "work_context": work_context,
        "project": build_project_context(db, project_id or (work_context or {}).get("project_id")),
        "client": build_client_context(db, client_id or hints.get("client_id")),
        "vendor": build_vendor_context(db, vendor_id or hints.get("vendor_id")),
        "document": build_document_context(db, document_id or hints.get("document_id")),
        "inventory": build_inventory_context(db, company_id, project_id),
        "finance": build_finance_context(db, company_id),
        "crm": build_crm_context(db, company_id),
        "hr": build_hr_context(db, user_id, company_id),
        "session": {
            "company_id": company_id,
            "branch_id": branch_id,
            "project_id": project_id,
            "username": session_data.get("username"),
            "role": session_data.get("role"),
        },
        "hints": hints,
    }
    return context


def serialize_context(context: dict[str, Any]) -> str:
    """JSON-serialize context for logging (best-effort)."""

    def _default(value: Any) -> str:
        return str(value)

    return json.dumps(context, default=_default, ensure_ascii=False)
