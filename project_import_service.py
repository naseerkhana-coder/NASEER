"""Project Master bulk import — validate and save spreadsheet rows."""

from __future__ import annotations

from typing import Any

from bulk_import_service import error_row, validation_result
from project_master_service import (
    PROJECT_LIFECYCLE_STATUSES,
    PROJECT_STATUSES,
    PROJECT_TYPES,
    PRIORITY_LEVELS,
    generate_project_code,
    log_project_audit,
    save_project_master,
    validate_project_uniqueness,
    validate_project_form_data,
)


def _row_val(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        val = str(row.get(key) or "").strip()
        if val:
            return val
    return ""


def _resolve_fk_code(db, table: str, code_col: str, code: str) -> int | None:
    if not code:
        return None
    row = db.execute(
        f"SELECT id FROM {table} WHERE UPPER({code_col})=? AND COALESCE(is_deleted,0)=0 LIMIT 1",
        (code.upper(),),
    ).fetchone()
    return int(row[0]) if row else None


def validate_project_import_rows(db, rows: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    parsed: list[dict] = []
    for row in rows:
        project_code = _row_val(row, "project_code", "code")
        project_name = _row_val(row, "project_name", "name")
        if not project_code and not project_name:
            continue
        row_num = row.get("_row_num", "?")
        if not project_name:
            errors.append(error_row(row_num, "Project Name", "Project name is required.", "Enter project name."))
            continue
        row["project_code"] = project_code or generate_project_code(db, project_name)
        row["project_name"] = project_name
        row["short_name"] = _row_val(row, "short_name") or project_name[:40]
        row["project_type"] = _row_val(row, "project_type") or "Infrastructure"
        if row["project_type"] not in PROJECT_TYPES:
            errors.append(
                error_row(row_num, "Project Type", f"Invalid type: {row['project_type']}.", "Use a valid project type.")
            )
        client_id = _resolve_fk_code(db, "clients", "client_code", _row_val(row, "client_code"))
        company_id = _resolve_fk_code(db, "companies", "company_code", _row_val(row, "company_code"))
        branch_id = _resolve_fk_code(db, "company_branches", "branch_code", _row_val(row, "branch_code"))
        pm_id = _resolve_fk_code(db, "staff", "employee_code", _row_val(row, "project_manager_code", "manager_code"))
        eng_id = _resolve_fk_code(db, "staff", "employee_code", _row_val(row, "engineer_code"))
        if not client_id:
            errors.append(error_row(row_num, "Client Code", "Client code not found.", "Use a valid client code."))
            continue
        if not company_id:
            errors.append(error_row(row_num, "Company Code", "Company code not found.", "Use a valid company code."))
            continue
        if not branch_id:
            errors.append(error_row(row_num, "Branch Code", "Branch code not found.", "Use a valid branch code."))
            continue
        if not pm_id:
            errors.append(
                error_row(row_num, "Project Manager Code", "Manager code not found.", "Use a valid employee code.")
            )
            continue
        row["client_id"] = client_id
        row["company_id"] = company_id
        row["branch_id"] = branch_id
        row["project_manager_id"] = pm_id
        row["project_engineer_id"] = eng_id
        row["contract_number"] = _row_val(row, "contract_number")
        row["work_order_number"] = _row_val(row, "work_order_number")
        row["agreement_number"] = _row_val(row, "agreement_number")
        row["project_value"] = _row_val(row, "project_value", "value")
        row["revised_project_value"] = _row_val(row, "revised_project_value", "revised_value")
        row["currency"] = _row_val(row, "currency") or "INR"
        row["start_date"] = _row_val(row, "start_date")
        row["planned_completion_date"] = _row_val(row, "planned_completion", "planned_completion_date")
        row["project_status"] = _row_val(row, "project_status") or "Execution"
        if row["project_status"] not in PROJECT_LIFECYCLE_STATUSES:
            errors.append(
                error_row(row_num, "Project Status", f"Invalid status: {row['project_status']}.", "Use a valid status.")
            )
        row["priority"] = _row_val(row, "priority") or "Medium"
        if row["priority"] not in PRIORITY_LEVELS:
            errors.append(error_row(row_num, "Priority", f"Invalid priority: {row['priority']}.", "Use Low/Medium/High/Critical."))
        row["city"] = _row_val(row, "city")
        row["state"] = _row_val(row, "state")
        row["latitude"] = _row_val(row, "latitude")
        row["longitude"] = _row_val(row, "longitude")
        row["status"] = _row_val(row, "status") or "Active"
        if row["status"] not in PROJECT_STATUSES:
            errors.append(error_row(row_num, "Status", f"Invalid status: {row['status']}.", "Use Active or Inactive."))
        try:
            validate_project_form_data(db, row)
            validate_project_uniqueness(db, project_code=row["project_code"])
        except ValueError as exc:
            errors.append(error_row(row_num, "Project", str(exc), "Fix validation errors."))
            continue
        parsed.append(row)
    return parsed, errors


def validate_project_import(db, rows: list[dict[str, Any]]) -> dict[str, Any]:
    parsed, errors = validate_project_import_rows(db, rows)
    result = validation_result(parsed, errors)
    result["parsed_rows"] = parsed
    return result


def validate_project_import_rows_public(db, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return validate_project_import(db, rows)


def save_project_import(
    db,
    rows: list[dict[str, Any]],
    *,
    username: str,
    filename: str = "",
    customer_id: int | None = None,
) -> dict[str, Any]:
    val = validate_project_import(db, rows)
    if not val.get("ok"):
        raise ValueError("Import validation failed.")
    imported = 0
    for row in val.get("parsed_rows") or []:
        form = {
            "project_code": row.get("project_code"),
            "project_name": row.get("project_name"),
            "short_name": row.get("short_name"),
            "project_type": row.get("project_type"),
            "client_id": row.get("client_id"),
            "company_id": row.get("company_id"),
            "branch_id": row.get("branch_id"),
            "project_manager_id": row.get("project_manager_id"),
            "project_engineer_id": row.get("project_engineer_id"),
            "contract_number": row.get("contract_number"),
            "work_order_number": row.get("work_order_number"),
            "agreement_number": row.get("agreement_number"),
            "project_value": row.get("project_value"),
            "revised_project_value": row.get("revised_project_value"),
            "currency": row.get("currency"),
            "start_date": row.get("start_date"),
            "planned_completion_date": row.get("planned_completion_date"),
            "project_status": row.get("project_status"),
            "priority": row.get("priority"),
            "city": row.get("city"),
            "state": row.get("state"),
            "latitude": row.get("latitude"),
            "longitude": row.get("longitude"),
            "status": row.get("status"),
        }
        new_id = save_project_master(db, form, username, customer_id=customer_id)
        log_project_audit(
            db,
            new_id,
            "import",
            username,
            remarks=f"Imported from {filename or 'spreadsheet'}",
        )
        imported += 1
    return {"ok": True, "imported": imported}
