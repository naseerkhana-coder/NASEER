"""Bulk Excel import for Standard BOQ Library master."""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any

import sqlite3

from bulk_import_service import (
    ImportErrorDict,
    RowDict,
    build_xlsx_template,
    error_row,
    validate_duplicates,
    validate_required,
    validate_unit,
    validation_result,
)
from import_audit_service import log_import
from standard_boq_library_service import ensure_standard_boq_library_schema

BOQ_LIBRARY_COLUMNS = [
    "BOQ Code",
    "Item Number",
    "Description",
    "Specification",
    "Unit",
    "Category",
    "Sub Category",
    "Standard Rate",
]

DEFAULT_UNITS = ["Nos", "Sqm", "Cum", "MT", "Rmt", "Kg", "Bag", "LS", "Ltr", "Set", "Day", "Hour"]


def boq_library_import_template():
    return build_xlsx_template(
        BOQ_LIBRARY_COLUMNS,
        ["EWC-001", "1", "Earth work in excavation", "Ordinary soil up to 1.5m", "Cum", "Civil", "Earthwork", "450"],
    )


def _row_key(row: RowDict) -> str:
    code = str(row.get("boq_code") or "").strip().upper()
    item_no = str(row.get("item_number") or row.get("item_no") or "").strip().upper()
    return f"{code}::{item_no}" if item_no else code


def _validate_boq_library_duplicates(rows: list[RowDict]) -> list[ImportErrorDict]:
    seen: dict[str, int] = {}
    errors: list[ImportErrorDict] = []
    for row in rows:
        key = _row_key(row)
        if not key or key == "::":
            continue
        row_num = row.get("_row_num", "?")
        if key in seen:
            errors.append(error_row(
                row_num,
                "BOQ Code",
                f"Duplicate BOQ Code + Item Number: {key}.",
                f"Use unique combination (also on row {seen[key]}).",
            ))
        else:
            seen[key] = int(row_num) if str(row_num).isdigit() else 0
    return errors


def validate_boq_library_import_rows(
    db,
    rows: list[RowDict],
    *,
    customer_id: int | None = None,
    upsert: bool = False,
    boq_units: list[str] | None = None,
) -> tuple[list[RowDict], list[ImportErrorDict]]:
    ensure_standard_boq_library_schema(db)
    units = boq_units or DEFAULT_UNITS
    errors: list[ImportErrorDict] = []
    errors.extend(_validate_boq_library_duplicates(rows))
    parsed: list[RowDict] = []

    for row in rows:
        code = str(row.get("boq_code") or "").strip().upper()
        desc = str(row.get("description") or "").strip()
        item_no = str(row.get("item_number") or row.get("item_no") or "").strip()
        if not code and not desc:
            continue
        row_num = row.get("_row_num", "?")
        errors.extend(validate_required(row, [("boq_code", "BOQ Code"), ("description", "Description")]))
        errors.extend(validate_unit(str(row.get("unit") or "Nos"), "Unit", row_num, units))
        rate_raw = str(row.get("standard_rate") or row.get("rate") or "0").strip()
        if rate_raw:
            try:
                float(rate_raw)
            except ValueError:
                errors.append(error_row(row_num, "Standard Rate", "Standard Rate must be numeric.", "Enter a number."))

        if code and not upsert:
            sql = "SELECT id FROM standard_boq_library WHERE UPPER(boq_code)=?"
            params: list[Any] = [code]
            if item_no:
                sql += " AND UPPER(COALESCE(item_number,''))=?"
                params.append(item_no.upper())
            if customer_id is not None:
                sql += " AND customer_id=?"
                params.append(customer_id)
            existing = db.execute(sql, params).fetchone()
            if existing:
                errors.append(error_row(
                    row_num,
                    "BOQ Code",
                    f"BOQ Code {code} already exists in library.",
                    "Enable 'Update existing' or use a new code.",
                ))

        normalized = {
            **row,
            "boq_code": code,
            "item_number": item_no,
            "description": desc,
            "detailed_specification": str(row.get("specification") or row.get("detailed_specification") or "").strip(),
            "category": str(row.get("category") or "").strip(),
            "sub_category": str(row.get("sub_category") or "").strip(),
            "unit": str(row.get("unit") or "Nos").strip() or "Nos",
            "standard_rate": rate_raw or "0",
        }
        parsed.append(normalized)

    if not parsed and not errors:
        errors.append(error_row("—", "File", "No importable rows.", "Add library item rows."))
    return parsed, errors


def validate_boq_library_import(
    db,
    rows: list[RowDict],
    *,
    customer_id: int | None = None,
    upsert: bool = False,
    boq_units: list[str] | None = None,
) -> dict[str, Any]:
    parsed, errors = validate_boq_library_import_rows(
        db, rows, customer_id=customer_id, upsert=upsert, boq_units=boq_units,
    )
    result = validation_result(parsed, errors)
    result["parsed_rows"] = parsed
    return result


