"""BOQ Excel import — validate and save BOQ line items for a project."""

from __future__ import annotations

from datetime import datetime
from typing import Any

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

BOQ_IMPORT_COLUMNS = [
    "Item No",
    "BOQ Code",
    "Description",
    "Specification",
    "Unit",
    "Quantity",
    "Rate",
    "Amount",
    "Remarks",
]

BOQ_COLUMN_MAP = {
    "item_no": "item_no",
    "item_number": "item_no",
    "boq_code": "boq_code",
    "description": "description",
    "specification": "specification",
    "detailed_specification": "specification",
    "unit": "unit",
    "quantity": "quantity",
    "qty": "quantity",
    "rate": "rate",
    "amount": "amount",
    "remarks": "remarks",
}


def boq_import_template():
    return build_xlsx_template(
        BOQ_IMPORT_COLUMNS,
        ["1", "EWC-001", "Earth work in excavation", "Ordinary soil up to 1.5m", "Cum", "100", "450", "45000", ""],
    )


def _normalize_boq_row(row: RowDict) -> RowDict:
    out = dict(row)
    for src, dest in BOQ_COLUMN_MAP.items():
        if src in row and dest not in out:
            out[dest] = row.get(src, "")
    return out


def _parse_number(value: str, *, allow_zero: bool = True) -> float | None:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    try:
        num = float(text)
    except ValueError:
        return None
    if num < 0:
        return None
    if not allow_zero and num == 0:
        return None
    return round(num, 4)


def validate_boq_import_rows(
    db,
    rows: list[RowDict],
    *,
    boq_units: list[str],
    project_id: int | None = None,
) -> tuple[list[RowDict], list[ImportErrorDict]]:
    ensure_standard_boq_library_schema(db)
    normalized = [_normalize_boq_row(r) for r in rows]
    errors: list[ImportErrorDict] = []

    if project_id:
        proj = db.execute("SELECT id FROM projects WHERE id=?", (project_id,)).fetchone()
        if not proj:
            errors.append(error_row("—", "Project", "Selected project not found.", "Choose a valid project."))

    errors.extend(validate_duplicates(normalized, "boq_code", "BOQ Code"))

    parsed: list[RowDict] = []
    for row in normalized:
        row_num = row.get("_row_num", "?")
        desc = str(row.get("description", "")).strip()
        qty_raw = str(row.get("quantity", "")).strip()
        rate_raw = str(row.get("rate", "")).strip()
        if not desc and not qty_raw and not rate_raw:
            continue

        errors.extend(
            validate_required(row, [("description", "Description"), ("unit", "Unit")])
        )
        errors.extend(validate_unit(str(row.get("unit", "")), "Unit", row_num, boq_units))

        qty = _parse_number(qty_raw, allow_zero=False)
        rate = _parse_number(rate_raw, allow_zero=True)
        if qty_raw and qty is None:
            errors.append(error_row(row_num, "Quantity", "Invalid quantity.", "Enter a positive number."))
        if rate_raw and rate is None:
            errors.append(error_row(row_num, "Rate", "Invalid rate.", "Enter a valid number ≥ 0."))

        amount_raw = str(row.get("amount", "")).strip()
        amount = _parse_number(amount_raw, allow_zero=True) if amount_raw else None
        if qty is not None and rate is not None:
            calc = round(qty * rate, 2)
            if amount is not None and abs(amount - calc) > 0.05:
                errors.append(
                    error_row(
                        row_num,
                        "Amount",
                        f"Amount {amount} does not match Qty × Rate ({calc}).",
                        "Correct Amount or leave blank to auto-calculate.",
                    )
                )
            amount = calc
        elif amount is None and qty is not None and rate is not None:
            amount = round(qty * rate, 2)

        boq_code = str(row.get("boq_code", "")).strip().upper()
        if boq_code:
            lib = db.execute(
                "SELECT id, standard_rate FROM standard_boq_library WHERE boq_code=? AND COALESCE(is_active,1)=1",
                (boq_code,),
            ).fetchone()
            if not lib:
                errors.append(
                    error_row(
                        row_num,
                        "BOQ Code",
                        f"BOQ Code {boq_code} not in Standard BOQ Library.",
                        "Add the item to BOQ Library first or leave BOQ Code blank.",
                    )
                )

        parsed.append(
            {
                **row,
                "quantity": qty or 0,
                "rate": rate or 0,
                "amount": amount or 0,
                "item_description": desc,
                "detailed_specification": str(row.get("specification", "")).strip(),
                "remarks": str(row.get("remarks", "")).strip(),
                "boq_code": boq_code,
                "item_no": str(row.get("item_no", "")).strip(),
            }
        )

    if not parsed and not errors:
        errors.append(error_row("—", "File", "No importable rows found.", "Add at least one line with Description."))

    return parsed, errors


