"""Roles & Permissions bulk import — validate and save spreadsheet rows."""

from __future__ import annotations

from typing import Any

from bulk_import_service import error_row, validation_result
from company_master_service import get_company, list_companies
from roles_permissions_service import (
    ROLE_STATUSES,
    log_role_audit,
    save_role_master,
    validate_role_uniqueness,
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


def validate_roles_import_rows(db, rows: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    parsed: list[dict] = []
    for row in rows:
        company_id = _resolve_company_id(db, row)
        role_code = _row_val(row, "role_code", "Role Code", "code")
        role_name = _row_val(row, "role_name", "Role Name", "name")
        if not company_id and not role_code and not role_name:
            continue
        row_num = row.get("_row_num", "?")
        if not company_id:
            errors.append(error_row(row_num, "Company Code", "Company code is required.", "Enter a valid company code."))
            continue
        if not get_company(db, company_id):
            errors.append(error_row(row_num, "Company Code", "Company not found.", "Use an existing company code."))
            continue
        row["company_id"] = company_id
        if not role_name:
            errors.append(error_row(row_num, "Role Name", "Role name is required.", "Enter role name."))
            continue
        status = _row_val(row, "status", "Status") or "Active"
        if status not in ROLE_STATUSES:
            errors.append(error_row(row_num, "Status", f"Invalid status: {status}.", "Use Active or Inactive."))
        if role_code or role_name:
            try:
                validate_role_uniqueness(
                    db,
                    company_id=company_id,
                    role_code=role_code or role_name,
                    role_name=role_name,
                )
            except ValueError as exc:
                errors.append(error_row(row_num, "Role Code", str(exc), "Use unique code and name."))
        parsed.append(row)
    return parsed, errors


def validate_roles_import(db, rows: list[dict[str, Any]]) -> dict[str, Any]:
    parsed, errors = validate_roles_import_rows(db, rows)
    result = validation_result(parsed, errors)
    result["parsed_rows"] = parsed
    return result


def save_roles_import(
    db,
    rows: list[dict[str, Any]],
    *,
    username: str,
    filename: str = "",
    customer_id: int | None = None,
) -> dict[str, Any]:
    val = validate_roles_import(db, rows)
    if not val.get("ok"):
        raise ValueError("Import validation failed.")
    imported = 0
    for row in val["parsed_rows"]:
        form = {
            "company_id": row["company_id"],
            "role_code": _row_val(row, "role_code", "Role Code", "code"),
            "role_name": _row_val(row, "role_name", "Role Name", "name"),
            "description": _row_val(row, "description", "Description"),
            "status": _row_val(row, "status", "Status") or "Active",
        }
        rid = save_role_master(db, form, username, customer_id=customer_id)
        log_role_audit(db, rid, "import", username, remarks=filename or "bulk import")
        imported += 1
    return {"ok": True, "imported": imported, "filename": filename}