def save_boq_library_import(
    db,
    parsed_rows: list[RowDict],
    *,
    username: str,
    filename: str,
    customer_id: int | None = None,
    upsert: bool = False,
) -> dict[str, Any]:
    ensure_standard_boq_library_schema(db)
    if not parsed_rows:
        raise ValueError("No rows to import.")

    saved = 0
    updated = 0
    failed = 0
    row_errors: list[str] = []
    inserted_ids: list[int] = []
    updated_ids: list[int] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    has_customer_col = "customer_id" in {
        r[1] for r in db.execute("PRAGMA table_info(standard_boq_library)").fetchall()
    }

    for row in parsed_rows:
        code = str(row.get("boq_code") or "").strip().upper()
        desc = str(row.get("description") or "").strip()
        if not code or not desc:
            continue
        item_no = str(row.get("item_number") or "").strip()
        try:
            standard_rate = float(row.get("standard_rate") or 0)
        except (TypeError, ValueError):
            failed += 1
            row_errors.append(f"Row {row.get('_row_num')}: invalid standard rate")
            continue

        lookup_sql = "SELECT id FROM standard_boq_library WHERE UPPER(boq_code)=?"
        lookup_params: list[Any] = [code]
        if item_no:
            lookup_sql += " AND UPPER(COALESCE(item_number,''))=?"
            lookup_params.append(item_no.upper())
        if customer_id is not None and has_customer_col:
            lookup_sql += " AND customer_id=?"
            lookup_params.append(customer_id)
        existing = db.execute(lookup_sql, lookup_params).fetchone()

        try:
            if existing and upsert:
                db.execute(
                    "UPDATE standard_boq_library SET description=?, detailed_specification=?, unit=?, "
                    "category=?, sub_category=?, standard_rate=?, modified_by=?, modified_at=? WHERE id=?",
                    (
                        desc,
                        str(row.get("detailed_specification") or "").strip(),
                        str(row.get("unit") or "Nos").strip() or "Nos",
                        str(row.get("category") or "").strip(),
                        str(row.get("sub_category") or "").strip(),
                        standard_rate,
                        username,
                        now,
                        int(existing["id"]),
                    ),
                )
                updated_ids.append(int(existing["id"]))
                updated += 1
            elif existing:
                failed += 1
                row_errors.append(f"Row {row.get('_row_num')}: BOQ Code {code} already exists.")
            else:
                cols = [
                    "boq_code", "item_number", "description", "detailed_specification",
                    "unit", "category", "sub_category", "standard_rate", "is_active",
                    "created_by", "created_at",
                ]
                vals: list[Any] = [
                    code, item_no, desc,
                    str(row.get("detailed_specification") or "").strip(),
                    str(row.get("unit") or "Nos").strip() or "Nos",
                    str(row.get("category") or "").strip(),
                    str(row.get("sub_category") or "").strip(),
                    standard_rate, 1, username, now,
                ]
                if has_customer_col and customer_id is not None:
                    cols.append("customer_id")
                    vals.append(customer_id)
                placeholders = ",".join("?" * len(vals))
                db.execute(
                    f"INSERT INTO standard_boq_library({','.join(cols)}) VALUES({placeholders})",
                    vals,
                )
                new_id = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])
                inserted_ids.append(new_id)
                saved += 1
        except sqlite3.Error as exc:
            failed += 1
            row_errors.append(f"Row {row.get('_row_num')}: {exc}")

    records = (
        [{"table": "standard_boq_library", "id": i, "action": "insert"} for i in inserted_ids]
        + [{"table": "standard_boq_library", "id": i, "action": "update", "snapshot": {}} for i in updated_ids]
    )
    log_import(
        db,
        module_key="boq_library",
        imported_by=username,
        filename=filename,
        total_rows=len(parsed_rows),
        success_rows=saved + updated,
        failed_rows=failed,
        customer_id=customer_id,
        notes="; ".join(row_errors[:10]),
        rollback_payload={
            "module_key": "boq_library",
            "records": records,
        } if records else None,
    )
    return {
        "ok": failed == 0,
        "imported": saved,
        "updated": updated,
        "failed": failed,
        "errors": row_errors,
    }


def export_boq_library_excel(db, *, customer_id: int | None = None) -> io.BytesIO:
    import pandas as pd

    ensure_standard_boq_library_schema(db)
    sql = (
        "SELECT boq_code AS \"BOQ Code\", item_number AS \"Item Number\", description AS Description, "
        "detailed_specification AS Specification, unit AS Unit, category AS Category, "
        "sub_category AS \"Sub Category\", standard_rate AS \"Standard Rate\" "
        "FROM standard_boq_library WHERE COALESCE(is_active,1)=1"
    )
    params: list[Any] = []
    has_customer_col = "customer_id" in {
        r[1] for r in db.execute("PRAGMA table_info(standard_boq_library)").fetchall()
    }
    if customer_id is not None and has_customer_col:
        sql += " AND customer_id=?"
        params.append(customer_id)
    sql += " ORDER BY category, boq_code, item_number"
    rows = [dict(r) for r in db.execute(sql, params).fetchall()]
    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=BOQ_LIBRARY_COLUMNS)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, sheet_name="BOQ Library")
    buf.seek(0)
    return buf
