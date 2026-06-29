"""Accounts opening data import — customers and vendors."""

from __future__ import annotations

from typing import Any

import sqlite3

from bulk_import_service import (
    ImportErrorDict,
    RowDict,
    build_xlsx_template,
    error_row,
    validate_duplicates,
    validate_gst,
    validate_pan,
    validate_required,
    validation_result,
)
from import_audit_service import log_import

CUSTOMER_COLUMNS = [
    "Client Code",
    "Company Name",
    "Contact Person",
    "Client Name",
    "Mobile",
    "Email",
    "Address",
    "GST Number",
    "PAN Number",
    "Status",
]

VENDOR_COLUMNS = [
    "Vendor Code",
    "Name",
    "GSTIN",
    "PAN",
    "Contact Person",
    "Phone",
    "Email",
    "Address",
    "City",
    "State",
    "Pincode",
]


def customer_import_template():
    return build_xlsx_template(
        CUSTOMER_COLUMNS,
        ["CLT101", "Acme Builders Pvt Ltd", "Raj Kumar", "Acme Builders", "9876543210",
         "accounts@acme.in", "Mumbai", "27AABCU9603R1ZM", "AABCU9603R", "Active"],
    )


def vendor_import_template():
    return build_xlsx_template(
        VENDOR_COLUMNS,
        ["VND101", "Steel Traders", "27AABCT1234M1Z5", "AABCT1234M", "Suresh", "9123456780",
         "sales@steel.in", "Industrial Area", "Pune", "Maharashtra", "411001"],
    )


def validate_customer_import_rows(
    db,
    rows: list[RowDict],
) -> tuple[list[RowDict], list[ImportErrorDict]]:
    errors: list[ImportErrorDict] = []
    errors.extend(validate_duplicates(rows, "client_code", "Client Code"))
    parsed: list[RowDict] = []
    for row in rows:
        company = str(row.get("company_name") or "").strip()
        code = str(row.get("client_code") or "").strip().upper()
        if not company and not code:
            continue
        row_num = row.get("_row_num", "?")
        errors.extend(validate_required(row, [("company_name", "Company Name")]))
        errors.extend(validate_gst(str(row.get("gst_number") or ""), "GST Number", row_num))
        errors.extend(validate_pan(str(row.get("pan_number") or ""), "PAN Number", row_num))
        if code:
            existing = db.execute(
                "SELECT id FROM clients WHERE UPPER(client_code)=?",
                (code,),
            ).fetchone()
            if existing:
                errors.append(error_row(
                    row_num, "Client Code", f"Client code {code} already exists.",
                    "Use a new code or update via Clients screen.",
                ))
        parsed.append(row)
    if not parsed and not errors:
        errors.append(error_row("—", "File", "No importable rows.", "Add customer rows."))
    return parsed, errors


def validate_customer_import(db, rows: list[RowDict]) -> dict[str, Any]:
    parsed, errors = validate_customer_import_rows(db, rows)
    result = validation_result(parsed, errors)
    result["parsed_rows"] = parsed
    return result


def save_customer_import(
    db,
    parsed_rows: list[RowDict],
    *,
    username: str,
    filename: str,
    generate_client_code_fn,
) -> dict[str, Any]:
    if not parsed_rows:
        raise ValueError("No rows to import.")
    saved = 0
    failed = 0
    row_errors: list[str] = []
    inserted_ids: list[int] = []
    for row in parsed_rows:
        company = str(row.get("company_name") or "").strip()
        if not company:
            continue
        code = str(row.get("client_code") or "").strip().upper() or generate_client_code_fn(db)
        contact = str(row.get("contact_person") or "").strip()
        client_name = str(row.get("client_name") or "").strip() or company or contact
        try:
            db.execute(
                "INSERT INTO clients(client_code, client_name, company_name, contact_person, mobile, email, "
                "address, gst_number, pan_number, status) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    code,
                    client_name,
                    company,
                    contact,
                    str(row.get("mobile") or "").strip(),
                    str(row.get("email") or "").strip(),
                    str(row.get("address") or "").strip(),
                    str(row.get("gst_number") or "").strip().upper(),
                    str(row.get("pan_number") or "").strip().upper(),
                    str(row.get("status") or "Active").strip() or "Active",
                ),
            )
            inserted_ids.append(int(db.execute("SELECT last_insert_rowid()").fetchone()[0]))
            saved += 1
        except sqlite3.IntegrityError:
            failed += 1
            row_errors.append(f"Row {row.get('_row_num')}: duplicate client code {code}")
        except sqlite3.Error as exc:
            failed += 1
            row_errors.append(f"Row {row.get('_row_num')}: {exc}")
    log_import(
        db,
        module_key="customers",
        imported_by=username,
        filename=filename,
        total_rows=len(parsed_rows),
        success_rows=saved,
        failed_rows=failed,
        notes="; ".join(row_errors[:10]),
        rollback_payload={
            "module_key": "customers",
            "records": [{"table": "clients", "id": cid} for cid in inserted_ids],
        } if inserted_ids else None,
    )
    return {"ok": failed == 0, "imported": saved, "failed": failed, "errors": row_errors}


