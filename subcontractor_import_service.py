"""Subcontractor Master bulk import — validate and save spreadsheet rows."""

from __future__ import annotations

from typing import Any

from bulk_import_service import error_row, validate_duplicates, validate_gst, validate_pan, validation_result
from company_master_service import validate_email, validate_phone
from subcontractor_master_service import (
    SUBCONTRACTOR_RATE_TYPES,
    SUBCONTRACTOR_STATUSES,
    log_subcontractor_audit,
    save_subcontractor_master,
    validate_labour_license,
    validate_subcontractor_uniqueness,
)
from store_service import TRADE_CATEGORY_OPTIONS


def _row_val(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        val = str(row.get(key) or "").strip()
        if val:
            return val
    return ""


def _parse_trades(raw: str) -> list[str]:
    if not raw:
        return []
    parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
    return [p for p in parts if p in TRADE_CATEGORY_OPTIONS] or parts


def validate_subcontractor_import_rows(db, rows: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    errors.extend(validate_duplicates(rows, "subcontractor_code", "Subcontractor Code"))
    parsed: list[dict] = []
    for row in rows:
        code = _row_val(row, "subcontractor_code", "code")
        name = _row_val(row, "subcontractor_name", "name")
        if not code and not name:
            continue
        row_num = row.get("_row_num", "?")
        if not name:
            errors.append(error_row(row_num, "Subcontractor Name", "Name is required.", "Enter subcontractor name."))
            continue
        trades_raw = _row_val(row, "trade_categories", "trades")
        trades = _parse_trades(trades_raw)
        if not trades:
            errors.append(
                error_row(row_num, "Trade Categories", "At least one trade is required.", "Enter trade categories.")
            )
            continue
        gst = _row_val(row, "gst_number", "gstin").upper()
        pan = _row_val(row, "pan_number", "pan").upper()
        errors.extend(validate_gst(gst, "GST Number", row_num))
        errors.extend(validate_pan(pan, "PAN", row_num))
        email = _row_val(row, "email")
        phone = _row_val(row, "phone", "contact_number", "mobile")
        if email:
            try:
                validate_email(email)
            except ValueError as exc:
                errors.append(error_row(row_num, "Email", str(exc), "Enter a valid email."))
        if phone:
            try:
                validate_phone(phone)
            except ValueError as exc:
                errors.append(error_row(row_num, "Phone", str(exc), "Enter a valid phone."))
        ll = _row_val(row, "labour_license_no")
        if ll:
            try:
                validate_labour_license(ll)
            except ValueError as exc:
                errors.append(error_row(row_num, "Labour License", str(exc), "Fix labour license."))
        status = _row_val(row, "status") or "Active"
        if status not in SUBCONTRACTOR_STATUSES:
            errors.append(error_row(row_num, "Status", f"Invalid status '{status}'.", "Use Active or Inactive."))
        rate_type = _row_val(row, "rate_type") or "Labour Supply"
        if rate_type not in SUBCONTRACTOR_RATE_TYPES:
            errors.append(error_row(row_num, "Rate Type", f"Invalid rate type '{rate_type}'.", "Use a standard type."))
        row["subcontractor_code"] = code
        row["subcontractor_name"] = name
        row["trade_categories_list"] = trades
        row["gst_number"] = gst
        row["pan_number"] = pan
        row["status"] = status
        row["rate_type"] = rate_type
        parsed.append(row)
    return parsed, errors


def validate_subcontractor_import(db, rows: list[dict[str, Any]]) -> dict[str, Any]:
    parsed, errors = validate_subcontractor_import_rows(db, rows)
    codes_in_file: set[str] = set()
    gst_in_file: set[str] = set()
    for row in parsed:
        row_num = row.get("_row_num", "?")
        code = _row_val(row, "subcontractor_code").upper()
        gst = _row_val(row, "gst_number").upper()
        if code:
            if code in codes_in_file:
                errors.append(error_row(row_num, "Subcontractor Code", f"Duplicate code '{code}' in file.", "Use unique codes."))
            codes_in_file.add(code)
        if gst:
            if gst in gst_in_file:
                errors.append(error_row(row_num, "GST", f"Duplicate GST '{gst}' in file.", "Use unique GST."))
            gst_in_file.add(gst)
        try:
            validate_subcontractor_uniqueness(
                db,
                subcontractor_code=code or f"NEW-{row_num}",
                gst_number=gst,
                subcontractor_id=None,
            )
        except ValueError as exc:
            errors.append(error_row(row_num, "Uniqueness", str(exc), "Fix code or GST."))
    result = validation_result(parsed, errors)
    result["parsed_rows"] = parsed
    return result


def save_subcontractor_import(
    db,
    rows: list[dict[str, Any]],
    *,
    username: str,
    filename: str = "",
    customer_id: int | None = None,
) -> dict[str, Any]:
    imported = 0
    for row in rows:
        trades = row.get("trade_categories_list") or _parse_trades(_row_val(row, "trade_categories"))
        form = {
            "subcontractor_code": _row_val(row, "subcontractor_code"),
            "subcontractor_name": _row_val(row, "subcontractor_name"),
            "legal_name": _row_val(row, "legal_name"),
            "company_name": _row_val(row, "company_name", "legal_name"),
            "classification": _row_val(row, "classification"),
            "trade_categories[]": trades,
            "rate_type": _row_val(row, "rate_type") or "Labour Supply",
            "gst_number": _row_val(row, "gst_number"),
            "pan_number": _row_val(row, "pan_number"),
            "contact_person": _row_val(row, "contact_person"),
            "phone": _row_val(row, "phone", "contact_number"),
            "mobile": _row_val(row, "mobile"),
            "email": _row_val(row, "email"),
            "address": _row_val(row, "address"),
            "city": _row_val(row, "city"),
            "state": _row_val(row, "state"),
            "pincode": _row_val(row, "pincode"),
            "payment_terms": _row_val(row, "payment_terms"),
            "retention_percent": _row_val(row, "retention_percent") or "0",
            "security_deposit": _row_val(row, "security_deposit") or "0",
            "insurance_policy_no": _row_val(row, "insurance_policy_no"),
            "insurance_expiry": _row_val(row, "insurance_expiry"),
            "labour_license_no": _row_val(row, "labour_license_no"),
            "labour_license_expiry": _row_val(row, "labour_license_expiry"),
            "rating": _row_val(row, "rating"),
            "status": _row_val(row, "status") or "Active",
            "approval_status": _row_val(row, "approval_status") or "Approved",
            "is_approved": _row_val(row, "is_approved") or "1",
            "is_blacklisted": _row_val(row, "is_blacklisted") or "0",
            "remarks": _row_val(row, "remarks"),
        }
        sid = save_subcontractor_master(db, form, username, None, customer_id=customer_id)
        log_subcontractor_audit(
            db, sid, "import", username, remarks=f"Imported from {filename or 'spreadsheet'}"
        )
        imported += 1
    return {"ok": True, "imported": imported}
