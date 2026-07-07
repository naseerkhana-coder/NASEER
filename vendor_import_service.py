"""Vendor Master bulk import — validate and save spreadsheet rows."""

from __future__ import annotations

from typing import Any

from bulk_import_service import error_row, validate_duplicates, validate_gst, validate_pan, validation_result
from company_master_service import validate_email, validate_phone
from vendor_master_service import (
    PAYMENT_TERMS_OPTIONS,
    VENDOR_STATUSES,
    log_vendor_audit,
    save_vendor_master,
    validate_vendor_uniqueness,
)


def _row_val(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        val = str(row.get(key) or "").strip()
        if val:
            return val
    return ""


def validate_vendor_import_rows(db, rows: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    errors.extend(validate_duplicates(rows, "vendor_code", "Vendor Code"))
    errors.extend(validate_duplicates(rows, "code", "Vendor Code"))
    parsed: list[dict] = []
    for row in rows:
        code = _row_val(row, "vendor_code", "code")
        name = _row_val(row, "vendor_name", "name")
        if not code and not name:
            continue
        row_num = row.get("_row_num", "?")
        if not name:
            errors.append(error_row(row_num, "Vendor Name", "Vendor name is required.", "Enter vendor name."))
            continue
        gstin = _row_val(row, "gstin", "gst_number").upper()
        pan = _row_val(row, "pan", "pan_number").upper()
        errors.extend(validate_gst(gstin, "GSTIN", row_num))
        errors.extend(validate_pan(pan, "PAN", row_num))
        email = _row_val(row, "email")
        phone = _row_val(row, "phone")
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
        status = _row_val(row, "status") or "Active"
        if status not in VENDOR_STATUSES:
            errors.append(
                error_row(row_num, "Status", f"Invalid status '{status}'.", "Use Active or Inactive.")
            )
        payment_terms = _row_val(row, "payment_terms")
        if payment_terms and payment_terms not in PAYMENT_TERMS_OPTIONS:
            errors.append(
                error_row(row_num, "Payment Terms", f"Invalid payment terms '{payment_terms}'.", "Use a standard term.")
            )
        row["vendor_code"] = code
        row["code"] = code
        row["vendor_name"] = name
        row["name"] = name
        row["gstin"] = gstin
        row["pan"] = pan
        row["status"] = status
        parsed.append(row)
    return parsed, errors


def validate_vendor_import(db, rows: list[dict[str, Any]]) -> dict[str, Any]:
    parsed, errors = validate_vendor_import_rows(db, rows)
    codes_in_file: set[str] = set()
    gst_in_file: set[str] = set()
    for row in parsed:
        row_num = row.get("_row_num", "?")
        code = _row_val(row, "vendor_code", "code").upper()
        gstin = _row_val(row, "gstin").upper()
        if code:
            if code in codes_in_file:
                errors.append(error_row(row_num, "Vendor Code", f"Duplicate code '{code}' in file.", "Use unique codes."))
            codes_in_file.add(code)
        if gstin:
            if gstin in gst_in_file:
                errors.append(error_row(row_num, "GSTIN", f"Duplicate GSTIN '{gstin}' in file.", "Use unique GSTIN."))
            gst_in_file.add(gstin)
        if gstin:
            try:
                validate_vendor_uniqueness(
                    db, vendor_code=code or f"NEW-{row_num}", gstin=gstin, vendor_id=None
                )
            except ValueError as exc:
                if code or "GSTIN" in str(exc):
                    errors.append(error_row(row_num, "Uniqueness", str(exc), "Fix code or GSTIN."))
        elif code:
            try:
                validate_vendor_uniqueness(db, vendor_code=code, gstin="", vendor_id=None)
            except ValueError as exc:
                errors.append(error_row(row_num, "Uniqueness", str(exc), "Fix vendor code."))
    result = validation_result(parsed, errors)
    result["parsed_rows"] = parsed
    return result


def save_vendor_import(
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
            "vendor_code": _row_val(row, "vendor_code", "code"),
            "vendor_name": _row_val(row, "vendor_name", "name"),
            "gstin": _row_val(row, "gstin"),
            "pan": _row_val(row, "pan"),
            "msme_number": _row_val(row, "msme_number"),
            "cin_number": _row_val(row, "cin_number"),
            "contact_person": _row_val(row, "contact_person"),
            "phone": _row_val(row, "phone"),
            "email": _row_val(row, "email"),
            "address": _row_val(row, "address"),
            "city": _row_val(row, "city"),
            "state": _row_val(row, "state"),
            "pincode": _row_val(row, "pincode"),
            "payment_terms": _row_val(row, "payment_terms"),
            "credit_limit": _row_val(row, "credit_limit") or "0",
            "rating": _row_val(row, "rating"),
            "website": _row_val(row, "website"),
            "status": _row_val(row, "status") or "Active",
            "approval_status": _row_val(row, "approval_status") or "Approved",
            "is_approved": _row_val(row, "is_approved") or "1",
            "is_blacklisted": _row_val(row, "is_blacklisted") or "0",
            "vendor_type": _row_val(row, "vendor_types", "vendor_type") or "Supplier",
            "remarks": _row_val(row, "remarks"),
        }
        vt = _row_val(row, "vendor_types", "vendor_type")
        if vt:
            form["vendor_types[]"] = [v.strip() for v in vt.split(",") if v.strip()]
        vid = save_vendor_master(db, form, username, None, customer_id=customer_id)
        log_vendor_audit(db, vid, "import", username, remarks=f"Imported from {filename or 'spreadsheet'}")
        imported += 1
    return {"ok": True, "imported": imported}
