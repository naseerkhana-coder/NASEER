"""Employee Master bulk import — validate and save spreadsheet rows."""

from __future__ import annotations

from typing import Any

from bulk_import_service import error_row, validation_result
from employee_master_service import (
    EMPLOYEE_STATUSES,
    EMPLOYEE_TYPES,
    SALARY_TYPES,
    generate_employee_code,
    log_employee_audit,
    save_employee_master,
    validate_employee_form_data,
    validate_employee_uniqueness,
)


def _row_val(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        val = str(row.get(key) or "").strip()
        if val:
            return val
    return ""


def _lookup_company_id(db, code: str) -> int | None:
    if not code:
        return None
    row = db.execute(
        "SELECT id FROM companies WHERE UPPER(company_code)=? AND COALESCE(is_deleted,0)=0",
        (code.upper(),),
    ).fetchone()
    return int(row[0]) if row else None


def _lookup_branch_id(db, company_id: int, code: str) -> int | None:
    if not code or not company_id:
        return None
    row = db.execute(
        """
        SELECT id FROM company_branches
        WHERE UPPER(branch_code)=? AND company_id=? AND COALESCE(is_deleted,0)=0
        """,
        (code.upper(), company_id),
    ).fetchone()
    return int(row[0]) if row else None


def _lookup_department_id(db, company_id: int, code: str, name: str = "") -> int | None:
    if code:
        row = db.execute(
            """
            SELECT id FROM departments
            WHERE UPPER(department_code)=? AND company_id=? AND COALESCE(is_deleted,0)=0
            """,
            (code.upper(), company_id),
        ).fetchone()
        if row:
            return int(row[0])
    if name:
        row = db.execute(
            """
            SELECT id FROM departments
            WHERE department_name=? AND company_id=? AND COALESCE(is_deleted,0)=0
            """,
            (name, company_id),
        ).fetchone()
        if row:
            return int(row[0])
    return None


def _lookup_designation_id(db, company_id: int, code: str, name: str = "") -> int | None:
    if code:
        row = db.execute(
            """
            SELECT id FROM designations
            WHERE UPPER(designation_code)=? AND company_id=? AND COALESCE(is_deleted,0)=0
            """,
            (code.upper(), company_id),
        ).fetchone()
        if row:
            return int(row[0])
    if name:
        row = db.execute(
            """
            SELECT id FROM designations
            WHERE designation_name=? AND company_id=? AND COALESCE(is_deleted,0)=0
            """,
            (name, company_id),
        ).fetchone()
        if row:
            return int(row[0])
    return None


def _lookup_manager_id(db, code: str) -> int | None:
    if not code:
        return None
    row = db.execute(
        "SELECT id FROM staff WHERE UPPER(employee_code)=? AND COALESCE(is_deleted,0)=0",
        (code.upper(),),
    ).fetchone()
    return int(row[0]) if row else None


def validate_employee_import_rows(db, rows: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    parsed: list[dict] = []
    for row in rows:
        employee_code = _row_val(row, "employee_code", "code")
        first_name = _row_val(row, "first_name", "name")
        last_name = _row_val(row, "last_name")
        full_name = _row_val(row, "staff_name", "employee_name", "name")
        if not employee_code and not first_name and not full_name:
            continue
        row_num = row.get("_row_num", "?")
        if not first_name and full_name:
            parts = full_name.split(None, 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""
        if not first_name:
            errors.append(error_row(row_num, "First Name", "Employee name is required.", "Enter first name."))
            continue
        company_code = _row_val(row, "company_code")
        company_id = _lookup_company_id(db, company_code)
        if company_code and not company_id:
            errors.append(error_row(row_num, "Company Code", f"Unknown company: {company_code}.", "Use valid code."))
            continue
        if not company_id:
            first_co = db.execute(
                "SELECT id FROM companies WHERE COALESCE(is_deleted,0)=0 ORDER BY id LIMIT 1"
            ).fetchone()
            company_id = int(first_co[0]) if first_co else None
        if not company_id:
            errors.append(error_row(row_num, "Company", "No company available.", "Create a company first."))
            continue
        dept_code = _row_val(row, "department_code")
        dept_name = _row_val(row, "department", "department_name")
        department_id = _lookup_department_id(db, company_id, dept_code, dept_name)
        if not department_id:
            errors.append(
                error_row(row_num, "Department", "Department is required.", "Provide department code or name.")
            )
            continue
        des_code = _row_val(row, "designation_code")
        des_name = _row_val(row, "designation", "designation_name")
        designation_id = _lookup_designation_id(db, company_id, des_code, des_name)
        if not designation_id:
            errors.append(
                error_row(row_num, "Designation", "Designation is required.", "Provide designation code or name.")
            )
            continue
        joining_date = _row_val(row, "joining_date", "join_date")
        if not joining_date:
            errors.append(error_row(row_num, "Joining Date", "Joining date is required.", "Enter joining date."))
            continue
        row["employee_code"] = employee_code
        row["first_name"] = first_name
        row["last_name"] = last_name
        row["staff_name"] = " ".join(p for p in (first_name, last_name) if p).strip()
        row["employee_type"] = _row_val(row, "employee_type") or "Permanent"
        row["company_id"] = company_id
        row["branch_id"] = _lookup_branch_id(db, company_id, _row_val(row, "branch_code"))
        row["department_id"] = department_id
        row["designation_id"] = designation_id
        row["reporting_manager_id"] = _lookup_manager_id(db, _row_val(row, "reporting_manager_code"))
        row["official_email"] = _row_val(row, "official_email", "email")
        row["mobile"] = _row_val(row, "mobile", "phone")
        row["joining_date"] = joining_date
        row["pan_number"] = _row_val(row, "pan_number", "pan").upper()
        row["aadhaar_number"] = _row_val(row, "aadhaar_number", "aadhaar")
        row["pf_number"] = _row_val(row, "pf_number")
        row["esi_number"] = _row_val(row, "esi_number")
        row["uan_number"] = _row_val(row, "uan_number")
        row["bank_name"] = _row_val(row, "bank_name")
        row["bank_account"] = _row_val(row, "account_number", "bank_account")
        row["ifsc_code"] = _row_val(row, "ifsc_code", "ifsc").upper()
        row["salary_type"] = _row_val(row, "salary_type") or "Monthly"
        row["salary_amount"] = _row_val(row, "salary_amount")
        row["status"] = _row_val(row, "status") or "Active"
        if row["employee_type"] not in EMPLOYEE_TYPES:
            errors.append(error_row(row_num, "Employee Type", f"Invalid type: {row['employee_type']}.", "Use valid type."))
        if row["status"] not in EMPLOYEE_STATUSES:
            errors.append(error_row(row_num, "Status", f"Invalid status: {row['status']}.", "Use Active or Inactive."))
        if row["salary_type"] not in SALARY_TYPES:
            errors.append(error_row(row_num, "Salary Type", f"Invalid salary type: {row['salary_type']}.", "Use Monthly/Daily/Hourly."))
        try:
            validate_employee_form_data(row)
            if employee_code:
                validate_employee_uniqueness(
                    db,
                    employee_code=employee_code,
                    official_email=row["official_email"],
                )
        except ValueError as exc:
            errors.append(error_row(row_num, "Employee", str(exc), "Fix validation errors."))
            continue
        parsed.append(row)
    return parsed, errors


def validate_employee_import(db, rows: list[dict[str, Any]]) -> dict[str, Any]:
    parsed, errors = validate_employee_import_rows(db, rows)
    result = validation_result(parsed, errors)
    result["parsed_rows"] = parsed
    return result


def validate_employee_import_rows_public(db, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return validate_employee_import(db, rows)


def save_employee_import(
    db,
    rows: list[dict[str, Any]],
    *,
    username: str,
    filename: str = "",
    customer_id: int | None = None,
) -> dict[str, Any]:
    val = validate_employee_import(db, rows)
    if not val.get("ok"):
        raise ValueError("Import validation failed.")
    imported = 0
    for row in val.get("parsed_rows") or []:
        form = {
            "employee_code": _row_val(row, "employee_code"),
            "first_name": _row_val(row, "first_name"),
            "last_name": _row_val(row, "last_name"),
            "staff_name": _row_val(row, "staff_name"),
            "employee_type": _row_val(row, "employee_type") or "Permanent",
            "company_id": str(row.get("company_id") or ""),
            "branch_id": str(row.get("branch_id") or ""),
            "department_id": str(row.get("department_id") or ""),
            "designation_id": str(row.get("designation_id") or ""),
            "reporting_manager_id": str(row.get("reporting_manager_id") or ""),
            "official_email": _row_val(row, "official_email"),
            "mobile": _row_val(row, "mobile"),
            "joining_date": _row_val(row, "joining_date"),
            "pan_number": _row_val(row, "pan_number"),
            "aadhaar_number": _row_val(row, "aadhaar_number"),
            "pf_number": _row_val(row, "pf_number"),
            "esi_number": _row_val(row, "esi_number"),
            "uan_number": _row_val(row, "uan_number"),
            "bank_name": _row_val(row, "bank_name"),
            "bank_account": _row_val(row, "bank_account"),
            "ifsc_code": _row_val(row, "ifsc_code"),
            "salary_type": _row_val(row, "salary_type") or "Monthly",
            "salary_amount": _row_val(row, "salary_amount"),
            "status": _row_val(row, "status") or "Active",
        }
        if not form["employee_code"]:
            form["employee_code"] = generate_employee_code(db)
        new_id = save_employee_master(db, form, username, customer_id=customer_id)
        log_employee_audit(
            db,
            new_id,
            "import",
            username,
            remarks=f"Imported from {filename or 'spreadsheet'}",
        )
        imported += 1
    return {"ok": True, "imported": imported}
