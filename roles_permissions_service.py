"""Roles & Permissions (MODULE-006) — role master, permission master, assignments."""

from __future__ import annotations

import csv
import io
import json
import re
from io import BytesIO
from typing import Any

from company_master_service import (
    _ensure_column,
    _now_ts,
    _table_exists,
    ensure_company_master_schema,
    get_company,
    list_companies,
)

ROLE_STATUSES = ("Active", "Inactive")
PERMISSION_STATUSES = ("Active", "Inactive")
STANDARD_ACTIONS: tuple[str, ...] = (
    "view",
    "create",
    "edit",
    "delete",
    "approve",
    "verify",
    "reject",
    "import",
    "export",
    "print",
    "upload",
    "download",
    "search",
    "filter",
    "activate",
    "deactivate",
)
STANDARD_ACTION_LABELS: dict[str, str] = {
    "view": "View",
    "create": "Create",
    "edit": "Edit",
    "delete": "Delete",
    "approve": "Approve",
    "verify": "Verify",
    "reject": "Reject",
    "import": "Import",
    "export": "Export",
    "print": "Print",
    "upload": "Upload",
    "download": "Download",
    "search": "Search",
    "filter": "Filter",
    "activate": "Activate",
    "deactivate": "Deactivate",
}
DEFAULT_ROLE_TYPES: tuple[str, ...] = (
    "Administrator",
    "Management",
    "Project Manager",
    "Site Engineer",
    "Supervisor",
    "Store Keeper",
    "Purchase",
    "Accounts",
    "HR",
    "Payroll",
    "Mechanical",
    "Fleet",
    "Quality",
    "Safety",
    "Planning",
    "Billing",
    "Data Entry",
    "Viewer",
    "Custom Role",
)
ROLE_SORT_COLUMNS = ("role_code", "role_name", "status", "created_at", "company_id")
PERMISSION_SORT_COLUMNS = ("permission_code", "permission_name", "module_name", "screen_name", "status")
ROLE_EXPORT_COLUMNS = (
    "company_code",
    "company_name",
    "role_code",
    "role_name",
    "description",
    "status",
    "permission_count",
    "user_count",
)
ROLE_AUDIT_FIELDS = ("role_code", "role_name", "description", "company_id", "status")
PERMISSION_AUDIT_FIELDS = (
    "permission_code",
    "permission_name",
    "module_name",
    "menu_name",
    "screen_name",
    "field_name",
    "action",
    "description",
    "status",
)
ADMINISTRATOR_ROLE_CODES = frozenset({"ADMINISTRATOR", "ADMIN", "SUPER-ADMINISTRATOR"})
SEED_MODULE_SCREENS: tuple[tuple[str, str, str], ...] = (
    ("Settings", "settings", "Company Settings"),
    ("Settings", "company_master", "Company Master"),
    ("Settings", "branch_master", "Branch Master"),
    ("Settings", "department_master", "Department Master"),
    ("Settings", "designation_master", "Designation Master"),
    ("Settings", "employee_master", "Employee Master"),
    ("Settings", "worker_master", "Worker Master"),
    ("Settings", "client_master", "Client Master"),
    ("Projects", "project_master", "Project Master"),
    ("Settings", "subcontractor_master", "Subcontractor Master"),
    ("Settings", "user_management", "User Management"),
    ("Settings", "roles_permissions", "Roles & Permissions"),
    ("Settings", "workflow_settings", "Workflow Settings"),
    ("Settings", "workflow_engine", "Workflow Engine"),
    ("Settings", "document_management", "Document Management"),
    ("Settings", "notification_center", "Notification Center"),
    ("Administration", "corporate_dms", "Corporate DMS (Legacy)"),
    ("Projects", "projects", "Project List"),
    ("Projects", "boq_management", "BOQ Master"),
    ("Store", "store", "Store Dashboard"),
    ("Accounts", "accounts_hub", "Accounts Dashboard"),
    ("HR", "workforce_dashboard", "HR Dashboard"),
    ("Approvals", "approvals", "Approval Dashboard"),
)


def empty_action_flags() -> dict[str, bool]:
    return {key: False for key in STANDARD_ACTIONS}


def full_action_flags() -> dict[str, bool]:
    return {key: True for key in STANDARD_ACTIONS}


def view_only_action_flags() -> dict[str, bool]:
    flags = empty_action_flags()
    flags["view"] = True
    flags["search"] = True
    flags["filter"] = True
    return flags


def normalize_action_flags(raw: Any) -> dict[str, bool]:
    base = empty_action_flags()
    if not isinstance(raw, dict):
        if isinstance(raw, str) and raw.strip():
            try:
                raw = json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                return base
        else:
            return base
    for key in STANDARD_ACTIONS:
        base[key] = bool(raw.get(key))
    return base


