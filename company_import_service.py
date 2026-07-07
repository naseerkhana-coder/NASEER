"""Company Master bulk import — validate and save spreadsheet rows."""

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
from company_master_service import (
    COMPANY_COUNTRIES,
    COMPANY_CURRENCIES,
    COMPANY_LANGUAGES,
    COMPANY_STATUSES,
    COMPANY_TIMEZONES,
    COMPANY_TYPES,
    FINANCIAL_YEARS,
    _next_company_code,
    _table_exists,
    log_company_audit,
    validate_company_contact,
    validate_company_uniqueness,
)


def _row_val(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        val = str(row.get(key) or "").strip()
        if val:
            return val
    return ""


def validate_company_import_rows(db, rows: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    errors.extend(validate_duplicates(rows, "company_code", "Company Code"))
    errors.extend(validate_duplicates(rows, "gst_number", "GST Number"))
    parsed: list[dict] = []
    for row in rows:
        code = _row_val(row, "company_code")
        legal_name = _row_val(row, "legal_name")
        company_name = _row_val(row, "company_name", "name")
        if not code and not legal_name and not company_name:
            continue
        row_num = row.get("_row_num", "?")
        if not company_name and legal_name:
            row["company_name"] = legal_name
        errors.extend(
            validate_required(
                row,
                [
                    ("legal_name", "Legal Name"),
                    ("company_name", "Company Name"),
                ],
            )
        )
        country = _row_val(row, "country") or "India"
        if country not in COMPANY_COUNTRIES:
            errors.append(
                error_row(row_num, "Country", f"Invalid country: {country}.", "Use a supported country.")
            )
        company_type = _row_val(row, "company_type")
        if company_type and company_type not in COMPANY_TYPES:
            errors.append(
                error_row(
                    row_num,
                    "Company Type",
                    f"Invalid company type: {company_type}.",
                    "Use Private Limited, LLP, etc.",
                )
            )
        status = _row_val(row, "status") or "Active"
        if status not in COMPANY_STATUSES:
            errors.append(error_row(row_num, "Status", f"Invalid status: {status}.", "Use Active or Inactive."))
        gst = _row_val(row, "gst_number", "gst")
        pan = _row_val(row, "pan_number", "pan")
        errors.extend(validate_gst(gst, "GST Number", row_num))
        errors.extend(validate_pan(pan, "PAN Number", row_num))
        try:
            validate_company_contact(
                email=_row_val(row, "email"),
                phone=_row_val(row, "phone"),
                website=_row_val(row, "website"),
            )
        except ValueError as exc:
            errors.append(error_row(row_num, "Contact", str(exc), "Correct email, phone, or website."))
        currency = _row_val(row, "currency") or "INR"
        if currency not in COMPANY_CURRENCIES:
            errors.append(error_row(row_num, "Currency", f"Invalid currency: {currency}.", "Use INR, USD, etc."))
        fy = _row_val(row, "financial_year") or "April-March"
        if fy not in FINANCIAL_YEARS:
            errors.append(error_row(row_num, "Financial Year", f"Invalid financial year: {fy}.", "Use April-March or January-December."))
        tz = _row_val(row, "timezone") or "Asia/Kolkata"
        if tz not in COMPANY_TIMEZONES:
            errors.append(error_row(row_num, "Timezone", f"Invalid timezone: {tz}.", "Use Asia/Kolkata, etc."))
        lang = _row_val(row, "language") or "en"
        if lang not in COMPANY_LANGUAGES:
            errors.append(error_row(row_num, "Language", f"Invalid language: {lang}.", "Use en, hi, or ar."))
        if code:
            try:
                validate_company_uniqueness(db, company_code=code, gst_number=gst, legal_name=legal_name)
            except ValueError as exc:
                errors.append(error_row(row_num, "Company Code", str(exc), "Use a unique company code."))
        elif gst:
            try:
                validate_company_uniqueness(db, gst_number=gst, legal_name=legal_name)
            except ValueError as exc:
                errors.append(error_row(row_num, "GST Number", str(exc), "GST must be unique."))
        parsed.append(row)
    return parsed, errors


def validate_company_import(db, rows: list[dict[str, Any]]) -> dict[str, Any]:
    parsed, errors = validate_company_import_rows(db, rows)
    result = validation_result(parsed, errors)
    result["parsed_rows"] = parsed
    return result


def save_company_import(
    db,
    rows: list[dict[str, Any]],
    *,
    username: str,
    filename: str = "",
) -> dict[str, Any]:
    if not _table_exists(db, "companies"):
        raise ValueError("Company master schema is not initialized.")
    val = validate_company_import(db, rows)
    if not val.get("ok"):
        raise ValueError("Import validation failed.")
    imported = 0
    for row in val.get("parsed_rows") or []:
        code = _row_val(row, "company_code") or _next_company_code(db)
        legal_name = _row_val(row, "legal_name")
        company_name = _row_val(row, "company_name", "name") or legal_name
        country = _row_val(row, "country") or "India"
        country_fields: dict[str, str] = {}
        pan = _row_val(row, "pan_number", "pan")
        tan = _row_val(row, "tan_number", "tan")
        cin = _row_val(row, "cin_number", "cin")
        if pan:
            country_fields["pan"] = pan.upper()
        if tan:
            country_fields["tan"] = tan.upper()
        if cin:
            country_fields["cin"] = cin.upper()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            """
            INSERT INTO companies(
                company_code, legal_name, trade_name, company_name, company_type, country, status,
                address_line1, address_line2, city, state_region, district, postal_code,
                phone, email, website, gst_number, pan_number, tan_number, cin_number,
                currency, financial_year, timezone, language, country_fields_json,
                approval_status, created_by, created_at, modified_by, modified_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                code.upper(),
                legal_name,
                company_name,
                company_name,
                _row_val(row, "company_type"),
                country,
                _row_val(row, "status") or "Active",
                _row_val(row, "address_line1", "address"),
                _row_val(row, "address_line2"),
                _row_val(row, "city"),
                _row_val(row, "state", "state_region"),
                _row_val(row, "district"),
                _row_val(row, "pin_code", "postal_code", "pin"),
                _row_val(row, "phone"),
                _row_val(row, "email"),
                _row_val(row, "website"),
                _row_val(row, "gst_number", "gst").upper(),
                pan.upper(),
                tan.upper(),
                cin.upper(),
                _row_val(row, "currency") or "INR",
                _row_val(row, "financial_year") or "April-March",
                _row_val(row, "timezone") or "Asia/Kolkata",
                _row_val(row, "language") or "en",
                json.dumps(country_fields, ensure_ascii=False),
                "Draft",
                username,
                now,
                username,
                now,
            ),
        )
        new_id = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])
        log_company_audit(
            db,
            new_id,
            "import",
            username,
            remarks=f"Imported from {filename or 'spreadsheet'}",
        )
        imported += 1
    return {"ok": True, "imported": imported, "filename": filename}
