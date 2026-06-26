"""Load module data for standardized corporate stub reports."""

from __future__ import annotations

from typing import Any

STUB_TEMPLATE = "reports/corporate_tabular_report.html"

REPORT_COLUMNS: dict[str, list[dict[str, str]]] = {
    "dpr_report": [
        {"key": "report_date", "label": "Date"},
        {"key": "project_code", "label": "Project"},
        {"key": "boq_number", "label": "BOQ No"},
        {"key": "boq_description", "label": "Description"},
        {"key": "unit", "label": "Unit"},
        {"key": "calculated_quantity", "label": "Qty", "class": "num"},
        {"key": "approval_status", "label": "Approval"},
    ],
    "quantity_report": [
        {"key": "project_code", "label": "Project"},
        {"key": "boq_number", "label": "BOQ No"},
        {"key": "description", "label": "Description"},
        {"key": "unit", "label": "Unit"},
        {"key": "boq_qty", "label": "BOQ Qty", "class": "num"},
        {"key": "executed_qty", "label": "Executed", "class": "num"},
        {"key": "balance_qty", "label": "Balance", "class": "num"},
        {"key": "completion_pct", "label": "% Done", "class": "num"},
    ],
    "progress_report": [
        {"key": "report_date", "label": "Date"},
        {"key": "project_code", "label": "Project"},
        {"key": "entry_count", "label": "Entries", "class": "num"},
        {"key": "total_qty", "label": "Total Qty", "class": "num"},
    ],
    "material_reconciliation": [
        {"key": "material_code", "label": "Code"},
        {"key": "material_name", "label": "Material"},
        {"key": "unit", "label": "Unit"},
        {"key": "received", "label": "Received", "class": "num"},
        {"key": "issued", "label": "Issued", "class": "num"},
        {"key": "balance", "label": "Balance", "class": "num"},
    ],
    "payment_voucher": [
        {"key": "payment_number", "label": "Voucher No"},
        {"key": "payment_date", "label": "Date"},
        {"key": "payee_name", "label": "Payee"},
        {"key": "amount", "label": "Amount", "class": "num"},
        {"key": "payment_mode", "label": "Mode"},
        {"key": "reference_no", "label": "Reference"},
    ],
    "receipt_voucher": [
        {"key": "receipt_number", "label": "Voucher No"},
        {"key": "receipt_date", "label": "Date"},
        {"key": "received_from", "label": "Received From"},
        {"key": "amount", "label": "Amount", "class": "num"},
        {"key": "receipt_mode", "label": "Mode"},
        {"key": "reference_no", "label": "Reference"},
    ],
    "fuel_register": [
        {"key": "log_date", "label": "Date"},
        {"key": "registration_number", "label": "Vehicle"},
        {"key": "driver_name", "label": "Driver"},
        {"key": "total_km", "label": "KM", "class": "num"},
        {"key": "fuel_liters", "label": "Fuel (L)", "class": "num"},
        {"key": "project_code", "label": "Project"},
        {"key": "purpose", "label": "Purpose"},
    ],
    "grn": [
        {"key": "grn_number", "label": "GRN No"},
        {"key": "grn_date", "label": "Date"},
        {"key": "po_number", "label": "PO No"},
        {"key": "vendor_name", "label": "Vendor"},
        {"key": "total_amount", "label": "Amount", "class": "num"},
        {"key": "approval_status", "label": "Status"},
    ],
    "material_issue_note": [
        {"key": "issue_number", "label": "Issue No"},
        {"key": "issue_date", "label": "Date"},
        {"key": "issued_to", "label": "Issued To"},
        {"key": "department", "label": "Department"},
        {"key": "approval_status", "label": "Status"},
    ],
}


def get_report_columns(slug: str) -> list[dict[str, str]]:
    return REPORT_COLUMNS.get(slug, [])


