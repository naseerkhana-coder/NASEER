"""User Management bulk import — validate and save spreadsheet rows."""

from __future__ import annotations

from typing import Any

from bulk_import_service import error_row, validation_result
from company_master_service import get_company, list_companies
from branch_master_service import list_branches_master
from department_master_service import list_departments_master
from user_management_service import (
    USER_STATUSES,
    USER_SYSTEM_ROLES,
    USER_WORKFLOW_ROLES,
    save_user_master,
    validate_password_policy,
    validate_user_uniqueness,
)


def _row_val(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        val = str(row.get(key) or "").strip()
        if val:
            return val
    return ""


def _resolve_company_id(db, row: dict[str, Any]) -> int | None:
    cid = row.get("company_id")
    if cid:
        try:
            return int(cid)
        except (TypeError, ValueError):
            pass
    code = _row_val(row, "company_code", "Company Code")
    if not code:
        return None
    listing = list_companies(db, search=code, per_page=50)
    for item in listing.get("items", []):
        if str(item.get("company_code", "")).upper() == code.upper():
            return int(item["id"])
    return None


def _resolve_branch_id(db, company_id: int, row: dict[str, Any]) -> int | None:
    bid = row.get("branch_id")
    if bid:
        try:
            return int(bid)
        except (TypeError, ValueError):
            pass
    code = _row_val(row, "branch_code", "Branch Code")
    if not code:
        return None
    listing = list_branches_master(db, company_id=company_id, search=code, per_page=50)
    for item in listing.get("items", []):
        if str(item.get("branch_code", "")).upper() == code.upper():
            return int(item["id"])
    return None


def _resolve_department_id(db, company_id: int, row: dict[str, Any]) -> int | None:
    did = row.get("department_id")
    if did:
        try:
            return int(did)
        except (TypeError, ValueError):
            pass
    code = _row_val(row, "department_code", "Department Code")
    if not code:
        return None
    listing = list_departments_master(db, company_id=company_id, search=code, per_page=50)
    for item in listing.get("items", []):
        if str(item.get("department_code", "")).upper() == code.upper():
            return int(item["id"])
    return None


def validate_user_import_rows(db, rows: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    parsed: list[dict] = []
    for row in rows:
        username = _row_val(row, "username", "Username")
        if not username and not _row_val(row, "company_code", "Company Code"):
            continue
        row_num = row.get("_row_num", "?")
        company_id = _resolve_company_id(db, row)
        if not company_id:
            errors.append(error_row(row_num, "Company Code", "Company code is required.", "Enter a valid company code."))
            continue
        if not get_company(db, company_id):
            errors.append(error_row(row_num, "Company Code", "Company not found.", "Use an existing company code."))
            continue
        branch_id = _resolve_branch_id(db, company_id, row)
        if not branch_id:
            errors.append(error_row(row_num, "Branch Code", "Branch is required.", "Enter a valid branch code."))
            continue
        department_id = _resolve_department_id(db, company_id, row)
        if not department_id:
            errors.append(error_row(row_num, "Department Code", "Department is required.", "Enter a valid department code."))
            continue
        if not username:
            errors.append(error_row(row_num, "Username", "Username is required.", "Enter a unique username."))
            continue
        password = _row_val(row, "password", "Password")
        if not password:
            errors.append(error_row(row_num, "Password", "Password is required.", "Enter a password meeting policy."))
            continue
        try:
            validate_password_policy(password)
        except ValueError as exc:
            errors.append(error_row(row_num, "Password", str(exc), "Use a stronger password."))
        email = _row_val(row, "email", "Email")
        mobile = _row_val(row, "mobile", "Mobile")
        try:
            validate_user_uniqueness(db, username=username, email=email, mobile=mobile)
        except ValueError as exc:
            errors.append(error_row(row_num, "Username", str(exc), "Use unique username, email, and mobile."))
        role = _row_val(row, "system_role", "System Role", "role", "Role") or "User"
        if role not in USER_SYSTEM_ROLES:
            errors.append(error_row(row_num, "System Role", f"Invalid role: {role}.", "Use a valid system role."))
        wf_role = _row_val(row, "workflow_role", "Workflow Role") or "Maker"
        if wf_role not in USER_WORKFLOW_ROLES:
            errors.append(error_row(row_num, "Workflow Role", f"Invalid workflow role: {wf_role}.", "Use Maker, Checker, Approver, or Administrator."))
        status = _row_val(row, "status", "Status") or "Active"
        if status not in USER_STATUSES:
            errors.append(error_row(row_num, "Status", f"Invalid status: {status}.", "Use Active or Inactive."))
        parsed.append(
            {
                **row,
                "company_id": company_id,
                "branch_id": branch_id,
                "department_id": department_id,
                "username": username,
                "password": password,
                "first_name": _row_val(row, "first_name", "First Name"),
                "last_name": _row_val(row, "last_name", "Last Name"),
                "display_name": _row_val(row, "display_name", "Display Name"),
                "email": email,
                "mobile": mobile,
                "system_role": role,
                "workflow_role": wf_role,
                "status": status,
            }
        )
    return parsed, errors


def validate_user_import(db, rows: list[dict[str, Any]]) -> dict[str, Any]:
    parsed, errors = validate_user_import_rows(db, rows)
    result = validation_result(parsed, errors)
    result["parsed_rows"] = parsed
    return result


def save_user_import(
    db,
    rows: list[dict[str, Any]],
    *,
    username: str,
    filename: str = "",
    customer_id: int | None = None,
    assert_user_limit_fn=None,
) -> dict[str, Any]:
    imported = 0
    for row in rows:
        class _Form:
            def get(self, key, default=None):
                mapping = {
                    "company_id": row.get("company_id"),
                    "branch_id": row.get("branch_id"),
                    "department_id": row.get("department_id"),
                    "username": row.get("username"),
                    "first_name": row.get("first_name"),
                    "last_name": row.get("last_name"),
                    "display_name": row.get("display_name"),
                    "email": row.get("email"),
                    "mobile": row.get("mobile"),
                    "system_role": row.get("system_role"),
                    "workflow_role": row.get("workflow_role"),
                    "status": row.get("status"),
                }
                return mapping.get(key, default)

        save_user_master(
            db,
            _Form(),
            username,
            password=row.get("password"),
            customer_id=customer_id,
            assert_user_limit_fn=assert_user_limit_fn,
        )
        imported += 1
    return {"ok": True, "imported": imported, "filename": filename}
