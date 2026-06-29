"""Bulk Excel import for master libraries — WBS, Labour, Machinery, Productivity, Rate, Materials."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

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
from master_library_service import ensure_master_library_schemas

DEFAULT_UNITS = ["Nos", "Sqm", "Cum", "MT", "Rmt", "Kg", "Bag", "LS", "Ltr", "Set", "Day", "Hour"]


def _lookup_existing(
    db,
    table: str,
    code_col: str,
    code: str,
    customer_id: int | None,
) -> dict | None:
    sql = f"SELECT id FROM {table} WHERE UPPER({code_col})=?"
    params: list[Any] = [code.upper()]
    if customer_id is not None:
        sql += " AND customer_id=?"
        params.append(customer_id)
    row = db.execute(sql, params).fetchone()
    return dict(row) if row else None


def _save_generic_import(
    db,
    *,
    module_key: str,
    table: str,
    code_col: str,
    parsed_rows: list[RowDict],
    username: str,
    filename: str,
    customer_id: int | None,
    upsert: bool,
    build_insert: Callable[[RowDict, str, str], tuple[list[str], list[Any]]],
    build_update: Callable[[RowDict, int, str, str], tuple[str, list[Any]]],
) -> dict[str, Any]:
    ensure_master_library_schemas(db)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    saved = updated = failed = 0
    row_errors: list[str] = []
    records: list[dict[str, Any]] = []

    for row in parsed_rows:
        code = str(row.get(code_col) or "").strip()
        if not code:
            continue
        existing = _lookup_existing(db, table, code_col, code, customer_id)
        try:
            if existing and upsert:
                sql, params = build_update(row, int(existing["id"]), username, now)
                db.execute(sql, params)
                records.append({"table": table, "id": int(existing["id"]), "action": "update"})
                updated += 1
            elif existing:
                failed += 1
                row_errors.append(f"Row {row.get('_row_num')}: {code_col} {code} already exists.")
            else:
                cols, vals = build_insert(row, username, now)
                if customer_id is not None:
                    cols.append("customer_id")
                    vals.append(customer_id)
                placeholders = ",".join("?" * len(vals))
                db.execute(
                    f"INSERT INTO {table}({','.join(cols)}) VALUES({placeholders})",
                    vals,
                )
                new_id = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])
                records.append({"table": table, "id": new_id, "action": "insert"})
                saved += 1
        except sqlite3.Error as exc:
            failed += 1
            row_errors.append(f"Row {row.get('_row_num')}: {exc}")

    log_import(
        db,
        module_key=module_key,
        imported_by=username,
        filename=filename,
        total_rows=len(parsed_rows),
        success_rows=saved + updated,
        failed_rows=failed,
        customer_id=customer_id,
        notes="; ".join(row_errors[:10]),
        rollback_payload={"module_key": module_key, "records": records} if records else None,
    )
    return {"ok": failed == 0, "imported": saved, "updated": updated, "failed": failed, "errors": row_errors}


# --- WBS ---

WBS_COLUMNS = ["WBS Code", "Parent Code", "Description", "Level", "Unit", "Planned Quantity"]


def wbs_library_template():
    return build_xlsx_template(WBS_COLUMNS, ["1.0", "", "Civil Works", "1", "LS", "1"])


def validate_wbs_library_rows(
    db, rows: list[RowDict], *, customer_id: int | None = None, upsert: bool = False,
) -> tuple[list[RowDict], list[ImportErrorDict]]:
    ensure_master_library_schemas(db)
    errors: list[ImportErrorDict] = []
    errors.extend(validate_duplicates(rows, "wbs_code", "WBS Code"))
    parsed: list[RowDict] = []
    for row in rows:
        code = str(row.get("wbs_code") or "").strip()
        desc = str(row.get("description") or "").strip()
        if not code and not desc:
            continue
        row_num = row.get("_row_num", "?")
        errors.extend(validate_required(row, [("wbs_code", "WBS Code"), ("description", "Description")]))
        if code and not upsert and _lookup_existing(db, "standard_wbs_library", "wbs_code", code, customer_id):
            errors.append(error_row(row_num, "WBS Code", f"WBS Code {code} already exists.", "Enable update existing."))
        parsed.append({**row, "wbs_code": code, "description": desc})
    if not parsed and not errors:
        errors.append(error_row("—", "File", "No importable rows.", "Add WBS rows."))
    return parsed, errors


def save_wbs_library_import(db, parsed_rows, *, username, filename, customer_id=None, upsert=False):
    def build_insert(row, user, now):
        try:
            qty = float(row.get("planned_quantity") or 0)
        except (TypeError, ValueError):
            qty = 0.0
        try:
            level = int(float(row.get("level") or 1))
        except (TypeError, ValueError):
            level = 1
        return (
            ["wbs_code", "parent_code", "description", "level", "unit", "planned_quantity", "is_active", "created_by", "created_at"],
            [
                str(row.get("wbs_code") or "").strip(),
                str(row.get("parent_code") or "").strip(),
                str(row.get("description") or "").strip(),
                level,
                str(row.get("unit") or "LS").strip() or "LS",
                qty, 1, user, now,
            ],
        )

    def build_update(row, item_id, user, now):
        try:
            qty = float(row.get("planned_quantity") or 0)
        except (TypeError, ValueError):
            qty = 0.0
        try:
            level = int(float(row.get("level") or 1))
        except (TypeError, ValueError):
            level = 1
        return (
            "UPDATE standard_wbs_library SET parent_code=?, description=?, level=?, unit=?, "
            "planned_quantity=?, modified_by=?, modified_at=? WHERE id=?",
            [
                str(row.get("parent_code") or "").strip(),
                str(row.get("description") or "").strip(),
                level,
                str(row.get("unit") or "LS").strip() or "LS",
                qty, user, now, item_id,
            ],
        )

    return _save_generic_import(
        db, module_key="wbs_library", table="standard_wbs_library", code_col="wbs_code",
        parsed_rows=parsed_rows, username=username, filename=filename,
        customer_id=customer_id, upsert=upsert, build_insert=build_insert, build_update=build_update,
    )


# --- Labour ---

LABOUR_COLUMNS = ["Trade Code", "Trade Name", "Unit", "Standard Rate", "Category"]


def labour_library_template():
    return build_xlsx_template(LABOUR_COLUMNS, ["LAB-MASON", "Mason", "Day", "850", "Civil"])


def validate_labour_library_rows(
    db, rows, *, customer_id=None, upsert=False,
) -> tuple[list[RowDict], list[ImportErrorDict]]:
    ensure_master_library_schemas(db)
    errors: list[ImportErrorDict] = []
    errors.extend(validate_duplicates(rows, "trade_code", "Trade Code"))
    parsed: list[RowDict] = []
    for row in rows:
        code = str(row.get("trade_code") or "").strip().upper()
        name = str(row.get("trade_name") or row.get("name") or "").strip()
        if not code and not name:
            continue
        row_num = row.get("_row_num", "?")
        row = {**row, "trade_name": name}
        errors.extend(validate_required(row, [("trade_code", "Trade Code"), ("trade_name", "Trade Name")]))
        errors.extend(validate_unit(str(row.get("unit") or "Day"), "Unit", row_num, DEFAULT_UNITS))
        if code and not upsert and _lookup_existing(db, "labour_rate_library", "trade_code", code, customer_id):
            errors.append(error_row(row_num, "Trade Code", f"Trade Code {code} exists.", "Enable update existing."))
        parsed.append({**row, "trade_code": code, "trade_name": name})
    if not parsed and not errors:
        errors.append(error_row("—", "File", "No importable rows.", "Add labour rows."))
    return parsed, errors


def save_labour_library_import(db, parsed_rows, *, username, filename, customer_id=None, upsert=False):
    def build_insert(row, user, now):
        try:
            rate = float(row.get("standard_rate") or row.get("rate") or 0)
        except (TypeError, ValueError):
            rate = 0.0
        return (
            ["trade_code", "trade_name", "unit", "standard_rate", "category", "is_active", "created_by", "created_at"],
            [
                str(row.get("trade_code") or "").strip().upper(),
                str(row.get("trade_name") or "").strip(),
                str(row.get("unit") or "Day").strip() or "Day",
                rate,
                str(row.get("category") or "").strip(),
                1, user, now,
            ],
        )

    def build_update(row, item_id, user, now):
        try:
            rate = float(row.get("standard_rate") or row.get("rate") or 0)
        except (TypeError, ValueError):
            rate = 0.0
        return (
            "UPDATE labour_rate_library SET trade_name=?, unit=?, standard_rate=?, category=?, "
            "modified_by=?, modified_at=? WHERE id=?",
            [
                str(row.get("trade_name") or "").strip(),
                str(row.get("unit") or "Day").strip() or "Day",
                rate,
                str(row.get("category") or "").strip(),
                user, now, item_id,
            ],
        )

    return _save_generic_import(
        db, module_key="labour_library", table="labour_rate_library", code_col="trade_code",
        parsed_rows=parsed_rows, username=username, filename=filename,
        customer_id=customer_id, upsert=upsert, build_insert=build_insert, build_update=build_update,
    )


# --- Machinery ---

MACHINERY_COLUMNS = ["Equipment Code", "Equipment Name", "Unit", "Hourly Rate", "Category"]


def machinery_library_template():
    return build_xlsx_template(MACHINERY_COLUMNS, ["MCH-EXC", "Excavator", "Hour", "2500", "Earthwork"])


def validate_machinery_library_rows(
    db, rows, *, customer_id=None, upsert=False,
) -> tuple[list[RowDict], list[ImportErrorDict]]:
    ensure_master_library_schemas(db)
    errors: list[ImportErrorDict] = []
    errors.extend(validate_duplicates(rows, "equipment_code", "Equipment Code"))
    parsed: list[RowDict] = []
    for row in rows:
        code = str(row.get("equipment_code") or row.get("code") or "").strip().upper()
        name = str(row.get("equipment_name") or row.get("name") or "").strip()
        if not code and not name:
            continue
        row_num = row.get("_row_num", "?")
        row = {**row, "equipment_name": name}
        errors.extend(validate_required(row, [("equipment_code", "Equipment Code"), ("equipment_name", "Equipment Name")]))
        if code and not upsert and _lookup_existing(db, "machinery_rate_library", "equipment_code", code, customer_id):
            errors.append(error_row(row_num, "Equipment Code", f"Code {code} exists.", "Enable update existing."))
        parsed.append({**row, "equipment_code": code, "equipment_name": name})
    if not parsed and not errors:
        errors.append(error_row("—", "File", "No importable rows.", "Add machinery rows."))
    return parsed, errors


def save_machinery_library_import(db, parsed_rows, *, username, filename, customer_id=None, upsert=False):
    def build_insert(row, user, now):
        try:
            rate = float(row.get("hourly_rate") or row.get("rate") or 0)
        except (TypeError, ValueError):
            rate = 0.0
        return (
            ["equipment_code", "equipment_name", "unit", "hourly_rate", "category", "is_active", "created_by", "created_at"],
            [
                str(row.get("equipment_code") or "").strip().upper(),
                str(row.get("equipment_name") or "").strip(),
                str(row.get("unit") or "Hour").strip() or "Hour",
                rate,
                str(row.get("category") or "").strip(),
                1, user, now,
            ],
        )

    def build_update(row, item_id, user, now):
        try:
            rate = float(row.get("hourly_rate") or row.get("rate") or 0)
        except (TypeError, ValueError):
            rate = 0.0
        return (
            "UPDATE machinery_rate_library SET equipment_name=?, unit=?, hourly_rate=?, category=?, "
            "modified_by=?, modified_at=? WHERE id=?",
            [
                str(row.get("equipment_name") or "").strip(),
                str(row.get("unit") or "Hour").strip() or "Hour",
                rate,
                str(row.get("category") or "").strip(),
                user, now, item_id,
            ],
        )

    return _save_generic_import(
        db, module_key="machinery_library", table="machinery_rate_library", code_col="equipment_code",
        parsed_rows=parsed_rows, username=username, filename=filename,
        customer_id=customer_id, upsert=upsert, build_insert=build_insert, build_update=build_update,
    )


# --- Productivity ---

PRODUCTIVITY_COLUMNS = ["Trade", "Unit", "Output Per Hour", "Project Code", "Remarks"]


def productivity_library_template():
    return build_xlsx_template(PRODUCTIVITY_COLUMNS, ["Mason", "Sqm", "2.5", "PRJ-001", "Plastering"])


def validate_productivity_library_rows(
    db, rows, *, customer_id=None, upsert=False,
) -> tuple[list[RowDict], list[ImportErrorDict]]:
    ensure_master_library_schemas(db)
    errors: list[ImportErrorDict] = []
    parsed: list[RowDict] = []
    for row in rows:
        trade = str(row.get("trade") or "").strip()
        if not trade:
            continue
        row_num = row.get("_row_num", "?")
        errors.extend(validate_required(row, [("trade", "Trade")]))
        out_raw = str(row.get("output_per_hour") or "").strip()
        if out_raw:
            try:
                float(out_raw)
            except ValueError:
                errors.append(error_row(row_num, "Output Per Hour", "Must be numeric.", "Enter a number."))
        parsed.append(row)
    if not parsed and not errors:
        errors.append(error_row("—", "File", "No importable rows.", "Add productivity rows."))
    return parsed, errors


def save_productivity_library_import(db, parsed_rows, *, username, filename, customer_id=None, upsert=False):
    ensure_master_library_schemas(db)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    saved = failed = 0
    row_errors: list[str] = []
    records: list[dict[str, Any]] = []

    for row in parsed_rows:
        trade = str(row.get("trade") or "").strip()
        if not trade:
            continue
        try:
            output = float(row.get("output_per_hour") or 0)
        except (TypeError, ValueError):
            output = 0.0
        cols = ["trade", "unit", "output_per_hour", "project_code", "remarks", "is_active", "created_by", "created_at"]
        vals: list[Any] = [
            trade,
            str(row.get("unit") or "").strip(),
            output,
            str(row.get("project_code") or "").strip(),
            str(row.get("remarks") or "").strip(),
            1, username, now,
        ]
        if customer_id is not None:
            cols.append("customer_id")
            vals.append(customer_id)
        try:
            db.execute(
                f"INSERT INTO productivity_library({','.join(cols)}) VALUES({','.join('?' * len(vals))})",
                vals,
            )
            new_id = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])
            records.append({"table": "productivity_library", "id": new_id, "action": "insert"})
            saved += 1
        except sqlite3.Error as exc:
            failed += 1
            row_errors.append(f"Row {row.get('_row_num')}: {exc}")

    log_import(
        db, module_key="productivity_library", imported_by=username, filename=filename,
        total_rows=len(parsed_rows), success_rows=saved, failed_rows=failed,
        customer_id=customer_id, notes="; ".join(row_errors[:10]),
        rollback_payload={"module_key": "productivity_library", "records": records} if records else None,
    )
    return {"ok": failed == 0, "imported": saved, "updated": 0, "failed": failed, "errors": row_errors}


# --- Rate ---

RATE_COLUMNS = ["BOQ Code", "Description", "Unit", "Labour Rate", "Machinery Rate", "Material Rate", "Total Rate"]


def rate_library_template():
    return build_xlsx_template(RATE_COLUMNS, ["EWC-001", "Earth work", "Cum", "120", "80", "250", "450"])


def validate_rate_library_rows(
    db, rows, *, customer_id=None, upsert=False,
) -> tuple[list[RowDict], list[ImportErrorDict]]:
    ensure_master_library_schemas(db)
    errors: list[ImportErrorDict] = []
    errors.extend(validate_duplicates(rows, "boq_code", "BOQ Code"))
    parsed: list[RowDict] = []
    for row in rows:
        code = str(row.get("boq_code") or "").strip().upper()
        if not code:
            continue
        row_num = row.get("_row_num", "?")
        errors.extend(validate_required(row, [("boq_code", "BOQ Code")]))
        if not upsert and _lookup_existing(db, "rate_master_library", "boq_code", code, customer_id):
            errors.append(error_row(row_num, "BOQ Code", f"BOQ Code {code} exists.", "Enable update existing."))
        parsed.append({**row, "boq_code": code})
    if not parsed and not errors:
        errors.append(error_row("—", "File", "No importable rows.", "Add rate rows."))
    return parsed, errors


def save_rate_library_import(db, parsed_rows, *, username, filename, customer_id=None, upsert=False):
    def _rates(row):
        def f(key):
            try:
                return float(row.get(key) or 0)
            except (TypeError, ValueError):
                return 0.0
        labour = f("labour_rate")
        machinery = f("machinery_rate")
        material = f("material_rate")
        total = f("total_rate")
        if total <= 0:
            total = labour + machinery + material
        return labour, machinery, material, total

    def build_insert(row, user, now):
        labour, machinery, material, total = _rates(row)
        return (
            ["boq_code", "description", "unit", "labour_rate", "machinery_rate", "material_rate", "total_rate",
             "is_active", "created_by", "created_at"],
            [
                str(row.get("boq_code") or "").strip().upper(),
                str(row.get("description") or "").strip(),
                str(row.get("unit") or "").strip(),
                labour, machinery, material, total,
                1, user, now,
            ],
        )

    def build_update(row, item_id, user, now):
        labour, machinery, material, total = _rates(row)
        return (
            "UPDATE rate_master_library SET description=?, unit=?, labour_rate=?, machinery_rate=?, "
            "material_rate=?, total_rate=?, modified_by=?, modified_at=? WHERE id=?",
            [
                str(row.get("description") or "").strip(),
                str(row.get("unit") or "").strip(),
                labour, machinery, material, total,
                user, now, item_id,
            ],
        )

    return _save_generic_import(
        db, module_key="rate_library", table="rate_master_library", code_col="boq_code",
        parsed_rows=parsed_rows, username=username, filename=filename,
        customer_id=customer_id, upsert=upsert, build_insert=build_insert, build_update=build_update,
    )


# --- Materials (enhanced with audit + rollback) ---

def save_materials_library_import(
    db,
    parsed_rows: list[RowDict],
    *,
    username: str,
    filename: str,
    customer_id: int | None = None,
    upsert: bool = True,
) -> dict[str, Any]:
    from store_service import ensure_store_schema, save_material

    ensure_store_schema(db)
    saved = updated = failed = 0
    row_errors: list[str] = []
    records: list[dict[str, Any]] = []

    for row in parsed_rows:
        code = str(row.get("code") or "").strip().upper()
        name = str(row.get("name") or "").strip()
        if not code or not name:
            continue
        existing = db.execute("SELECT id FROM materials WHERE UPPER(code)=?", (code,)).fetchone()
        row_data = {
            "code": code,
            "name": name,
            "category": str(row.get("category") or "").strip(),
            "unit": str(row.get("unit") or "Nos").strip() or "Nos",
            "hsn_code": str(row.get("hsn_code") or "").strip(),
            "gst_percent": row.get("gst_percent") or row.get("gst") or 0,
            "reorder_level": row.get("reorder_level") or 0,
            "min_stock": row.get("min_stock") or 0,
            "max_stock": row.get("max_stock") or 0,
            "preferred_vendor_id": "",
            "is_active": "1",
        }
        try:
            if existing and upsert:
                mat_id = save_material(db, row_data, int(existing["id"]))
                records.append({"table": "materials", "id": int(mat_id), "action": "update"})
                updated += 1
            elif existing:
                failed += 1
                row_errors.append(f"Row {row.get('_row_num')}: Material code {code} exists.")
            else:
                mat_id = save_material(db, row_data, None)
                records.append({"table": "materials", "id": int(mat_id), "action": "insert"})
                saved += 1
        except (ValueError, sqlite3.Error) as exc:
            failed += 1
            row_errors.append(f"Row {row.get('_row_num')}: {exc}")

    log_import(
        db, module_key="materials", imported_by=username, filename=filename,
        total_rows=len(parsed_rows), success_rows=saved + updated, failed_rows=failed,
        customer_id=customer_id, notes="; ".join(row_errors[:10]),
        rollback_payload={"module_key": "materials", "records": records} if records else None,
    )
    return {"ok": failed == 0, "imported": saved, "updated": updated, "failed": failed, "errors": row_errors}


def validate_and_wrap(module_key: str, validate_fn, db, rows, **kwargs) -> dict[str, Any]:
    parsed, errors = validate_fn(db, rows, **kwargs)
    result = validation_result(parsed, errors)
    result["parsed_rows"] = parsed
    result["module_key"] = module_key
    return result
