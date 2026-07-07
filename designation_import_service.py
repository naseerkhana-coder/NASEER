"""Designation Master bulk import — validate and save spreadsheet rows."""

from __future__ import annotations

from typing import Any

from bulk_import_service import error_row, validation_result
from company_master_service import get_company, list_companies
from department_master_service import list_departments_master
from designation_master_service import (
    DESIGNATION_STATUSES,
    WORKFLOW_ROLE_DEFAULTS,
    log_designation_audit,
    save_designation_master,
    validate_designation_uniqueness,
)


def _row_val(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        val = str(row.get(key) or "").strip()
        if val:
            return val
    return ""


def _resolve_company_id(db, row: dict[str, Any]) -> int | None:
    cid = row.get("company_id")
    if cid:
        try:
            return int(cid)
        except (TypeError, ValueError):
            pass
    code = _row_val(row, "company_code", "Company Code")
    if not code:
        return None
    listing = list_companies(db, search=code, per_page=50)
    for item in listing.get("items", []):
        if str(item.get("company_code", "")).upper() == code.upper():
            return int(item["id"])
    return None


def _resolve_department_id(db, company_id: int, row: dict[str, Any]) -> int | None:
    did = row.get("department_id")
    if did:
        try:
            return int(did)
        except (TypeError, ValueError):
            pass
    code = _row_val(row, "department_code", "Department Code")
    if not code:
        return None
    listing = list_departments_master(db, company_id=company_id, search=code, per_page=50)
    for item in listing.get("items", []):
        if str(item.get("department_code", "")).upper() == code.upper():
            return int(item["id"])
    return None


def validate_designation_import_rows(db, rows: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    parsed: list[dict] = []
    for row in rows:
        company_id = _resolve_company_id(db, row)
        desig_code = _row_val(row, "designation_code", "Designation Code", "code")
        desig_name = _row_val(row, "designation_name", "Designation Name", "name")
        if not company_id and not desig_code and not desig_name:
            continue
        row_num = row.get("_row_num", "?")
        if not company_id:
            errors.append(error_row(row_num, "Company Code", "Company code is required.", "Enter a valid company code."))
            continue
        if not get_company(db, company_id):
            errors.append(error_row(row_num, "Company Code", "Company not found.", "Use an existing company code."))
            continue
        row["company_id"] = company_id
        if not desig_name:
            errors.append(error_row(row_num, "Designation Name", "Designation name is required.", "Enter designation name."))
        department_id = _resolve_department_id(db, company_id, row)
        if _row_val(row, "department_code", "Department Code") and not department_id:
            errors.append(error_row(row_num, "Department Code", "Department not found.", "Use a valid department for the company."))
        elif department_id:
            row["department_id"] = department_id
        status = _row_val(row, "status", "Status") or "Active"
        if status not in DESIGNATION_STATUSES:
            errors.append(error_row(row_num, "Status", f"Invalid status: {status}.", "Use Active or Inactive."))
        wf_role = _row_val(row, "workflow_role", "Workflow Role", "workflow_role_default") or "None"
        if wf_role not in WORKFLOW_ROLE_DEFAULTS:
            errors.append(error_row(row_num, "Workflow Role", f"Invalid role: {wf_role}.", "Use Maker, Checker, Approver, or None."))
        if desig_code and desig_name:
            try:
                validate_designation_uniqueness(
                    db,
                    company_id=company_id,
                    designation_code=desig_code,
                    designation_name=desig_name,
                )
            except ValueError as exc:
                errors.append(error_row(row_num, "Designation Code", str(exc), "Use unique code and name."))
        parsed.append(row)
    return parsed, errors


def validate_designation_import(db, rows: list[dict[str, Any]]) -> dict[str, Any]:
    parsed, errors = validate_designation_import_rows(db, rows)
    result = validation_result(parsed, errors)
    result["parsed_rows"] = parsed
    return result


def save_designation_import(
    db,
    rows: list[dict[str, Any]],
    *,
    username: str,
    filename: str = "",
    customer_id: int | None = None,
) -> dict[str, Any]:
    val = validate_designation_import(db, rows)
    if not val.get("ok"):
        raise ValueError("Import validation failed.")
    imported = 0
    for row in val.get("parsed_rows") or []:
        form = {
            "company_id": row["company_id"],
            "department_id": row.get("department_id"),
            "designation_code": _row_val(row, "designation_code", "Designation Code", "code"),
            "designation_name": _row_val(row, "designation_name", "Designation Name", "name"),
            "designation_short_name": _row_val(row, "designation_short_name", "Short Name", "short_name"),
            "grade_level": _row_val(row, "grade_level", "Grade Level"),
            "workflow_role_default": _row_val(row, "workflow_role", "Workflow Role") or "None",
            "description": _row_val(row, "description", "Description"),
            "status": _row_val(row, "status", "Status") or "Active",
        }
        new_id = save_designation_master(db, form, username, customer_id=customer_id)
        log_designation_audit(
            db,
            new_id,
            "import",
            username,
            remarks=f"Imported from {filename or 'spreadsheet'}",
        )
        imported += 1
    return {"ok": True, "imported": imported, "filename": filename}