def ensure_roles_permissions_schema(db) -> None:
    """Bootstrap MODULE-006 tables (idempotent)."""
    ensure_company_master_schema(db)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS roles(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_code TEXT,
            role_name TEXT,
            description TEXT,
            company_id INTEGER,
            status TEXT DEFAULT 'Active',
            is_system INTEGER DEFAULT 0,
            created_by TEXT,
            updated_by TEXT,
            created_at TEXT,
            updated_at TEXT,
            is_deleted INTEGER DEFAULT 0,
            deleted_by TEXT,
            deleted_at TEXT,
            customer_id INTEGER
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS permissions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            permission_code TEXT,
            permission_name TEXT,
            module_name TEXT,
            menu_name TEXT,
            screen_name TEXT,
            field_name TEXT,
            action TEXT,
            description TEXT,
            status TEXT DEFAULT 'Active',
            created_by TEXT,
            updated_by TEXT,
            created_at TEXT,
            updated_at TEXT,
            is_deleted INTEGER DEFAULT 0,
            deleted_by TEXT,
            deleted_at TEXT
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS role_permissions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_id INTEGER NOT NULL,
            permission_id INTEGER NOT NULL,
            action_flags TEXT,
            created_by TEXT,
            created_at TEXT,
            updated_by TEXT,
            updated_at TEXT,
            UNIQUE(role_id, permission_id),
            FOREIGN KEY(role_id) REFERENCES roles(id),
            FOREIGN KEY(permission_id) REFERENCES permissions(id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS user_roles(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            assigned_by TEXT,
            assigned_at TEXT,
            UNIQUE(user_id, role_id),
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(role_id) REFERENCES roles(id)
        )
        """
    )
    for col, ctype in (
        ("is_system", "INTEGER DEFAULT 0"),
        ("customer_id", "INTEGER"),
        ("menu_name", "TEXT"),
        ("field_name", "TEXT"),
    ):
        table = "roles" if col in ("is_system", "customer_id") else "permissions"
        if col in ("menu_name", "field_name"):
            table = "permissions"
        _ensure_column(db, table, col, ctype)
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_roles_company ON roles(company_id, status)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_permissions_module ON permissions(module_name, screen_name)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles(user_id)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_role_permissions_role ON role_permissions(role_id)"
    )
    try:
        from audit_trail_service import ensure_audit_schema

        ensure_audit_schema(db)
    except Exception:
        pass
    _seed_default_permissions(db)
    _seed_default_roles(db)


def _seed_default_permissions(db) -> None:
    if not _table_exists(db, "permissions"):
        return
    count = int(db.execute("SELECT COUNT(*) FROM permissions WHERE COALESCE(is_deleted,0)=0").fetchone()[0])
    if count:
        return
    now = _now_ts()
    for module_name, screen_name, label in SEED_MODULE_SCREENS:
        code = f"{module_name[:3].upper()}-{screen_name.upper().replace('_', '-')}"
        db.execute(
            """
            INSERT INTO permissions(
                permission_code, permission_name, module_name, menu_name, screen_name,
                action, description, status, created_by, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                code,
                label,
                module_name,
                module_name,
                screen_name,
                "",
                f"Access to {label}",
                "Active",
                "system",
                now,
            ),
        )


def _seed_default_roles(db) -> None:
    if not _table_exists(db, "roles"):
        return
    count = int(db.execute("SELECT COUNT(*) FROM roles WHERE COALESCE(is_deleted,0)=0").fetchone()[0])
    if count:
        return
    first_company = db.execute(
        "SELECT id FROM companies WHERE COALESCE(is_deleted,0)=0 ORDER BY id LIMIT 1"
    ).fetchone()
    company_id = int(first_company[0]) if first_company else None
    if not company_id:
        return
    now = _now_ts()
    admin_role_id: int | None = None
    for role_name in DEFAULT_ROLE_TYPES:
        slug = re.sub(r"[^A-Za-z0-9]+", "-", role_name).strip("-").upper()
        code = slug[:40] or f"ROLE-{role_name[:8].upper()}"
        cur = db.execute(
            """
            INSERT INTO roles(
                role_code, role_name, description, company_id, status, is_system,
                created_by, created_at
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                code,
                role_name,
                f"Default {role_name} role",
                company_id,
                "Active",
                1,
                "system",
                now,
            ),
        )
        rid = int(cur.lastrowid)
        if role_name == "Administrator":
            admin_role_id = rid
    if admin_role_id:
        perm_rows = db.execute(
            "SELECT id FROM permissions WHERE COALESCE(is_deleted,0)=0 AND status='Active'"
        ).fetchall()
        flags = json.dumps(full_action_flags(), sort_keys=True)
        for prow in perm_rows:
            db.execute(
                """
                INSERT OR IGNORE INTO role_permissions(role_id, permission_id, action_flags, created_by, created_at)
                VALUES (?,?,?,?,?)
                """,
                (admin_role_id, int(prow[0]), flags, "system", now),
            )
    viewer_id = db.execute(
        "SELECT id FROM roles WHERE role_name='Viewer' AND company_id=? LIMIT 1",
        (company_id,),
    ).fetchone()
    if viewer_id:
        flags = json.dumps(view_only_action_flags(), sort_keys=True)
        for prow in db.execute(
            "SELECT id FROM permissions WHERE COALESCE(is_deleted,0)=0 AND status='Active'"
        ).fetchall():
            db.execute(
                """
                INSERT OR IGNORE INTO role_permissions(role_id, permission_id, action_flags, created_by, created_at)
                VALUES (?,?,?,?,?)
                """,
                (int(viewer_id[0]), int(prow[0]), flags, "system", now),
            )


def log_role_audit(
    db,
    role_id: int,
    action: str,
    username: str,
    *,
    field_name: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
    remarks: str | None = None,
) -> None:
    try:
        from audit_trail_service import log_audit_event

        log_audit_event(
            db,
            record_table="roles",
            record_id=role_id,
            action=action,
            changed_by=username,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            remarks=remarks,
        )
    except Exception:
        pass


def log_permission_audit(
    db,
    permission_id: int,
    action: str,
    username: str,
    *,
    field_name: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
    remarks: str | None = None,
) -> None:
    try:
        from audit_trail_service import log_audit_event

        log_audit_event(
            db,
            record_table="permissions",
            record_id=permission_id,
            action=action,
            changed_by=username,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            remarks=remarks,
        )
    except Exception:
        pass


def list_role_audit_trail(db, role_id: int, limit: int = 100) -> list[dict[str, Any]]:
    try:
        from audit_trail_service import list_audit_trail

        return list_audit_trail(db, "roles", role_id, limit=limit)
    except Exception:
        return []


def list_permission_audit_trail(db, permission_id: int, limit: int = 100) -> list[dict[str, Any]]:
    try:
        from audit_trail_service import list_audit_trail

        return list_audit_trail(db, "permissions", permission_id, limit=limit)
    except Exception:
        return []


def _user_has_administrator_role(db, user_id: int | None) -> bool:
    if not user_id or not _table_exists(db, "user_roles"):
        return False
    row = db.execute(
        """
        SELECT 1 FROM user_roles ur
        JOIN roles r ON ur.role_id = r.id
        WHERE ur.user_id=? AND COALESCE(r.is_deleted,0)=0 AND r.status='Active'
          AND (
            UPPER(r.role_code) IN ('ADMINISTRATOR','ADMIN','SUPER-ADMINISTRATOR')
            OR LOWER(r.role_name) IN ('administrator','super administrator')
          )
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    return bool(row)


def is_roles_super_administrator(
    db,
    user_id: int | None,
    *,
    is_platform_super_admin: bool = False,
) -> bool:
    """Only Super Administrator / platform super admin may manage roles and permissions."""
    if is_platform_super_admin:
        return True
    return _user_has_administrator_role(db, user_id)


def user_can_roles_permissions(
    db,
    user_id: int | None,
    action: str,
    *,
    is_admin: bool = False,
    is_platform_super_admin: bool = False,
) -> bool:
    if is_platform_super_admin or is_roles_super_administrator(
        db, user_id, is_platform_super_admin=is_platform_super_admin
    ):
        return True
    if is_admin and action in ("view", "export", "search", "filter"):
        return True
    if not user_id:
        return False
    privileged = {"create", "edit", "delete", "import", "activate", "deactivate"}
    if action in privileged or action in ("approve", "verify", "reject"):
        return False
    action_map = {"deactivate": "edit", "activate": "edit"}
    check = action_map.get(action, action)
    try:
        from user_permission_service import (
            empty_permission_actions,
            ensure_user_tab_permissions_schema,
            normalize_permission_actions,
        )

        ensure_user_tab_permissions_schema(db)
        row = db.execute(
            """
            SELECT granted, action_flags FROM user_tab_permissions
            WHERE user_id=? AND granted=1 AND endpoint='roles_permissions'
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        if not row:
            return False
        raw_flags = row["action_flags"] if hasattr(row, "keys") else row[1]
        actions = normalize_permission_actions(
            json.loads(raw_flags) if raw_flags else empty_permission_actions()
        )
        if check == "import":
            return bool(actions.get("import") or actions.get("create"))
        if check == "delete":
            return bool(actions.get("delete") or actions.get("edit"))
        return bool(actions.get(check))
    except Exception:
        return False


def validate_role_uniqueness(
    db,
    *,
    company_id: int,
    role_code: str,
    role_name: str,
    role_id: int | None = None,
) -> None:
    code = (role_code or "").strip().upper()
    name = (role_name or "").strip()
    if not code:
        raise ValueError("Role code is required.")
    if not name:
        raise ValueError("Role name is required.")
    row = db.execute(
        """
        SELECT id FROM roles
        WHERE company_id=? AND UPPER(role_code)=? AND COALESCE(is_deleted,0)=0
        """,
        (company_id, code),
    ).fetchone()
    if row and (not role_id or int(row[0]) != int(role_id)):
        raise ValueError(f"Role code '{role_code}' already exists for this company.")
    row = db.execute(
        """
        SELECT id FROM roles
        WHERE company_id=? AND LOWER(role_name)=LOWER(?) AND COALESCE(is_deleted,0)=0
        """,
        (company_id, name),
    ).fetchone()
    if row and (not role_id or int(row[0]) != int(role_id)):
        raise ValueError(f"Role name '{role_name}' already exists for this company.")


def validate_permission_uniqueness(
    db,
    *,
    permission_code: str,
    permission_id: int | None = None,
) -> None:
    code = (permission_code or "").strip().upper()
    if not code:
        raise ValueError("Permission code is required.")
    row = db.execute(
        """
        SELECT id FROM permissions
        WHERE UPPER(permission_code)=? AND COALESCE(is_deleted,0)=0
        """,
        (code,),
    ).fetchone()
    if row and (not permission_id or int(row[0]) != int(permission_id)):
        raise ValueError(f"Permission code '{permission_code}' already exists.")


def _next_role_code(db, company_id: int) -> str:
    prefix = f"ROL-{company_id}-"
    row = db.execute(
        """
        SELECT role_code FROM roles
        WHERE company_id=? AND role_code LIKE ? AND COALESCE(is_deleted,0)=0
        ORDER BY id DESC LIMIT 1
        """,
        (company_id, f"{prefix}%"),
    ).fetchone()
    seq = 1
    if row and row[0]:
        m = re.search(r"-(\d+)$", str(row[0]))
        if m:
            seq = int(m.group(1)) + 1
    return f"{prefix}{seq:03d}"


def list_roles_master(
    db,
    *,
    search: str = "",
    company_id: int | None = None,
    status: str = "",
    customer_id: int | None = None,
    include_deleted: bool = False,
    page: int = 1,
    per_page: int = 25,
    sort_by: str = "role_name",
    sort_dir: str = "asc",
) -> dict[str, Any]:
    if not _table_exists(db, "roles"):
        return {"items": [], "total": 0, "page": 1, "per_page": per_page, "pages": 0}
    sql = (
        "SELECT r.*, c.company_code, c.company_name, "
        "(SELECT COUNT(*) FROM role_permissions rp WHERE rp.role_id=r.id) AS permission_count, "
        "(SELECT COUNT(*) FROM user_roles ur WHERE ur.role_id=r.id) AS user_count "
        "FROM roles r LEFT JOIN companies c ON r.company_id=c.id WHERE 1=1"
    )
    count_sql = "SELECT COUNT(*) FROM roles r WHERE 1=1"
    params: list[Any] = []
    if not include_deleted:
        sql += " AND COALESCE(r.is_deleted,0)=0"
        count_sql += " AND COALESCE(r.is_deleted,0)=0"
    if customer_id is not None:
        sql += " AND (r.customer_id IS ? OR (r.customer_id IS NULL AND ? IS NULL))"
        count_sql += " AND (r.customer_id IS ? OR (r.customer_id IS NULL AND ? IS NULL))"
        params.extend([customer_id, customer_id])
    if company_id:
        sql += " AND r.company_id=?"
        count_sql += " AND r.company_id=?"
        params.append(company_id)
    if status:
        sql += " AND r.status=?"
        count_sql += " AND r.status=?"
        params.append(status)
    if search:
        clause = " AND (r.role_code LIKE ? OR r.role_name LIKE ? OR r.description LIKE ?)"
        sql += clause
        count_sql += clause
        like = f"%{search}%"
        params.extend([like, like, like])
    sort_col = sort_by if sort_by in ROLE_SORT_COLUMNS else "role_name"
    sort_col = f"r.{sort_col}"
    direction = "DESC" if str(sort_dir).lower() == "desc" else "ASC"
    sql += f" ORDER BY {sort_col} {direction}, r.id DESC"
    per_page = max(1, min(int(per_page or 25), 10000))
    page = max(1, int(page or 1))
    offset = (page - 1) * per_page
    sql += " LIMIT ? OFFSET ?"
    total = int(db.execute(count_sql, params).fetchone()[0])
    rows = db.execute(sql, [*params, per_page, offset]).fetchall()
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if total else 0,
    }


def get_role_master(db, role_id: int, *, include_deleted: bool = False) -> dict[str, Any] | None:
    if not role_id:
        return None
    row = db.execute(
        """
        SELECT r.*, c.company_code, c.company_name
        FROM roles r LEFT JOIN companies c ON r.company_id=c.id
        WHERE r.id=?
        """
        + ("" if include_deleted else " AND COALESCE(r.is_deleted,0)=0"),
        (role_id,),
    ).fetchone()
    return dict(row) if row else None


def list_permissions_master(
    db,
    *,
    search: str = "",
    module_name: str = "",
    screen_name: str = "",
    status: str = "",
    include_deleted: bool = False,
    page: int = 1,
    per_page: int = 50,
    sort_by: str = "module_name",
    sort_dir: str = "asc",
) -> dict[str, Any]:
    if not _table_exists(db, "permissions"):
        return {"items": [], "total": 0, "page": 1, "per_page": per_page, "pages": 0}
    sql = "SELECT * FROM permissions WHERE 1=1"
    count_sql = "SELECT COUNT(*) FROM permissions WHERE 1=1"
    params: list[Any] = []
    if not include_deleted:
        sql += " AND COALESCE(is_deleted,0)=0"
        count_sql += " AND COALESCE(is_deleted,0)=0"
    if module_name:
        sql += " AND module_name=?"
        count_sql += " AND module_name=?"
        params.append(module_name)
    if screen_name:
        sql += " AND screen_name=?"
        count_sql += " AND screen_name=?"
        params.append(screen_name)
    if status:
        sql += " AND status=?"
        count_sql += " AND status=?"
        params.append(status)
    if search:
        clause = (
            " AND (permission_code LIKE ? OR permission_name LIKE ? "
            "OR module_name LIKE ? OR screen_name LIKE ? OR description LIKE ?)"
        )
        sql += clause
        count_sql += clause
        like = f"%{search}%"
        params.extend([like, like, like, like, like])
    sort_col = sort_by if sort_by in PERMISSION_SORT_COLUMNS else "module_name"
    direction = "DESC" if str(sort_dir).lower() == "desc" else "ASC"
    sql += f" ORDER BY {sort_col} {direction}, id DESC"
    per_page = max(1, min(int(per_page or 50), 10000))
    page = max(1, int(page or 1))
    offset = (page - 1) * per_page
    sql += " LIMIT ? OFFSET ?"
    total = int(db.execute(count_sql, params).fetchone()[0])
    rows = db.execute(sql, [*params, per_page, offset]).fetchall()
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if total else 0,
    }


def get_permission_master(db, permission_id: int, *, include_deleted: bool = False) -> dict[str, Any] | None:
    if not permission_id:
        return None
    row = db.execute(
        "SELECT * FROM permissions WHERE id=?"
        + ("" if include_deleted else " AND COALESCE(is_deleted,0)=0"),
        (permission_id,),
    ).fetchone()
    return dict(row) if row else None


def _parse_role_form(form) -> dict[str, Any]:
    return {
        "company_id": int(form.get("company_id") or 0),
        "role_code": (form.get("role_code") or "").strip(),
        "role_name": (form.get("role_name") or "").strip(),
        "description": (form.get("description") or "").strip(),
        "status": (form.get("status") or "Active").strip(),
    }


def _parse_permission_form(form) -> dict[str, Any]:
    return {
        "permission_code": (form.get("permission_code") or "").strip(),
        "permission_name": (form.get("permission_name") or "").strip(),
        "module_name": (form.get("module_name") or "").strip(),
        "menu_name": (form.get("menu_name") or "").strip(),
        "screen_name": (form.get("screen_name") or "").strip(),
        "field_name": (form.get("field_name") or "").strip(),
        "action": (form.get("action") or "").strip(),
        "description": (form.get("description") or "").strip(),
        "status": (form.get("status") or "Active").strip(),
    }


def save_role_master(
    db,
    form,
    username: str,
    role_id: int | None = None,
    *,
    customer_id: int | None = None,
) -> int:
    data = _parse_role_form(form)
    company_id = data["company_id"]
    if not company_id:
        raise ValueError("Company is required.")
    if not get_company(db, company_id):
        raise ValueError("Selected company was not found.")
    if not data["role_code"]:
        data["role_code"] = _next_role_code(db, company_id)
    if data["status"] not in ROLE_STATUSES:
        raise ValueError("Select a valid status.")
    validate_role_uniqueness(
        db,
        company_id=company_id,
        role_code=data["role_code"],
        role_name=data["role_name"],
        role_id=role_id,
    )
    now = _now_ts()
    before = get_role_master(db, role_id, include_deleted=True) if role_id else None
    if role_id:
        db.execute(
            """
            UPDATE roles SET role_code=?, role_name=?, description=?, company_id=?, status=?,
            updated_by=?, updated_at=?, customer_id=COALESCE(?, customer_id)
            WHERE id=? AND COALESCE(is_deleted,0)=0
            """,
            (
                data["role_code"].upper(),
                data["role_name"],
                data["description"],
                company_id,
                data["status"],
                username,
                now,
                customer_id,
                role_id,
            ),
        )
        after = get_role_master(db, role_id)
        if before and after:
            for field in ROLE_AUDIT_FIELDS:
                if str(before.get(field) or "") != str(after.get(field) or ""):
                    log_role_audit(
                        db,
                        role_id,
                        "update",
                        username,
                        field_name=field,
                        old_value=str(before.get(field) or ""),
                        new_value=str(after.get(field) or ""),
                    )
        return role_id
    cur = db.execute(
        """
        INSERT INTO roles(
            role_code, role_name, description, company_id, status, is_system,
            created_by, created_at, customer_id
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            data["role_code"].upper(),
            data["role_name"],
            data["description"],
            company_id,
            data["status"],
            0,
            username,
            now,
            customer_id,
        ),
    )
    new_id = int(cur.lastrowid)
    log_role_audit(db, new_id, "create", username)
    try:
        from audit_trail_service import stamp_created

        stamp_created(db, "roles", new_id, username)
    except Exception:
        pass
    return new_id


def save_permission_master(
    db,
    form,
    username: str,
    permission_id: int | None = None,
) -> int:
    data = _parse_permission_form(form)
    if not data["permission_name"]:
        raise ValueError("Permission name is required.")
    if not data["module_name"]:
        raise ValueError("Module name is required.")
    if not data["permission_code"]:
        slug = re.sub(r"[^A-Za-z0-9]+", "-", data["permission_name"]).strip("-").upper()
        data["permission_code"] = f"PERM-{slug[:30] or 'NEW'}"
    if data["status"] not in PERMISSION_STATUSES:
        raise ValueError("Select a valid status.")
    validate_permission_uniqueness(db, permission_code=data["permission_code"], permission_id=permission_id)
    now = _now_ts()
    before = get_permission_master(db, permission_id, include_deleted=True) if permission_id else None
    if permission_id:
        db.execute(
            """
            UPDATE permissions SET permission_code=?, permission_name=?, module_name=?, menu_name=?,
            screen_name=?, field_name=?, action=?, description=?, status=?, updated_by=?, updated_at=?
            WHERE id=? AND COALESCE(is_deleted,0)=0
            """,
            (
                data["permission_code"].upper(),
                data["permission_name"],
                data["module_name"],
                data["menu_name"] or data["module_name"],
                data["screen_name"],
                data["field_name"],
                data["action"],
                data["description"],
                data["status"],
                username,
                now,
                permission_id,
            ),
        )
        after = get_permission_master(db, permission_id)
        if before and after:
            for field in PERMISSION_AUDIT_FIELDS:
                if str(before.get(field) or "") != str(after.get(field) or ""):
                    log_permission_audit(
                        db,
                        permission_id,
                        "update",
                        username,
                        field_name=field,
                        old_value=str(before.get(field) or ""),
                        new_value=str(after.get(field) or ""),
                    )
        return permission_id
    cur = db.execute(
        """
        INSERT INTO permissions(
            permission_code, permission_name, module_name, menu_name, screen_name,
            field_name, action, description, status, created_by, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            data["permission_code"].upper(),
            data["permission_name"],
            data["module_name"],
            data["menu_name"] or data["module_name"],
            data["screen_name"],
            data["field_name"],
            data["action"],
            data["description"],
            data["status"],
            username,
            now,
        ),
    )
    new_id = int(cur.lastrowid)
    log_permission_audit(db, new_id, "create", username)
    try:
        from audit_trail_service import stamp_created

        stamp_created(db, "permissions", new_id, username)
    except Exception:
        pass
    return new_id


def soft_delete_role_master(db, role_id: int, username: str) -> None:
    row = get_role_master(db, role_id)
    if not row:
        raise ValueError("Role not found.")
    if int(row.get("is_system") or 0):
        raise ValueError("System roles cannot be deleted.")
    refs = db.execute("SELECT COUNT(*) FROM user_roles WHERE role_id=?", (role_id,)).fetchone()[0]
    if int(refs) > 0:
        raise ValueError("Role is assigned to users. Remove assignments before deleting.")
    now = _now_ts()
    db.execute(
        """
        UPDATE roles SET is_deleted=1, deleted_by=?, deleted_at=?, updated_by=?, updated_at=?
        WHERE id=?
        """,
        (username, now, username, now, role_id),
    )
    log_role_audit(db, role_id, "delete", username)


def soft_delete_permission_master(db, permission_id: int, username: str) -> None:
    row = get_permission_master(db, permission_id)
    if not row:
        raise ValueError("Permission not found.")
    now = _now_ts()
    db.execute(
        """
        UPDATE permissions SET is_deleted=1, deleted_by=?, deleted_at=?, updated_by=?, updated_at=?
        WHERE id=?
        """,
        (username, now, username, now, permission_id),
    )
    db.execute("DELETE FROM role_permissions WHERE permission_id=?", (permission_id,))
    log_permission_audit(db, permission_id, "delete", username)


def activate_role_master(db, role_id: int, username: str) -> None:
    db.execute(
        "UPDATE roles SET status='Active', updated_by=?, updated_at=? WHERE id=? AND COALESCE(is_deleted,0)=0",
        (username, _now_ts(), role_id),
    )
    log_role_audit(db, role_id, "activate", username)


def deactivate_role_master(db, role_id: int, username: str) -> None:
    db.execute(
        "UPDATE roles SET status='Inactive', updated_by=?, updated_at=? WHERE id=? AND COALESCE(is_deleted,0)=0",
        (username, _now_ts(), role_id),
    )
    log_role_audit(db, role_id, "deactivate", username)


def get_role_permission_matrix(db, role_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        """
        SELECT p.*, rp.action_flags, rp.id AS mapping_id
        FROM permissions p
        LEFT JOIN role_permissions rp ON rp.permission_id=p.id AND rp.role_id=?
        WHERE COALESCE(p.is_deleted,0)=0
        ORDER BY p.module_name, p.screen_name, p.permission_name
        """,
        (role_id,),
    ).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["action_flags"] = normalize_action_flags(item.get("action_flags"))
        item["assigned"] = item.get("mapping_id") is not None
        items.append(item)
    return items


def save_role_permission_matrix(
    db,
    role_id: int,
    assignments: list[dict[str, Any]],
    username: str,
) -> int:
    if not get_role_master(db, role_id):
        raise ValueError("Role not found.")
    now = _now_ts()
    saved = 0
    for item in assignments:
        perm_id = int(item.get("permission_id") or 0)
        if not perm_id:
            continue
        flags = normalize_action_flags(item.get("action_flags") or {})
        if not any(flags.values()):
            db.execute(
                "DELETE FROM role_permissions WHERE role_id=? AND permission_id=?",
                (role_id, perm_id),
            )
            continue
        db.execute(
            """
            INSERT INTO role_permissions(role_id, permission_id, action_flags, created_by, created_at, updated_by, updated_at)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(role_id, permission_id) DO UPDATE SET
                action_flags=excluded.action_flags,
                updated_by=excluded.updated_by,
                updated_at=excluded.updated_at
            """,
            (role_id, perm_id, json.dumps(flags, sort_keys=True), username, now, username, now),
        )
        saved += 1
    log_role_audit(db, role_id, "permission_matrix_update", username, remarks=f"{saved} permissions updated")
    return saved


def list_users_for_role(db, role_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        """
        SELECT u.id, u.username, u.employee_name, u.email, u.status, ur.assigned_at, ur.assigned_by
        FROM user_roles ur
        JOIN users u ON u.id=ur.user_id
        WHERE ur.role_id=?
        ORDER BY u.username
        """,
        (role_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_roles_for_user(db, user_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        """
        SELECT r.*, ur.assigned_at, ur.assigned_by
        FROM user_roles ur
        JOIN roles r ON r.id=ur.role_id
        WHERE ur.user_id=? AND COALESCE(r.is_deleted,0)=0
        ORDER BY r.role_name
        """,
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def assign_roles_to_user(
    db,
    user_id: int,
    role_ids: list[int],
    username: str,
) -> dict[str, Any]:
    if not _table_exists(db, "users"):
        raise ValueError("Users table not found.")
    user = db.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone()
    if not user:
        raise ValueError("User not found.")
    now = _now_ts()
    clean_ids = sorted({int(rid) for rid in role_ids if rid})
    existing = {
        int(r[0])
        for r in db.execute("SELECT role_id FROM user_roles WHERE user_id=?", (user_id,)).fetchall()
    }
    to_add = set(clean_ids) - existing
    to_remove = existing - set(clean_ids)
    for rid in to_remove:
        db.execute("DELETE FROM user_roles WHERE user_id=? AND role_id=?", (user_id, rid))
    for rid in to_add:
        role = get_role_master(db, rid)
        if not role:
            raise ValueError(f"Role id {rid} not found.")
        db.execute(
            """
            INSERT OR IGNORE INTO user_roles(user_id, role_id, assigned_by, assigned_at)
            VALUES (?,?,?,?)
            """,
            (user_id, rid, username, now),
        )
    return {"user_id": user_id, "assigned": clean_ids, "added": list(to_add), "removed": list(to_remove)}


def assign_users_to_role(
    db,
    role_id: int,
    user_ids: list[int],
    username: str,
) -> dict[str, Any]:
    if not get_role_master(db, role_id):
        raise ValueError("Role not found.")
    now = _now_ts()
    clean_ids = sorted({int(uid) for uid in user_ids if uid})
    existing = {
        int(r[0])
        for r in db.execute("SELECT user_id FROM user_roles WHERE role_id=?", (role_id,)).fetchall()
    }
    to_add = set(clean_ids) - existing
    to_remove = existing - set(clean_ids)
    for uid in to_remove:
        db.execute("DELETE FROM user_roles WHERE user_id=? AND role_id=?", (uid, role_id))
    for uid in to_add:
        user = db.execute("SELECT id FROM users WHERE id=?", (uid,)).fetchone()
        if not user:
            raise ValueError(f"User id {uid} not found.")
        db.execute(
            """
            INSERT OR IGNORE INTO user_roles(user_id, role_id, assigned_by, assigned_at)
            VALUES (?,?,?,?)
            """,
            (uid, role_id, username, now),
        )
    log_role_audit(db, role_id, "user_assignment", username, remarks=f"users: {clean_ids}")
    return {"role_id": role_id, "assigned": clean_ids, "added": list(to_add), "removed": list(to_remove)}


def aggregate_user_role_permissions(db, user_id: int) -> dict[str, dict[str, bool]]:
    """Merged action flags keyed by permission_code from all active roles."""
    merged: dict[str, dict[str, bool]] = {}
    if not user_id or not _table_exists(db, "user_roles"):
        return merged
    rows = db.execute(
        """
        SELECT p.permission_code, p.module_name, p.screen_name, p.field_name, rp.action_flags
        FROM user_roles ur
        JOIN roles r ON r.id=ur.role_id
        JOIN role_permissions rp ON rp.role_id=r.id
        JOIN permissions p ON p.id=rp.permission_id
        WHERE ur.user_id=? AND COALESCE(r.is_deleted,0)=0 AND r.status='Active'
          AND COALESCE(p.is_deleted,0)=0 AND p.status='Active'
        """,
        (user_id,),
    ).fetchall()
    for row in rows:
        code = str(row["permission_code"] if hasattr(row, "keys") else row[0])
        flags = normalize_action_flags(row["action_flags"] if hasattr(row, "keys") else row[4])
        if code not in merged:
            merged[code] = empty_action_flags()
        for action, granted in flags.items():
            if granted:
                merged[code][action] = True
    return merged


def user_has_assigned_role_permission(
    db,
    user_id: int | None,
    *,
    module_name: str = "",
    screen_name: str = "",
    menu_name: str = "",
    field_name: str = "",
    action: str = "view",
    is_platform_super_admin: bool = False,
) -> bool | None:
    """
    Check MODULE-006 role-based permission.
    Returns True/False when role assignments exist; None when no roles module data (caller may fall back).
    """
    if is_platform_super_admin:
        return True
    if not user_id:
        return False
    if is_roles_super_administrator(db, user_id, is_platform_super_admin=False):
        return True
    if not _table_exists(db, "user_roles"):
        return None
    role_count = int(
        db.execute("SELECT COUNT(*) FROM user_roles WHERE user_id=?", (user_id,)).fetchone()[0]
    )
    if role_count == 0:
        return None
    action_key = (action or "view").lower()
    if action_key not in STANDARD_ACTIONS:
        action_key = "view"
    sql = """
        SELECT rp.action_flags
        FROM user_roles ur
        JOIN roles r ON r.id=ur.role_id
        JOIN role_permissions rp ON rp.role_id=r.id
        JOIN permissions p ON p.id=rp.permission_id
        WHERE ur.user_id=? AND COALESCE(r.is_deleted,0)=0 AND r.status='Active'
          AND COALESCE(p.is_deleted,0)=0 AND p.status='Active'
    """
    params: list[Any] = [user_id]
    if module_name:
        sql += " AND LOWER(p.module_name)=LOWER(?)"
        params.append(module_name)
    if screen_name:
        sql += " AND LOWER(p.screen_name)=LOWER(?)"
        params.append(screen_name)
    if menu_name:
        sql += " AND LOWER(COALESCE(p.menu_name,''))=LOWER(?)"
        params.append(menu_name)
    if field_name:
        sql += " AND (p.field_name IS NULL OR p.field_name='' OR LOWER(p.field_name)=LOWER(?))"
        params.append(field_name)
    rows = db.execute(sql, params).fetchall()
    if not rows:
        return False
    for row in rows:
        flags = normalize_action_flags(row["action_flags"] if hasattr(row, "keys") else row[0])
        if flags.get(action_key):
            return True
    return False


def roles_for_export(db, **filters) -> list[dict[str, Any]]:
    listing = list_roles_master(db, per_page=10000, **filters)
    return listing.get("items", [])


def export_roles_excel(db, **filters) -> BytesIO:
    from openpyxl import Workbook

    rows = roles_for_export(db, **filters)
    wb = Workbook()
    ws = wb.active
    ws.title = "Roles"
    headers = list(ROLE_EXPORT_COLUMNS)
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h, "") for h in headers])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def export_roles_csv(db, **filters) -> str:
    rows = roles_for_export(db, **filters)
    si = io.StringIO()
    writer = csv.writer(si)
    headers = list(ROLE_EXPORT_COLUMNS)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row.get(h, "") for h in headers])
    return si.getvalue()


def export_roles_pdf(db, *, report_title: str = "Roles & Permissions Report", **filters) -> BytesIO:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas

    rows = roles_for_export(db, **filters)
    buf = BytesIO()
    page_size = landscape(A4)
    c = canvas.Canvas(buf, pagesize=page_size)
    _, height = page_size
    y = height - 40
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, f"MAXEK ERP — {report_title}")
    y -= 24
    c.setFont("Helvetica", 9)
    for row in rows[:250]:
        line = (
            f"{row.get('company_code')} | {row.get('role_code')} | {row.get('role_name')} | "
            f"perms:{row.get('permission_count')} users:{row.get('user_count')} | {row.get('status')}"
        )
        if y < 40:
            c.showPage()
            y = height - 40
            c.setFont("Helvetica", 9)
        c.drawString(40, y, line[:130])
        y -= 14
    c.save()
    buf.seek(0)
    return buf


def roles_permissions_report(db, report_key: str, **filters) -> list[dict[str, Any]]:
    key = (report_key or "").lower().strip()
    if key == "roles_by_company":
        return roles_for_export(db, **filters)
    if key == "unassigned_roles":
        listing = list_roles_master(db, per_page=10000, **filters)
        return [r for r in listing["items"] if int(r.get("user_count") or 0) == 0]
    if key == "roles_without_permissions":
        listing = list_roles_master(db, per_page=10000, **filters)
        return [r for r in listing["items"] if int(r.get("permission_count") or 0) == 0]
    return roles_for_export(db, **filters)


def roles_import_template() -> BytesIO:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Roles"
    ws.append(["company_code", "role_code", "role_name", "description", "status"])
    ws.append(["CO-001", "SITE-ENG", "Site Engineer", "Site operations access", "Active"])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def ai_validate_role(
    db, role_id: int | None = None, form: dict | None = None
) -> dict[str, Any]:
    data = dict(form or {})
    if role_id and not form:
        row = get_role_master(db, role_id)
        if row:
            data = dict(row)
    issues: list[str] = []
    suggestions: list[str] = []
    duplicates: list[str] = []
    missing: list[str] = []
    if not int(data.get("company_id") or 0):
        issues.append("Company is required.")
        missing.append("company_id")
    name = (data.get("role_name") or "").strip()
    if not name:
        issues.append("Role name is required.")
        missing.append("role_name")
    else:
        try:
            validate_role_uniqueness(
                db,
                company_id=int(data.get("company_id") or 0) or 1,
                role_code=(data.get("role_code") or name).strip(),
                role_name=name,
                role_id=role_id,
            )
        except ValueError as exc:
            duplicates.append(str(exc))
    if role_id:
        matrix = get_role_permission_matrix(db, role_id)
        assigned = [m for m in matrix if m.get("assigned")]
        if not assigned:
            suggestions.append("Assign at least one permission to this role.")
    result = {
        "ok": not issues and not duplicates,
        "issues": issues,
        "duplicates": duplicates,
        "suggestions": suggestions,
        "missing": missing,
    }
    try:
        from ai_service import chat_completion_json

        prompt = (
            "Review ERP role definition for construction company. "
            f"Role: {json.dumps({k: data.get(k) for k in ('role_code', 'role_name', 'description', 'status')})}. "
            "Return JSON with keys: ok (bool), suggestions (list of strings)."
        )
        ai = chat_completion_json(prompt, fallback={"ok": True, "suggestions": []})
        if isinstance(ai, dict) and ai.get("suggestions"):
            for s in ai["suggestions"]:
                if s and s not in suggestions:
                    suggestions.append(str(s))
    except Exception:
        pass
    result["suggestions"] = suggestions
    result["ok"] = not issues and not duplicates
    return result
