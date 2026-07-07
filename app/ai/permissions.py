"""AI permission layer — role, department, module, record, and company access."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai.registry import AIRequest, BaseAIModule


@dataclass
class PermissionResult:
    allowed: bool
    reason: str = ""
    checks: dict[str, bool] | None = None


def _table_exists(db, table: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _column_exists(db, table: str, column: str) -> bool:
    if not _table_exists(db, table):
        return False
    cols = {row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
    return column in cols


def verify_company_access(
    db,
    user_id: int | None,
    company_id: int | None,
    *,
    session_data: dict[str, Any] | None = None,
    is_admin: bool = False,
    is_platform_super_admin: bool = False,
) -> bool:
    if is_platform_super_admin or is_admin:
        return True
    if company_id is None:
        return True
    session_data = session_data or {}
    session_company = session_data.get("company_id")
    if session_company is not None and int(session_company) == int(company_id):
        return True
    if not user_id:
        return False
    try:
        from user_management_service import get_user_master

        user = get_user_master(db, int(user_id))
        if user and user.get("company_id") is not None:
            return int(user["company_id"]) == int(company_id)
    except Exception:
        pass
    try:
        from user_context_service import load_user_context

        ctx = load_user_context(db, int(user_id))
        if ctx and ctx.get("company_id") is not None:
            return int(ctx["company_id"]) == int(company_id)
    except Exception:
        pass
    if _table_exists(db, "users"):
        row = db.execute("SELECT company_id FROM users WHERE id=?", (user_id,)).fetchone()
        if row and row["company_id"] is not None:
            return int(row["company_id"]) == int(company_id)
    return False


def verify_department_access(
    db,
    user_id: int | None,
    department_id: int | None,
    *,
    is_admin: bool = False,
    is_platform_super_admin: bool = False,
) -> bool:
    if is_platform_super_admin or is_admin:
        return True
    if department_id is None:
        return True
    if not user_id:
        return False
    try:
        from user_management_service import get_user_master

        user = get_user_master(db, int(user_id))
        if user and user.get("department_id") is not None:
            return int(user["department_id"]) == int(department_id)
    except Exception:
        pass
    if _table_exists(db, "users"):
        row = db.execute("SELECT department_id FROM users WHERE id=?", (user_id,)).fetchone()
        if row and row["department_id"] is not None:
            return int(row["department_id"]) == int(department_id)
    return True


def verify_module_access(
    db,
    user_id: int | None,
    module: BaseAIModule,
    *,
    action: str = "view",
    is_admin: bool = False,
    is_platform_super_admin: bool = False,
) -> bool:
    if is_platform_super_admin or is_admin:
        return True
    try:
        from user_permission_service import check_user_access_with_roles

        return bool(
            check_user_access_with_roles(
                db,
                user_id,
                module_name=module.erp_module_name,
                screen_name=module.erp_screen_name,
                action=action,
                is_admin=is_admin,
                is_platform_super_admin=is_platform_super_admin,
            )
        )
    except ImportError:
        return True


def verify_record_ownership(
    db,
    user_id: int | None,
    *,
    record_table: str = "",
    record_id: int | None = None,
    username: str = "",
    is_admin: bool = False,
    is_platform_super_admin: bool = False,
) -> bool:
    if is_platform_super_admin or is_admin:
        return True
    if not record_table or record_id is None:
        return True
    if not _table_exists(db, record_table):
        return True
    row = db.execute(
        f"SELECT * FROM {record_table} WHERE id=?",
        (record_id,),
    ).fetchone()
    if not row:
        return False
    record = dict(row)
    if _column_exists(db, record_table, "created_by") and username:
        created_by = (record.get("created_by") or "").strip().lower()
        if created_by and created_by == username.strip().lower():
            return True
    if _column_exists(db, record_table, "user_id") and user_id:
        if record.get("user_id") is not None and int(record["user_id"]) == int(user_id):
            return True
    # If ownership columns exist but do not match, deny; otherwise allow read via module perms.
    ownership_columns = ("created_by", "user_id", "owner_id")
    if any(_column_exists(db, record_table, col) for col in ownership_columns):
        return False
    return True


def verify_ai_permissions(
    db,
    request: AIRequest,
    module: BaseAIModule,
    *,
    session_data: dict[str, Any] | None = None,
) -> PermissionResult:
    """Run all AI permission checks before module execution."""
    session_data = session_data or {}
    username = str(session_data.get("username") or "")
    checks = {
        "company_access": verify_company_access(
            db,
            request.user_id,
            request.company_id,
            session_data=session_data,
            is_admin=request.is_admin,
            is_platform_super_admin=request.is_platform_super_admin,
        ),
        "department_access": verify_department_access(
            db,
            request.user_id,
            request.department_id,
            is_admin=request.is_admin,
            is_platform_super_admin=request.is_platform_super_admin,
        ),
        "module_access": verify_module_access(
            db,
            request.user_id,
            module,
            action=request.action or "view",
            is_admin=request.is_admin,
            is_platform_super_admin=request.is_platform_super_admin,
        ),
        "record_ownership": verify_record_ownership(
            db,
            request.user_id,
            record_table=request.record_table,
            record_id=request.record_id,
            username=username,
            is_admin=request.is_admin,
            is_platform_super_admin=request.is_platform_super_admin,
        ),
    }
    if not checks["company_access"]:
        return PermissionResult(False, "Company access denied.", checks)
    if not checks["department_access"]:
        return PermissionResult(False, "Department access denied.", checks)
    if not checks["module_access"]:
        return PermissionResult(False, f"Module access denied for {module.display_name}.", checks)
    if not checks["record_ownership"]:
        return PermissionResult(False, "Record ownership check failed.", checks)
    return PermissionResult(True, "Allowed", checks)
