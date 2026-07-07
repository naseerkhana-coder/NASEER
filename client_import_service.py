"""Client Master bulk import — validate and save spreadsheet rows."""

from __future__ import annotations

from typing import Any

from bulk_import_service import error_row, validation_result
from client_master_service import (
    CLIENT_STATUSES,
    CLIENT_TYPES,
    log_client_audit,
    save_client_master,
    validate_client_uniqueness,
    validate_client_form_data,
)


def _row_val(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        val = str(row.get(key) or "").strip()
        if val:
            return val
    return ""


def validate_client_import_rows(db, rows: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    parsed: list[dict] = []
    for row in rows:
        client_code = _row_val(row, "client_code", "code")
        client_name = _row_val(row, "client_name", "name")
        if not client_code and not client_name:
            continue
        row_num = row.get("_row_num", "?")
        if not client_name:
            errors.append(error_row(row_num, "Client Name", "Client name is required.", "Enter client name."))
            continue
        row["client_code"] = client_code
        row["client_name"] = client_name
        row["legal_name"] = _row_val(row, "legal_name") or client_name
        row["company_name"] = row["legal_name"]
        row["client_type"] = _row_val(row, "client_type") or "Corporate"
        if row["client_type"] not in CLIENT_TYPES:
            errors.append(
                error_row(row_num, "Client Type", f"Invalid type: {row['client_type']}.", "Use a valid client type.")
            )
        row["industry"] = _row_val(row, "industry")
        row["gst_number"] = _row_val(row, "gst_number", "gst").upper()
        row["pan_number"] = _row_val(row, "pan_number", "pan").upper()
        row["email"] = _row_val(row, "email")
        row["phone"] = _row_val(row, "phone")
        row["mobile"] = _row_val(row, "mobile")
        row["billing_address"] = _row_val(row, "billing_address", "address")
        row["city"] = _row_val(row, "city")
        row["state"] = _row_val(row, "state")
        row["pin_code"] = _row_val(row, "pin_code", "pin")
        row["payment_terms"] = _row_val(row, "payment_terms")
        credit = _row_val(row, "credit_limit")
        row["credit_limit"] = credit
        row["bank_name"] = _row_val(row, "bank_name")
        row["account_number"] = _row_val(row, "account_number")
        row["ifsc_swift"] = _row_val(row, "ifsc_swift", "ifsc").upper()
        row["status"] = _row_val(row, "status") or "Active"
        if row["status"] not in CLIENT_STATUSES:
            errors.append(error_row(row_num, "Status", f"Invalid status: {row['status']}.", "Use Active or Inactive."))
        row["contact_person"] = _row_val(row, "primary_contact_name", "contact_person")
        row["contact_email"] = _row_val(row, "primary_contact_email", "contact_email")
        row["contact_mobile"] = _row_val(row, "primary_contact_mobile", "contact_mobile")
        try:
            validate_client_form_data(row)
            if client_code:
                validate_client_uniqueness(db, client_code=client_code, gst_number=row["gst_number"])
            elif row["gst_number"]:
                gst_hit = db.execute(
                    "SELECT id FROM clients WHERE UPPER(gst_number)=? AND COALESCE(is_deleted,0)=0",
                    (row["gst_number"].upper(),),
                ).fetchone()
                if gst_hit:
                    raise ValueError(f"GST number '{row['gst_number']}' is already registered.")
        except ValueError as exc:
            errors.append(error_row(row_num, "Client", str(exc), "Fix validation errors."))
            continue
        parsed.append(row)
    return parsed, errors


def validate_client_import(db, rows: list[dict[str, Any]]) -> dict[str, Any]:
    parsed, errors = validate_client_import_rows(db, rows)
    result = validation_result(parsed, errors)
    result["parsed_rows"] = parsed
    return result


def validate_client_import_rows_public(db, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return validate_client_import(db, rows)


def save_client_import(
    db,
    rows: list[dict[str, Any]],
    *,
    username: str,
    filename: str = "",
    customer_id: int | None = None,
) -> dict[str, Any]:
    val = validate_client_import(db, rows)
    if not val.get("ok"):
        raise ValueError("Import validation failed.")
    imported = 0
    for row in val.get("parsed_rows") or []:
        form = {
            "client_code": _row_val(row, "client_code"),
            "client_name": _row_val(row, "client_name"),
            "legal_name": _row_val(row, "legal_name"),
            "company_name": _row_val(row, "company_name"),
            "client_type": _row_val(row, "client_type") or "Corporate",
            "industry": _row_val(row, "industry"),
            "gst_number": _row_val(row, "gst_number"),
            "pan_number": _row_val(row, "pan_number"),
            "email": _row_val(row, "email"),
            "phone": _row_val(row, "phone"),
            "mobile": _row_val(row, "mobile"),
            "billing_address": _row_val(row, "billing_address"),
            "city": _row_val(row, "city"),
            "state": _row_val(row, "state"),
            "pin_code": _row_val(row, "pin_code"),
            "payment_terms": _row_val(row, "payment_terms"),
            "credit_limit": _row_val(row, "credit_limit"),
            "bank_name": _row_val(row, "bank_name"),
            "account_number": _row_val(row, "account_number"),
            "ifsc_swift": _row_val(row, "ifsc_swift"),
            "status": _row_val(row, "status") or "Active",
            "contact_person": _row_val(row, "contact_person"),
            "contact_name[]": [_row_val(row, "contact_person") or "Primary Contact"],
            "contact_email[]": [_row_val(row, "contact_email") or _row_val(row, "email")],
            "contact_mobile[]": [_row_val(row, "contact_mobile") or _row_val(row, "mobile")],
            "contact_primary_index": "0",
            "address_line1[]": [_row_val(row, "billing_address")] if _row_val(row, "billing_address") else [],
            "address_type[]": ["Billing"] if _row_val(row, "billing_address") else [],
            "address_primary_index": "0",
        }
        new_id = save_client_master(db, form, username, customer_id=customer_id)
        log_client_audit(
            db,
            new_id,
            "import",
            username,
            remarks=f"Imported from {filename or 'spreadsheet'}",
        )
        imported += 1
    return {"ok": True, "imported": imported, "filename": filename}