def validate_boq_import(db, rows: list[RowDict], *, boq_units: list[str], project_id: int | None) -> dict[str, Any]:
    parsed, errors = validate_boq_import_rows(db, rows, boq_units=boq_units, project_id=project_id)
    result = validation_result(parsed, errors)
    result["parsed_rows"] = parsed
    return result


def save_boq_import(
    db,
    parsed_rows: list[RowDict],
    *,
    project_id: int,
    username: str,
    filename: str,
    generate_boq_number_fn,
    insert_boq_lines_fn,
    create_approval_request_fn,
    record_pending_checker: str,
) -> dict[str, Any]:
    """Create one BOQ master and insert all validated lines."""
    ensure_standard_boq_library_schema(db)
    if not parsed_rows:
        raise ValueError("No rows to import.")

    proj = db.execute("SELECT id FROM projects WHERE id=?", (project_id,)).fetchone()
    if not proj:
        raise ValueError("Project not found.")

    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []
    for idx, row in enumerate(parsed_rows, start=1):
        lines.append(
            {
                "line_no": idx,
                "item_description": row["item_description"],
                "detailed_specification": row.get("detailed_specification", ""),
                "quantity": float(row.get("quantity") or 0),
                "unit": row.get("unit") or "Nos",
                "rate": float(row.get("rate") or 0),
                "amount": float(row.get("amount") or 0),
                "remarks": row.get("remarks", ""),
                "boq_code": row.get("boq_code", ""),
                "library_item_id": None,
            }
        )
        boq_code = row.get("boq_code")
        if boq_code:
            lib = db.execute(
                "SELECT id FROM standard_boq_library WHERE boq_code=?",
                (boq_code,),
            ).fetchone()
            if lib:
                lines[-1]["library_item_id"] = lib["id"]

    total_amount = round(sum(l["amount"] for l in lines), 2)
    boq_number = generate_boq_number_fn(db, project_id)
    db.execute(
        "INSERT INTO boq_master(boq_number, project_id, total_amount, line_count, "
        "created_by, approval_status, created_at) VALUES(?,?,?,?,?,?,?)",
        (boq_number, project_id, total_amount, len(lines), username, record_pending_checker, now_ts),
    )
    boq_id = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])

    for line in lines:
        item_code = line.get("item_no") or f"BOQ{line['line_no']}"
        db.execute(
            "INSERT INTO boq_items(boq_id, line_no, item_code, project_id, item_description, "
            "detailed_specification, quantity, unit, rate, amount, remarks, boq_code, "
            "library_item_id, created_by, created_at, approval_status, is_deleted) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                boq_id,
                line["line_no"],
                item_code,
                project_id,
                line["item_description"],
                line.get("detailed_specification") or "",
                line["quantity"],
                line["unit"],
                line["rate"],
                line["amount"],
                line.get("remarks") or "",
                line.get("boq_code") or "",
                line.get("library_item_id"),
                username,
                now_ts,
                record_pending_checker,
                0,
            ),
        )

    create_approval_request_fn(db, "boq", boq_id, "boq_master", username, None)

    log_import(
        db,
        module_key="boq",
        imported_by=username,
        filename=filename,
        total_rows=len(parsed_rows),
        success_rows=len(parsed_rows),
        failed_rows=0,
        rollback_payload={"module_key": "boq", "boq_id": boq_id},
    )

    return {
        "ok": True,
        "boq_id": boq_id,
        "boq_number": boq_number,
        "line_count": len(lines),
        "total_amount": total_amount,
    }