def validate_vendor_import_rows(
    db,
    rows: list[RowDict],
) -> tuple[list[RowDict], list[ImportErrorDict]]:
    errors: list[ImportErrorDict] = []
    errors.extend(validate_duplicates(rows, "vendor_code", "Vendor Code"))
    parsed: list[RowDict] = []
    for row in rows:
        name = str(row.get("name") or row.get("vendor_name") or "").strip()
        if name and not str(row.get("name") or "").strip():
            row = {**row, "name": name}
        code = str(row.get("vendor_code") or row.get("code") or "").strip().upper()
        if not name and not code:
            continue
        row_num = row.get("_row_num", "?")
        errors.extend(validate_required(row, [("name", "Name")]))
        errors.extend(validate_gst(str(row.get("gstin") or row.get("gst") or ""), "GSTIN", row_num))
        errors.extend(validate_pan(str(row.get("pan") or ""), "PAN", row_num))
        if code:
            existing = db.execute("SELECT id FROM vendors WHERE UPPER(code)=?", (code,)).fetchone()
            if existing:
                errors.append(error_row(
                    row_num, "Vendor Code", f"Code {code} already exists.", "Use a unique vendor code.",
                ))
        parsed.append(row)
    if not parsed and not errors:
        errors.append(error_row("—", "File", "No importable rows.", "Add vendor rows."))
    return parsed, errors


def validate_vendor_import(db, rows: list[RowDict]) -> dict[str, Any]:
    parsed, errors = validate_vendor_import_rows(db, rows)
    result = validation_result(parsed, errors)
    result["parsed_rows"] = parsed
    return result


def save_vendor_import(db, parsed_rows: list[RowDict], *, username: str, filename: str) -> dict[str, Any]:
    from store_service import ensure_store_schema, save_vendor

    ensure_store_schema(db)
    if not parsed_rows:
        raise ValueError("No rows to import.")
    saved = 0
    failed = 0
    row_errors: list[str] = []
    inserted_ids: list[int] = []
    for row in parsed_rows:
        name = str(row.get("name") or row.get("vendor_name") or "").strip()
        if not name:
            continue
        form = {
            "code": str(row.get("vendor_code") or row.get("code") or "").strip(),
            "name": name,
            "gstin": str(row.get("gstin") or row.get("gst") or "").strip(),
            "pan": str(row.get("pan") or "").strip(),
            "contact_person": str(row.get("contact_person") or "").strip(),
            "phone": str(row.get("phone") or "").strip(),
            "email": str(row.get("email") or "").strip(),
            "address": str(row.get("address") or "").strip(),
            "city": str(row.get("city") or "").strip(),
            "state": str(row.get("state") or "").strip(),
            "pincode": str(row.get("pincode") or "").strip(),
            "is_active": "1",
        }
        try:
            vendor_id = save_vendor(db, form, None)
            inserted_ids.append(int(vendor_id))
            saved += 1
        except (ValueError, sqlite3.IntegrityError) as exc:
            failed += 1
            row_errors.append(f"Row {row.get('_row_num')}: {exc}")
    log_import(
        db,
        module_key="vendors",
        imported_by=username,
        filename=filename,
        total_rows=len(parsed_rows),
        success_rows=saved,
        failed_rows=failed,
        notes="; ".join(row_errors[:10]),
        rollback_payload={
            "module_key": "vendors",
            "records": [{"table": "vendors", "id": vid} for vid in inserted_ids],
        } if inserted_ids else None,
    )
    return {"ok": failed == 0, "imported": saved, "failed": failed, "errors": row_errors}
