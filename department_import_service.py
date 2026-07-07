"""Department Master bulk import — validate and save spreadsheet rows."""

from __future__ import annotations

from typing import Any

from bulk_import_service import error_row, validation_result
from company_master_service import get_company, list_companies
from department_master_service import (
    DEPARTMENT_STATUSES,
    log_department_audit,
    save_department_master,
    validate_department_uniqueness,
)
from branch_master_service import list_branches_master


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
    code = _row_val(row, "company_code")
    if not code:
        return None
    listing = list_companies(db, search=code, per_page=50)
    for item in listing.get("items", []):
        if str(item.get("company_code", "")).upper() == code.upper():
            return int(item["id"])
    return None


def _resolve_branch_id(db, company_id: int, row: dict[str, Any]) -> int | None:
    bid = row.get("branch_id")
    if bid:
        try:
            return int(bid)
        except (TypeError, ValueError):
            pass
    code = _row_val(row, "branch_code")
    if not code:
        return None
    listing = list_branches_master(db, company_id=company_id, search=code, per_page=50)
    for item in listing.get("items", []):
        if str(item.get("branch_code", "")).upper() == code.upper():
            return int(item["id"])
    return None


def validate_department_import_rows(db, rows: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    parsed: list[dict] = []
    for row in rows:
        company_id = _resolve_company_id(db, row)
        dept_code = _row_val(row, "department_code", "code")
        dept_name = _row_val(row, "department_name", "name")
        if not company_id and not dept_code and not dept_name:
            continue
        row_num = row.get("_row_num", "?")
        if not company_id:
            errors.append(
                error_row(row_num, "Company Code", "Company code is required.", "Enter a valid company code.")
            )
            continue
        if not get_company(db, company_id):
            errors.append(error_row(row_num, "Company Code", "Company not found.", "Use an existing company code."))
            continue
        row["company_id"] = company_id
        row["department_code"] = dept_code
        row["department_name"] = dept_name
        if not dept_code:
            errors.append(error_row(row_num, "Department Code", "Department code is required.", "Enter a unique code."))
        if not dept_name:
            errors.append(error_row(row_num, "Department Name", "Department name is required.", "Enter department name."))
        branch_id = _resolve_branch_id(db, company_id, row)
        if _row_val(row, "branch_code") and not branch_id:
            errors.append(error_row(row_num, "Branch Code", "Branch not found.", "Use a valid branch for the company."))
        elif branch_id:
            row["branch_id"] = branch_id
        status = _row_val(row, "status") or "Active"
        if status not in DEPARTMENT_STATUSES:
            errors.append(error_row(row_num, "Status", f"Invalid status: {status}.", "Use Active or Inactive."))
        try:
            validate_department_uniqueness(
                db,
                company_id=company_id,
                department_code=dept_code,
                department_name=dept_name,
            )
        except ValueError as exc:
            errors.append(error_row(row_num, "Department Code", str(exc), "Use unique code and name per company."))
        parsed.append(row)
    return parsed, errors


def validate_department_import(db, rows: list[dict[str, Any]]) -> dict[str, Any]:
    parsed, errors = validate_department_import_rows(db, rows)
    result = validation_result(parsed, errors)
    result["parsed_rows"] = parsed
    return result


def save_department_import(
    db,
    rows: list[dict[str, Any]],
    *,
    username: str,
    filename: str = "",
    customer_id: int | None = None,
) -> dict[str, Any]:
    val = validate_department_import(db, rows)
    if not val.get("ok"):
        raise ValueError("Import validation failed.")
    imported = 0
    for row in val.get("parsed_rows") or []:
        form = {
            "company_id": row["company_id"],
            "branch_id": row.get("branch_id"),
            "department_code": _row_val(row, "department_code", "code"),
            "department_name": _row_val(row, "department_name", "name"),
            "department_short_name": _row_val(row, "department_short_name", "short_name"),
            "department_head": _row_val(row, "department_head"),
            "description": _row_val(row, "description"),
            "status": _row_val(row, "status") or "Active",
            "approval_status": "Draft",
        }
        new_id = save_department_master(db, form, username, customer_id=customer_id)
        log_department_audit(
            db,
            new_id,
            "import",
            username,
            remarks=f"Imported from {filename or 'spreadsheet'}",
        )
        imported += 1
    return {"ok": True, "imported": imported, "filename": filename}