def _table_exists(db, table: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _rows(db, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    try:
        return [dict(r) for r in db.execute(sql, params).fetchall()]
    except Exception:
        return []


def get_stub_template(slug: str, has_data: bool) -> str:
    if has_data and slug in REPORT_COLUMNS:
        return STUB_TEMPLATE
    return "report_standard_print.html"


def load_standard_report_data(
    db,
    slug: str,
    *,
    project_id: int | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    loaders = {
        "dpr_report": _load_dpr_report,
        "quantity_report": _load_quantity_report,
        "progress_report": _load_progress_report,
        "material_reconciliation": _load_material_reconciliation,
        "payment_voucher": _load_payment_voucher,
        "receipt_voucher": _load_receipt_voucher,
        "fuel_register": _load_fuel_register,
        "grn": _load_grn_report,
        "material_issue_note": _load_material_issue,
    }
    loader = loaders.get(slug)
    if not loader:
        return {"stub": True, "rows": [], "summary": {}}
    return loader(db, project_id=project_id, limit=limit)


def _project_clause(project_id: int | None, alias: str = "m") -> tuple[str, list]:
    if project_id:
        return f" AND {alias}.project_id=?", [project_id]
    return "", []


def _load_dpr_report(db, *, project_id: int | None, limit: int) -> dict[str, Any]:
    if not _table_exists(db, "dpr_measurements"):
        return {"stub": True, "rows": [], "summary": {}}
    clause, params = _project_clause(project_id)
    rows = _rows(
        db,
        f"""
        SELECT m.id, m.report_date, m.boq_number, m.boq_description, m.unit,
               m.calculated_quantity, m.approval_status, m.dpr_status,
               p.project_code, p.project_name
        FROM dpr_measurements m
        LEFT JOIN projects p ON m.project_id = p.id
        WHERE 1=1{clause}
        ORDER BY m.report_date DESC, m.id DESC
        LIMIT ?
        """,
        tuple(params + [limit]),
    )
    return {
        "stub": not rows,
        "rows": rows,
        "summary": {"total_records": len(rows), "report_type": "Daily Progress Report"},
    }


def _load_quantity_report(db, *, project_id: int | None, limit: int) -> dict[str, Any]:
    if not _table_exists(db, "boq_items"):
        return {"stub": True, "rows": [], "summary": {}}
    clause, params = _project_clause(project_id, "b")
    rows = _rows(
        db,
        f"""
        SELECT b.boq_number, b.description, b.unit, b.quantity AS boq_qty,
               COALESCE(SUM(m.calculated_quantity), 0) AS executed_qty,
               p.project_code, p.project_name
        FROM boq_items b
        LEFT JOIN projects p ON b.project_id = p.id
        LEFT JOIN dpr_measurements m ON m.boq_item_id = b.id
        WHERE 1=1{clause}
        GROUP BY b.id
        ORDER BY b.boq_number
        LIMIT ?
        """,
        tuple(params + [limit]),
    )
    for row in rows:
        boq = float(row.get("boq_qty") or 0)
        exe = float(row.get("executed_qty") or 0)
        row["balance_qty"] = round(boq - exe, 4)
        row["completion_pct"] = round((exe / boq * 100) if boq else 0, 2)
    return {
        "stub": not rows,
        "rows": rows,
        "summary": {"total_items": len(rows), "report_type": "Quantity Report"},
    }


def _load_progress_report(db, *, project_id: int | None, limit: int) -> dict[str, Any]:
    if not _table_exists(db, "dpr_measurements"):
        return {"stub": True, "rows": [], "summary": {}}
    clause, params = _project_clause(project_id)
    rows = _rows(
        db,
        f"""
        SELECT m.report_date, COUNT(*) AS entry_count,
               SUM(m.calculated_quantity) AS total_qty,
               p.project_code, p.project_name
        FROM dpr_measurements m
        LEFT JOIN projects p ON m.project_id = p.id
        WHERE 1=1{clause}
        GROUP BY m.report_date, m.project_id
        ORDER BY m.report_date DESC
        LIMIT ?
        """,
        tuple(params + [limit]),
    )
    return {
        "stub": not rows,
        "rows": rows,
        "summary": {"total_days": len(rows), "report_type": "Progress Report"},
    }


def _load_material_reconciliation(db, *, project_id: int | None, limit: int) -> dict[str, Any]:
    if not _table_exists(db, "stock_ledger"):
        return {"stub": True, "rows": [], "summary": {}}
    clause, params = _project_clause(project_id, "sl")
    rows = _rows(
        db,
        f"""
        SELECT mat.code AS material_code, mat.name AS material_name, mat.unit,
               SUM(CASE WHEN sl.movement_type IN ('GRN_IN','TRANSFER_IN') THEN sl.quantity ELSE 0 END) AS received,
               SUM(CASE WHEN sl.movement_type IN ('ISSUE_OUT','TRANSFER_OUT') THEN sl.quantity ELSE 0 END) AS issued,
               SUM(sl.quantity) AS balance
        FROM stock_ledger sl
        LEFT JOIN materials mat ON sl.material_id = mat.id
        WHERE 1=1{clause}
        GROUP BY sl.material_id
        ORDER BY mat.code
        LIMIT ?
        """,
        tuple(params + [limit]),
    )
    return {
        "stub": not rows,
        "rows": rows,
        "summary": {"total_materials": len(rows), "report_type": "Material Reconciliation"},
    }


def _load_payment_voucher(db, *, project_id: int | None, limit: int) -> dict[str, Any]:
    if not _table_exists(db, "bank_payments"):
        return {"stub": True, "rows": [], "summary": {}}
    rows = _rows(
        db,
        """
        SELECT payment_number, payment_date, payee_name, amount, payment_mode,
               bank_account, reference_no, remarks, project_id
        FROM bank_payments
        ORDER BY payment_date DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    )
    if project_id:
        rows = [r for r in rows if r.get("project_id") == project_id]
    total = round(sum(float(r.get("amount") or 0) for r in rows), 2)
    return {
        "stub": not rows,
        "rows": rows,
        "summary": {"total_payments": len(rows), "total_amount": total, "report_type": "Payment Voucher Register"},
    }


def _load_receipt_voucher(db, *, project_id: int | None, limit: int) -> dict[str, Any]:
    if not _table_exists(db, "bank_receipts"):
        return {"stub": True, "rows": [], "summary": {}}
    rows = _rows(
        db,
        """
        SELECT receipt_number, receipt_date, received_from, amount, receipt_mode,
               bank_account, reference_no, remarks, project_id
        FROM bank_receipts
        ORDER BY receipt_date DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    )
    if project_id:
        rows = [r for r in rows if r.get("project_id") == project_id]
    total = round(sum(float(r.get("amount") or 0) for r in rows), 2)
    return {
        "stub": not rows,
        "rows": rows,
        "summary": {"total_receipts": len(rows), "total_amount": total, "report_type": "Receipt Voucher Register"},
    }


def _load_fuel_register(db, *, project_id: int | None, limit: int) -> dict[str, Any]:
    if not _table_exists(db, "fleet_running_log"):
        return {"stub": True, "rows": [], "summary": {}}
    clause, params = _project_clause(project_id, "l")
    rows = _rows(
        db,
        f"""
        SELECT l.log_date, v.registration_number, l.driver_name,
               l.start_km, l.end_km, l.total_km, l.fuel_liters, l.purpose,
               p.project_code, p.project_name
        FROM fleet_running_log l
        LEFT JOIN fleet_vehicles v ON l.vehicle_id = v.id
        LEFT JOIN projects p ON l.project_id = p.id
        WHERE 1=1{clause}
        ORDER BY l.log_date DESC, l.id DESC
        LIMIT ?
        """,
        tuple(params + [limit]),
    )
    total_fuel = round(sum(float(r.get("fuel_liters") or 0) for r in rows), 2)
    return {
        "stub": not rows,
        "rows": rows,
        "summary": {"total_entries": len(rows), "total_fuel_liters": total_fuel, "report_type": "Fuel Register"},
    }


def _load_grn_report(db, *, project_id: int | None, limit: int) -> dict[str, Any]:
    if not _table_exists(db, "grn_headers"):
        return {"stub": True, "rows": [], "summary": {}}
    clause, params = _project_clause(project_id, "g")
    rows = _rows(
        db,
        f"""
        SELECT g.grn_number, g.grn_date, g.po_number, g.vendor_name,
               g.total_amount, g.approval_status, p.project_code, p.project_name
        FROM grn_headers g
        LEFT JOIN projects p ON g.project_id = p.id
        WHERE 1=1{clause}
        ORDER BY g.grn_date DESC, g.id DESC
        LIMIT ?
        """,
        tuple(params + [limit]),
    )
    return {
        "stub": not rows,
        "rows": rows,
        "summary": {"total_grn": len(rows), "report_type": "GRN Register"},
    }


def _load_material_issue(db, *, project_id: int | None, limit: int) -> dict[str, Any]:
    if not _table_exists(db, "material_issues"):
        return {"stub": True, "rows": [], "summary": {}}
    clause, params = _project_clause(project_id, "mi")
    rows = _rows(
        db,
        f"""
        SELECT mi.issue_number, mi.issue_date, mi.issued_to, mi.department,
               mi.approval_status, p.project_code, p.project_name
        FROM material_issues mi
        LEFT JOIN projects p ON mi.project_id = p.id
        WHERE 1=1{clause}
        ORDER BY mi.issue_date DESC, mi.id DESC
        LIMIT ?
        """,
        tuple(params + [limit]),
    )
    return {
        "stub": not rows,
        "rows": rows,
        "summary": {"total_issues": len(rows), "report_type": "Material Issue Register"},
    }
