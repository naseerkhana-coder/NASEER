"""Branch Master bulk import — validate and save spreadsheet rows."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from bulk_import_service import (
    error_row,
    validate_duplicates,
    validate_gst,
    validate_pan,
    validate_required,
    validation_result,
)
from branch_master_service import (
    BRANCH_STATUSES,
    BRANCH_TYPES,
    COMPANY_COUNTRIES,
    COMPANY_CURRENCIES,
    COMPANY_TIMEZONES,
    _table_exists,
    log_branch_audit,
    save_branch_master,
    validate_branch_contact,
    validate_branch_uniqueness,
    validate_pin_code,
)
from company_master_service import get_company, list_companies


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


def validate_branch_import_rows(db, rows: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    parsed: list[dict] = []
    for row in rows:
        company_id = _resolve_company_id(db, row)
        branch_code = _row_val(row, "branch_code")
        branch_name = _row_val(row, "branch_name", "name")
        if not company_id and not branch_code and not branch_name:
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
        errors.extend(
            validate_required(
                row,
                [
                    ("branch_code", "Branch Code"),
                    ("branch_name", "Branch Name"),
                ],
            )
        )
        branch_type = _row_val(row, "branch_type")
        if branch_type and branch_type not in BRANCH_TYPES:
            errors.append(error_row(row_num, "Branch Type", f"Invalid branch type: {branch_type}.", "Use Head Office, Site, etc."))
        status = _row_val(row, "status") or "Active"
        if status not in BRANCH_STATUSES:
            errors.append(error_row(row_num, "Status", f"Invalid status: {status}.", "Use Active or Inactive."))
        country = _row_val(row, "country") or "India"
        if country not in COMPANY_COUNTRIES:
            errors.append(error_row(row_num, "Country", f"Invalid country: {country}.", "Use a supported country."))
        gst = _row_val(row, "gst_number", "gst")
        pan = _row_val(row, "pan_number", "pan")
        errors.extend(validate_gst(gst, "GST Number", row_num))
        errors.extend(validate_pan(pan, "PAN Number", row_num))
        try:
            validate_branch_contact(email=_row_val(row, "email"), phone=_row_val(row, "phone"))
            validate_pin_code(_row_val(row, "pin_code", "postal_code", "pin"), country=country)
        except ValueError as exc:
            errors.append(error_row(row_num, "Validation", str(exc), "Correct the value."))
        currency = _row_val(row, "currency") or "INR"
        if currency not in COMPANY_CURRENCIES:
            errors.append(error_row(row_num, "Currency", f"Invalid currency: {currency}.", "Use INR, USD, etc."))
        tz = _row_val(row, "timezone") or "Asia/Kolkata"
        if tz not in COMPANY_TIMEZONES:
            errors.append(error_row(row_num, "Timezone", f"Invalid timezone: {tz}.", "Use Asia/Kolkata, etc."))
        try:
            validate_branch_uniqueness(db, company_id=company_id, branch_code=branch_code, gst_number=gst)
        except ValueError as exc:
            errors.append(error_row(row_num, "Branch Code", str(exc), "Use a unique branch code for the company."))
        parsed.append(row)
    return parsed, errors


def validate_branch_import(db, rows: list[dict[str, Any]]) -> dict[str, Any]:
    parsed, errors = validate_branch_import_rows(db, rows)
    result = validation_result(parsed, errors)
    result["parsed_rows"] = parsed
    return result


def save_branch_import(
    db,
    rows: list[dict[str, Any]],
    *,
    username: str,
    filename: str = "",
    customer_id: int | None = None,
) -> dict[str, Any]:
    if not _table_exists(db, "company_branches"):
        raise ValueError("Branch master schema is not initialized.")
    val = validate_branch_import(db, rows)
    if not val.get("ok"):
        raise ValueError("Import validation failed.")
    imported = 0
    for row in val.get("parsed_rows") or []:
        form = {
            "company_id": row["company_id"],
            "branch_code": _row_val(row, "branch_code"),
            "branch_name": _row_val(row, "branch_name", "name"),
            "branch_type": _row_val(row, "branch_type"),
            "gst_number": _row_val(row, "gst_number", "gst"),
            "pan_number": _row_val(row, "pan_number", "pan"),
            "country": _row_val(row, "country") or "India",
            "state_region": _row_val(row, "state", "state_region"),
            "district": _row_val(row, "district"),
            "city": _row_val(row, "city"),
            "postal_code": _row_val(row, "pin_code", "postal_code", "pin"),
            "latitude": _row_val(row, "latitude"),
            "longitude": _row_val(row, "longitude"),
            "phone": _row_val(row, "phone"),
            "email": _row_val(row, "email"),
            "branch_manager": _row_val(row, "branch_manager"),
            "opening_date": _row_val(row, "opening_date"),
            "closing_date": _row_val(row, "closing_date"),
            "working_hours": _row_val(row, "working_hours"),
            "currency": _row_val(row, "currency") or "INR",
            "timezone": _row_val(row, "timezone") or "Asia/Kolkata",
            "status": _row_val(row, "status") or "Active",
            "address_line1": _row_val(row, "address_line1", "address"),
            "address_line2": _row_val(row, "address_line2"),
            "approval_status": "Draft",
        }
        new_id = save_branch_master(db, form, username, customer_id=customer_id)
        log_branch_audit(
            db,
            new_id,
            "import",
            username,
            remarks=f"Imported from {filename or 'spreadsheet'}",
        )
        imported += 1
    return {"ok": True, "imported": imported, "filename": filename}
