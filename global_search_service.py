"""Universal ERP global search across operational modules."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlencode

SEARCH_LIMIT_DEFAULT = 12
SEARCH_LIMIT_MAX = 30

# category key → search specs (table must exist; safe LIKE on label columns)
SEARCH_REGISTRY: dict[str, list[dict[str, Any]]] = {
    "project": [
        {
            "table": "projects",
            "id_col": "id",
            "label_sql": "COALESCE(project_name, project_code, '')",
            "subtitle_sql": "COALESCE(location, status, '')",
            "endpoint": "projects",
            "view_param": "view",
        },
    ],
    "boq": [
        {
            "table": "boq_master",
            "id_col": "id",
            "label_sql": "COALESCE(boq_number, boq_name, '')",
            "subtitle_sql": "COALESCE(status, '')",
            "endpoint": "boq_management",
            "view_param": "view",
        },
    ],
    "dpr": [
        {
            "table": "dpr_entries",
            "id_col": "id",
            "label_sql": "COALESCE(dpr_number, CAST(id AS TEXT), '')",
            "subtitle_sql": "COALESCE(entry_date, status, '')",
            "endpoint": "dpr_entry",
            "view_param": "view",
        },
        {
            "table": "dpr_measurements",
            "id_col": "id",
            "label_sql": "COALESCE(measurement_ref, CAST(id AS TEXT), '')",
            "subtitle_sql": "COALESCE(work_date, '')",
            "endpoint": "dpr_entry",
            "view_param": "view",
        },
    ],
    "material": [
        {
            "table": "material_requests",
            "id_col": "id",
            "label_sql": "COALESCE(request_number, CAST(id AS TEXT), '')",
            "subtitle_sql": "COALESCE(approval_status, '')",
            "endpoint": "material_request",
            "view_param": "view",
        },
        {
            "table": "materials",
            "id_col": "id",
            "label_sql": "COALESCE(code, name, '')",
            "subtitle_sql": "COALESCE(category, unit, '')",
            "endpoint": "store",
            "view_param": None,
        },
    ],
    "purchase_request": [
        {
            "table": "purchase_requests",
            "id_col": "id",
            "label_sql": "COALESCE(request_number, CAST(id AS TEXT), '')",
            "subtitle_sql": "COALESCE(approval_status, '')",
            "endpoint": "purchase_request",
            "view_param": "view",
        },
    ],
    "purchase_order": [
        {
            "table": "purchase_orders",
            "id_col": "id",
            "label_sql": "COALESCE(po_number, CAST(id AS TEXT), '')",
            "subtitle_sql": "COALESCE(approval_status, vendor_name, '')",
            "endpoint": "purchase_orders",
            "view_param": "view",
        },
    ],
    "grn": [
        {
            "table": "store_receipts",
            "id_col": "id",
            "label_sql": "COALESCE(grn_number, receipt_number, CAST(id AS TEXT), '')",
            "subtitle_sql": "COALESCE(approval_status, receipt_date, '')",
            "endpoint": "store_receipt",
            "view_param": "view",
        },
    ],
    "employee": [
        {
            "table": "staff",
            "id_col": "id",
            "label_sql": "COALESCE(staff_name, employee_code, '')",
            "subtitle_sql": "COALESCE(designation, department, '')",
            "endpoint": "staff",
            "view_param": "view",
        },
        {
            "table": "workers",
            "id_col": "id",
            "label_sql": "COALESCE(worker_name, worker_code, '')",
            "subtitle_sql": "COALESCE(designation, worker_category, '')",
            "endpoint": "workers",
            "view_param": "view",
        },
    ],
    "vendor": [
        {
            "table": "vendors",
            "id_col": "id",
            "label_sql": "COALESCE(vendor_name, vendor_code, '')",
            "subtitle_sql": "COALESCE(vendor_type, gstin, '')",
            "endpoint": "purchase_vendors",
            "view_param": "view",
        },
    ],
    "subcontractor": [
        {
            "table": "subcontractors",
            "id_col": "id",
            "label_sql": "COALESCE(subcontractor_name, code, '')",
            "subtitle_sql": "COALESCE(trade, status, '')",
            "endpoint": "subcontractors",
            "view_param": "view",
        },
        {
            "table": "subcontract_requests",
            "id_col": "id",
            "label_sql": "COALESCE(request_number, CAST(id AS TEXT), '')",
            "subtitle_sql": "COALESCE(approval_status, '')",
            "endpoint": "subcontract_request",
            "view_param": "view",
        },
    ],
    "vehicle": [
        {
            "table": "fleet_vehicles",
            "id_col": "id",
            "label_sql": "COALESCE(vehicle_number, registration_no, '')",
            "subtitle_sql": "COALESCE(vehicle_type, make_model, '')",
            "endpoint": "fleet_vehicles",
            "view_param": "view",
        },
    ],
    "payroll": [
        {
            "table": "payroll_records",
            "id_col": "id",
            "label_sql": "COALESCE(payroll_month, CAST(id AS TEXT), '')",
            "subtitle_sql": "COALESCE(approval_status, '')",
            "endpoint": "payroll",
            "view_param": "view",
        },
        {
            "table": "salary",
            "id_col": "id",
            "label_sql": "COALESCE(month, CAST(id AS TEXT), '')",
            "subtitle_sql": "COALESCE(payment_status, approval_status, '')",
            "endpoint": "salary",
            "view_param": "view",
        },
    ],
    "petty_cash": [
        {
            "table": "petty_cash_requests",
            "id_col": "id",
            "label_sql": "COALESCE(request_number, CAST(id AS TEXT), '')",
            "subtitle_sql": "COALESCE(approval_status, purpose, '')",
            "endpoint": "petty_cash",
            "view_param": "view",
        },
    ],
    "bill": [
        {
            "table": "client_bills",
            "id_col": "id",
            "label_sql": "COALESCE(bill_number, invoice_number, CAST(id AS TEXT), '')",
            "subtitle_sql": "COALESCE(approval_status, bill_date, '')",
            "endpoint": "client_billing_register",
            "view_param": "view",
        },
    ],
    "work_order": [
        {
            "table": "subcontract_work_orders",
            "id_col": "id",
            "label_sql": "COALESCE(work_order_number, CAST(id AS TEXT), '')",
            "subtitle_sql": "COALESCE(approval_status, status, '')",
            "endpoint": "subcontract_work_orders",
            "view_param": "view",
        },
    ],
    "document": [
        {
            "table": "project_documents",
            "id_col": "id",
            "label_sql": "COALESCE(document_name, file_name, CAST(id AS TEXT), '')",
            "subtitle_sql": "COALESCE(document_type, '')",
            "endpoint": "project_documents",
            "view_param": "view_document",
        },
        {
            "table": "corporate_dms_documents",
            "id_col": "id",
            "label_sql": "COALESCE(title, document_code, CAST(id AS TEXT), '')",
            "subtitle_sql": "COALESCE(category, '')",
            "endpoint": "corporate_dms",
            "view_param": "view",
        },
    ],
}

CATEGORY_ALIASES = {
    "material_request": "material",
    "purchase_order": "purchase_order",
    "purchase_request": "purchase_request",
    "all": None,
}


def _table_exists(db, table: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _column_exists(db, table: str, column: str) -> bool:
    if not _table_exists(db, table):
        return False
    cols = [r[1] for r in db.execute(f"PRAGMA table_info({table})").fetchall()]
    return column in cols


def _soft_delete_clause(db, table: str) -> str:
    if _column_exists(db, table, "is_deleted"):
        return " AND (is_deleted IS NULL OR is_deleted=0)"
    return ""


def build_result_url(endpoint: str, record_id: int, view_param: str | None) -> str:
    """Return a path with query string for opening a record (Flask url_for done in route layer)."""
    if view_param:
        return f"?{view_param}={record_id}"
    return ""


def search_category_keys() -> list[str]:
    return list(SEARCH_REGISTRY.keys())


def _search_spec(db, spec: dict, term: str, limit: int) -> list[dict[str, Any]]:
    table = spec["table"]
    if not _table_exists(db, table):
        return []
    label_sql = spec["label_sql"]
    subtitle_sql = spec.get("subtitle_sql", "''")
    id_col = spec["id_col"]
    like = f"%{term}%"
    deleted = _soft_delete_clause(db, table)
    sql = (
        f"SELECT {id_col} AS id, ({label_sql}) AS label, ({subtitle_sql}) AS subtitle "
        f"FROM {table} WHERE ({label_sql}) LIKE ? OR ({subtitle_sql}) LIKE ?{deleted} "
        f"ORDER BY {id_col} DESC LIMIT ?"
    )
    try:
        rows = db.execute(sql, (like, like, limit)).fetchall()
    except Exception:
        return []
    results = []
    for row in rows:
        rid = row["id"] if hasattr(row, "keys") else row[0]
        label = row["label"] if hasattr(row, "keys") else row[1]
        subtitle = row["subtitle"] if hasattr(row, "keys") else row[2]
        if not str(label or "").strip():
            label = f"#{rid}"
        results.append(
            {
                "id": int(rid),
                "label": str(label).strip(),
                "subtitle": str(subtitle or "").strip(),
                "table": table,
                "endpoint": spec["endpoint"],
                "view_param": spec.get("view_param") or "view",
            }
        )
    return results


def global_search(
    db,
    term: str,
    category: str | None = None,
    limit: int = SEARCH_LIMIT_DEFAULT,
) -> list[dict[str, Any]]:
    term = (term or "").strip()
    if len(term) < 2:
        return []
    limit = max(1, min(limit, SEARCH_LIMIT_MAX))
    category = CATEGORY_ALIASES.get(category or "", category)
    categories = [category] if category and category in SEARCH_REGISTRY else list(SEARCH_REGISTRY.keys())
    per_cat = max(2, limit // max(1, len(categories)))
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for cat in categories:
        for spec in SEARCH_REGISTRY.get(cat, []):
            for hit in _search_spec(db, spec, term, per_cat):
                key = (hit["table"], hit["id"])
                if key in seen:
                    continue
                seen.add(key)
                hit["category"] = cat
                merged.append(hit)
                if len(merged) >= limit:
                    return merged
    return merged
