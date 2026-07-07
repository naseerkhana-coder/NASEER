"""Worker Master bulk import — validate and save spreadsheet rows."""

from __future__ import annotations

from typing import Any

from bulk_import_service import error_row, validate_duplicates, validate_pan, validation_result
from company_master_service import validate_phone
from store_service import TRADE_CATEGORY_OPTIONS
from worker_master_service import (
    SALARY_TYPES,
    WORKER_STATUSES,
    WORKER_TYPES,
    log_worker_audit,
    normalize_worker_type,
    save_worker_master,
    validate_aadhaar_number,
    validate_worker_uniqueness,
    worker_category_from_type,
)


def _row_val(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        val = str(row.get(key) or "").strip()
        if val:
            return val
    return ""


def _resolve_company_id(db, code: str) -> int | None:
    if not code:
        return None
    hit = db.execute(
        "SELECT id FROM companies WHERE UPPER(company_code)=? AND COALESCE(is_deleted,0)=0 LIMIT 1",
        (code.upper(),),
    ).fetchone()
    return int(hit[0]) if hit else None


def _resolve_subcontractor_id(db, code: str) -> int | None:
    if not code:
        return None
    hit = db.execute(
        "SELECT id FROM subcontractors WHERE UPPER(subcontractor_code)=? AND COALESCE(is_deleted,0)=0 LIMIT 1",
        (code.upper(),),
    ).fetchone()
    return int(hit[0]) if hit else None


def _resolve_project_id(db, code: str) -> int | None:
    if not code:
        return None
    hit = db.execute(
        "SELECT id FROM projects WHERE UPPER(project_code)=? LIMIT 1",
        (code.upper(),),
    ).fetchone()
    return int(hit[0]) if hit else None


def validate_worker_import_rows(db, rows: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    errors.extend(validate_duplicates(rows, "worker_code", "Worker Code"))
    parsed: list[dict] = []
    for row in rows:
        code = _row_val(row, "worker_code", "code")
        name = _row_val(row, "worker_name", "name")
        if not code and not name:
            continue
        row_num = row.get("_row_num", "?")
        if not name:
            errors.append(error_row(row_num, "Worker Name", "Name is required.", "Enter worker name."))
            continue
        worker_type = normalize_worker_type(_row_val(row, "worker_type", "worker_category") or "Company Worker")
        trade = _row_val(row, "trade")
        if not trade:
            errors.append(error_row(row_num, "Trade", "Trade is required.", "Enter trade."))
            continue
        if trade not in TRADE_CATEGORY_OPTIONS:
            pass
        mobile = _row_val(row, "mobile")
        aadhaar = _row_val(row, "aadhaar_number", "aadhaar")
        pan = _row_val(row, "pan_number", "pan").upper()
        if mobile:
            try:
                validate_phone(mobile)
            except ValueError as exc:
                errors.append(error_row(row_num, "Mobile", str(exc), "Enter valid mobile."))
        if aadhaar:
            try:
                validate_aadhaar_number(aadhaar)
            except ValueError as exc:
                errors.append(error_row(row_num, "Aadhaar", str(exc), "Enter 12-digit Aadhaar."))
        errors.extend(validate_pan(pan, "PAN", row_num))
        status = _row_val(row, "status") or "Active"
        if status not in WORKER_STATUSES:
            errors.append(error_row(row_num, "Status", f"Invalid status '{status}'.", "Use Active or Inactive."))
        salary_type = _row_val(row, "salary_type") or "Daily"
        if salary_type not in SALARY_TYPES:
            errors.append(error_row(row_num, "Salary Type", f"Invalid salary type '{salary_type}'.", "Use Monthly/Daily/Hourly."))
        sub_code = _row_val(row, "subcontractor_code")
        if worker_category_from_type(worker_type) == "Sub Contractor Staff" and not sub_code:
            errors.append(error_row(row_num, "Subcontractor Code", "Required for subcontractor workers.", "Enter sub code."))
        row["worker_code"] = code
        row["worker_name"] = name
        row["worker_type"] = worker_type
        row["trade"] = trade
        row["status"] = status
        row["salary_type"] = salary_type
        row["company_id_resolved"] = _resolve_company_id(db, _row_val(row, "company_code"))
        row["subcontractor_id_resolved"] = _resolve_subcontractor_id(db, sub_code)
        row["project_id_resolved"] = _resolve_project_id(db, _row_val(row, "project_code"))
        parsed.append(row)
    return parsed, errors


def validate_worker_import(db, rows: list[dict[str, Any]]) -> dict[str, Any]:
    parsed, errors = validate_worker_import_rows(db, rows)
    codes_in_file: set[str] = set()
    for row in parsed:
        row_num = row.get("_row_num", "?")
        code = _row_val(row, "worker_code").upper()
        if code:
            if code in codes_in_file:
                errors.append(error_row(row_num, "Worker Code", f"Duplicate code '{code}' in file.", "Use unique codes."))
            codes_in_file.add(code)
        if code:
            try:
                validate_worker_uniqueness(db, worker_code=code, worker_id=None)
            except ValueError as exc:
                errors.append(error_row(row_num, "Uniqueness", str(exc), "Fix worker code."))
        if row.get("subcontractor_id_resolved") is None and row.get("worker_type") == "Subcontractor Worker":
            sub_code = _row_val(row, "subcontractor_code")
            if sub_code:
                errors.append(
                    error_row(row_num, "Subcontractor Code", f"Subcontractor '{sub_code}' not found.", "Check sub code.")
                )
    result = validation_result(parsed, errors)
    result["parsed_rows"] = parsed
    return result


def save_worker_import(
    db,
    rows: list[dict[str, Any]],
    *,
    username: str,
    filename: str = "",
    customer_id: int | None = None,
) -> dict[str, Any]:
    imported = 0
    for row in rows:
        form = {
            "worker_code": _row_val(row, "worker_code"),
            "worker_name": _row_val(row, "worker_name"),
            "worker_type": row.get("worker_type") or "Company Worker",
            "company_id": row.get("company_id_resolved") or "",
            "subcontractor_id": row.get("subcontractor_id_resolved") or "",
            "project_id": row.get("project_id_resolved") or "",
            "trade": _row_val(row, "trade"),
            "skill": _row_val(row, "skill"),
            "designation": _row_val(row, "designation"),
            "mobile": _row_val(row, "mobile"),
            "aadhaar_number": _row_val(row, "aadhaar_number"),
            "pan_number": _row_val(row, "pan_number"),
            "salary_type": _row_val(row, "salary_type") or "Daily",
            "salary_amount": _row_val(row, "salary_amount"),
            "ot_applicable": _row_val(row, "ot_applicable") or "No",
            "ot_rate": _row_val(row, "ot_rate"),
            "working_hours": _row_val(row, "working_hours") or "8",
            "joining_date": _row_val(row, "joining_date"),
            "assignment_start_date": _row_val(row, "joining_date"),
            "status": _row_val(row, "status") or "Active",
        }
        new_id = save_worker_master(db, form, username, customer_id=customer_id)
        log_worker_audit(db, new_id, "import", username, remarks=f"Imported from {filename or 'spreadsheet'}")
        imported += 1
    return {"ok": True, "imported": imported}
