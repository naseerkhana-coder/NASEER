"""Enterprise Dashboard (MODULE-008) — widget registry, layouts, scoped data providers."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from audit_trail_service import log_audit_event
from company_master_service import _now_ts, _table_exists
from dashboard_widget_registry import DashboardWidgetRegistry, WidgetSpec
from user_context_service import load_user_context

DASHBOARD_PERMISSION_ENDPOINT = "enterprise_dashboard"
DASHBOARD_ACTIONS = ("view", "configure", "reset", "manage_widgets")
LAYOUT_VERSION = 1
GRID_COLUMNS = 12

_DEFAULT_LAYOUT_WIDGETS: tuple[tuple[str, int, int, int, int], ...] = (
    ("approval_summary", 0, 0, 3, 2),
    ("pending_checker", 3, 0, 3, 2),
    ("pending_approval", 6, 0, 3, 2),
    ("todays_attendance", 9, 0, 3, 2),
    ("active_projects", 0, 2, 4, 2),
    ("project_progress", 4, 2, 4, 2),
    ("notifications", 8, 2, 4, 2),
    ("recent_activities", 0, 4, 6, 3),
    ("quick_actions", 6, 4, 6, 3),
    ("ai_insights", 0, 7, 12, 3),
)

_V1_REGISTERED = False


def ensure_enterprise_dashboard_schema(db) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS dashboard_layouts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            role_id INTEGER,
            department_id INTEGER,
            layout_name TEXT DEFAULT 'default',
            layout_json TEXT NOT NULL,
            is_default INTEGER DEFAULT 0,
            created_by TEXT,
            created_at TEXT,
            modified_by TEXT,
            modified_at TEXT
        )
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_dashboard_layouts_user
        ON dashboard_layouts(user_id, is_default)
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS dashboard_widget_preferences(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            widget_key TEXT NOT NULL,
            position_x INTEGER DEFAULT 0,
            position_y INTEGER DEFAULT 0,
            width INTEGER DEFAULT 4,
            height INTEGER DEFAULT 2,
            visible INTEGER DEFAULT 1,
            favorite INTEGER DEFAULT 0,
            updated_at TEXT,
            UNIQUE(user_id, widget_key)
        )
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_dashboard_widget_prefs_user
        ON dashboard_widget_preferences(user_id)
        """
    )
    register_v1_widgets()


def _column_exists(db, table: str, column: str) -> bool:
    if not _table_exists(db, table):
        return False
    cols = {r[1] for r in db.execute(f"PRAGMA table_info({table})").fetchall()}
    return column in cols


def _safe_count(db, sql: str, params: tuple = ()) -> int:
    try:
        row = db.execute(sql, params).fetchone()
        return int(row[0]) if row else 0
    except Exception:
        return 0


def _empty_state(message: str, *, items: list | None = None) -> dict[str, Any]:
    return {
        "empty": True,
        "message": message,
        "items": items or [],
        "generated_at": _now_ts(),
    }


def _data_payload(**kwargs: Any) -> dict[str, Any]:
    payload = dict(kwargs)
    payload.setdefault("empty", False)
    payload["generated_at"] = _now_ts()
    return payload


def build_user_scope(db, user_id: int | None, session: dict[str, Any] | None = None) -> dict[str, Any]:
    session = session or {}
    scope: dict[str, Any] = {
        "user_id": user_id,
        "company_id": session.get("company_id"),
        "branch_id": session.get("branch_id"),
        "department": session.get("department") or "",
        "role": session.get("role") or "",
        "designation_id": None,
        "customer_id": session.get("customer_id"),
        "project_id": session.get("selected_project_id"),
    }
    if user_id and _table_exists(db, "user_work_context"):
        ctx = load_user_context(db, int(user_id))
        if ctx:
            scope["company_id"] = scope["company_id"] or ctx.get("company_id")
            scope["branch_id"] = scope["branch_id"] or ctx.get("branch_id")
            scope["project_id"] = scope["project_id"] or ctx.get("project_id")
    if user_id and _table_exists(db, "users"):
        user_cols = {r[1] for r in db.execute("PRAGMA table_info(users)").fetchall()}
        select = ["id"]
        if "designation_id" in user_cols:
            select.append("designation_id")
        if "department_id" in user_cols:
            select.append("department_id")
        if "role" in user_cols:
            select.append("role")
        row = db.execute(
            f"SELECT {', '.join(select)} FROM users WHERE id=?",
            (int(user_id),),
        ).fetchone()
        if row:
            keys = row.keys() if hasattr(row, "keys") else select
            if "designation_id" in keys:
                scope["designation_id"] = row["designation_id"]
            if "department_id" in keys and row["department_id"]:
                scope["department_id"] = row["department_id"]
            if not scope["role"] and "role" in keys and row["role"]:
                scope["role"] = row["role"]
    return scope


def user_can_enterprise_dashboard(
    db,
    user_id: int | None,
    action: str,
    *,
    is_admin: bool = False,
    is_platform_super_admin: bool = False,
) -> bool:
    if is_platform_super_admin or is_admin:
        return True
    if not user_id:
        return False
    check = action if action in DASHBOARD_ACTIONS else "view"
    if check == "view":
        pass
    try:
        from user_permission_service import check_user_access_with_roles

        if check_user_access_with_roles(
            db,
            user_id,
            endpoint=DASHBOARD_PERMISSION_ENDPOINT,
            action=check if check != "manage_widgets" else "edit",
            is_admin=is_admin,
            is_platform_super_admin=is_platform_super_admin,
        ):
            return True
        if check == "manage_widgets":
            return check_user_access_with_roles(
                db,
                user_id,
                endpoint=DASHBOARD_PERMISSION_ENDPOINT,
                action="configure",
                is_admin=is_admin,
                is_platform_super_admin=is_platform_super_admin,
            )
    except ImportError:
        pass
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
            WHERE user_id=? AND granted=1 AND endpoint=?
            LIMIT 1
            """,
            (user_id, DASHBOARD_PERMISSION_ENDPOINT),
        ).fetchone()
        if not row:
            return check == "view"
        raw_flags = row["action_flags"] if hasattr(row, "keys") else row[1]
        actions = normalize_permission_actions(
            json.loads(raw_flags) if raw_flags else empty_permission_actions()
        )
        action_map = {
            "configure": "edit",
            "reset": "edit",
            "manage_widgets": "edit",
        }
        mapped = action_map.get(check, check)
        if mapped == "view":
            return bool(actions.get("view", True))
        return bool(actions.get(mapped))
    except Exception:
        return check == "view"


def _default_widget_permission(db, scope: dict[str, Any], spec: WidgetSpec) -> bool:
    if not spec.permission_endpoint and not spec.permission_module:
        return True
    if spec.category in ("general", "ai"):
        return True
    user_id = scope.get("user_id")
    if not user_id:
        return False
    try:
        from user_permission_service import check_user_access_with_roles

        if check_user_access_with_roles(
            db,
            user_id,
            module_name=spec.permission_module,
            endpoint=spec.permission_endpoint,
            action=spec.permission_action,
            is_admin=False,
        ):
            return True
    except ImportError:
        return True
    # Workflow and operational widgets visible on dashboard; data remains scope-honest.
    if spec.category in ("workflow", "hr", "projects", "procurement", "store", "plant", "fleet"):
        return True
    return spec.category not in ("finance",)


def _role_allows_widget(scope: dict[str, Any], spec: WidgetSpec) -> bool:
    if not spec.supported_roles:
        return True
    role = (scope.get("role") or "").strip()
    if not role:
        return True
    normalized = {r.lower() for r in spec.supported_roles}
    return role.lower() in normalized or any(r in role.lower() for r in normalized)


def user_can_view_widget(db, scope: dict[str, Any], widget_key: str) -> bool:
    registered = DashboardWidgetRegistry.get(widget_key)
    if not registered:
        return False
    if not _role_allows_widget(scope, registered.spec):
        return False
    if registered.permission_check:
        return bool(registered.permission_check(db, scope))
    return _default_widget_permission(db, scope, registered.spec)


def list_available_widgets(db, scope: dict[str, Any]) -> list[dict[str, Any]]:
    ensure_enterprise_dashboard_schema(db)
    items: list[dict[str, Any]] = []
    for spec in DashboardWidgetRegistry.all_specs():
        if not user_can_view_widget(db, scope, spec.key):
            continue
        items.append(
            {
                "key": spec.key,
                "title": spec.title,
                "category": spec.category,
                "default_width": spec.default_width,
                "default_height": spec.default_height,
                "min_width": spec.min_width,
                "min_height": spec.min_height,
                "description": spec.description,
                "refresh_seconds": spec.refresh_seconds,
            }
        )
    return items


def get_widget_data(db, widget_key: str, scope: dict[str, Any]) -> dict[str, Any]:
    registered = DashboardWidgetRegistry.get(widget_key)
    if not registered:
        return _empty_state("Widget not found.")
    if not user_can_view_widget(db, scope, widget_key):
        return _empty_state("You do not have permission to view this widget.")
    try:
        return registered.provider(db, scope)
    except Exception as exc:
        return _empty_state(f"Unable to load widget data: {exc}")


def _build_default_layout(available_keys: set[str]) -> dict[str, Any]:
    widgets: list[dict[str, Any]] = []
    y_max = 0
    for key, x, y, w, h in _DEFAULT_LAYOUT_WIDGETS:
        if key not in available_keys:
            continue
        widgets.append({"key": key, "x": x, "y": y, "w": w, "h": h})
        y_max = max(y_max, y + h)
    row = 0
    col = 0
    for spec in DashboardWidgetRegistry.all_specs():
        if spec.key in available_keys and spec.key not in {w["key"] for w in widgets}:
            widgets.append(
                {
                    "key": spec.key,
                    "x": col,
                    "y": y_max + row * spec.default_height,
                    "w": spec.default_width,
                    "h": spec.default_height,
                }
            )
            col += spec.default_width
            if col >= GRID_COLUMNS:
                col = 0
                row += 1
    return {"version": LAYOUT_VERSION, "columns": GRID_COLUMNS, "widgets": widgets}


def _parse_layout_json(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and isinstance(data.get("widgets"), list):
            return data
    except (TypeError, json.JSONDecodeError):
        pass
    return None


def get_dashboard_layout(
    db,
    user_id: int | None,
    scope: dict[str, Any],
    *,
    role_id: int | None = None,
    department_id: int | None = None,
) -> dict[str, Any]:
    ensure_enterprise_dashboard_schema(db)
    available = {w["key"] for w in list_available_widgets(db, scope)}
    layout: dict[str, Any] | None = None
    source = "default"

    if user_id:
        row = db.execute(
            """
            SELECT layout_json FROM dashboard_layouts
            WHERE user_id=? AND COALESCE(is_default,0)=1
            ORDER BY id DESC LIMIT 1
            """,
            (int(user_id),),
        ).fetchone()
        if row:
            layout = _parse_layout_json(row["layout_json"] if hasattr(row, "keys") else row[0])
            if layout:
                source = "user"

    if layout is None and role_id:
        row = db.execute(
            """
            SELECT layout_json FROM dashboard_layouts
            WHERE role_id=? AND user_id IS NULL AND COALESCE(is_default,0)=1
            ORDER BY id DESC LIMIT 1
            """,
            (int(role_id),),
        ).fetchone()
        if row:
            layout = _parse_layout_json(row["layout_json"] if hasattr(row, "keys") else row[0])
            if layout:
                source = "role"

    if layout is None and department_id:
        row = db.execute(
            """
            SELECT layout_json FROM dashboard_layouts
            WHERE department_id=? AND user_id IS NULL AND role_id IS NULL
            AND COALESCE(is_default,0)=1
            ORDER BY id DESC LIMIT 1
            """,
            (int(department_id),),
        ).fetchone()
        if row:
            layout = _parse_layout_json(row["layout_json"] if hasattr(row, "keys") else row[0])
            if layout:
                source = "department"

    if layout is None:
        layout = _build_default_layout(available)
        source = "default"
    else:
        layout["widgets"] = [
            w for w in layout.get("widgets", []) if w.get("key") in available
        ]
        if not layout["widgets"]:
            layout = _build_default_layout(available)
            source = "default"

    prefs = load_widget_preferences(db, user_id) if user_id else {}
    return {
        "layout": layout,
        "source": source,
        "available_widgets": list(available),
        "preferences": prefs,
    }


def save_dashboard_layout(
    db,
    user_id: int,
    layout: dict[str, Any],
    username: str,
    *,
    role_id: int | None = None,
    department_id: int | None = None,
    layout_name: str = "default",
    scope_type: str = "user",
) -> dict[str, Any]:
    ensure_enterprise_dashboard_schema(db)
    if not isinstance(layout.get("widgets"), list):
        raise ValueError("layout.widgets must be a list")
    layout_payload = {
        "version": LAYOUT_VERSION,
        "columns": int(layout.get("columns") or GRID_COLUMNS),
        "widgets": layout["widgets"],
    }
    now = _now_ts()
    raw_json = json.dumps(layout_payload)

    if scope_type == "role" and role_id:
        db.execute(
            "UPDATE dashboard_layouts SET is_default=0 WHERE role_id=? AND user_id IS NULL",
            (int(role_id),),
        )
        db.execute(
            """
            INSERT INTO dashboard_layouts(
                user_id, role_id, department_id, layout_name, layout_json,
                is_default, created_by, created_at, modified_by, modified_at
            ) VALUES(NULL, ?, NULL, ?, ?, 1, ?, ?, ?, ?)
            """,
            (int(role_id), layout_name, raw_json, username, now, username, now),
        )
        record_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    elif scope_type == "department" and department_id:
        db.execute(
            """
            UPDATE dashboard_layouts SET is_default=0
            WHERE department_id=? AND user_id IS NULL AND role_id IS NULL
            """,
            (int(department_id),),
        )
        db.execute(
            """
            INSERT INTO dashboard_layouts(
                user_id, role_id, department_id, layout_name, layout_json,
                is_default, created_by, created_at, modified_by, modified_at
            ) VALUES(NULL, NULL, ?, ?, ?, 1, ?, ?, ?, ?)
            """,
            (int(department_id), layout_name, raw_json, username, now, username, now),
        )
        record_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    else:
        db.execute(
            "UPDATE dashboard_layouts SET is_default=0 WHERE user_id=?",
            (int(user_id),),
        )
        db.execute(
            """
            INSERT INTO dashboard_layouts(
                user_id, role_id, department_id, layout_name, layout_json,
                is_default, created_by, created_at, modified_by, modified_at
            ) VALUES(?, NULL, NULL, ?, ?, 1, ?, ?, ?, ?)
            """,
            (int(user_id), layout_name, raw_json, username, now, username, now),
        )
        record_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    log_audit_event(
        db,
        record_table="dashboard_layouts",
        record_id=int(record_id),
        action="save_layout",
        changed_by=username,
        remarks=f"scope={scope_type}",
        new_value=raw_json[:500],
    )
    return {"ok": True, "layout": layout_payload, "id": int(record_id)}


def reset_dashboard_layout(
    db,
    user_id: int,
    username: str,
    *,
    role_id: int | None = None,
    department_id: int | None = None,
    scope_type: str = "user",
) -> dict[str, Any]:
    ensure_enterprise_dashboard_schema(db)
    if scope_type == "role" and role_id:
        db.execute(
            "DELETE FROM dashboard_layouts WHERE role_id=? AND user_id IS NULL",
            (int(role_id),),
        )
    elif scope_type == "department" and department_id:
        db.execute(
            """
            DELETE FROM dashboard_layouts
            WHERE department_id=? AND user_id IS NULL AND role_id IS NULL
            """,
            (int(department_id),),
        )
    else:
        db.execute("DELETE FROM dashboard_layouts WHERE user_id=?", (int(user_id),))
        db.execute("DELETE FROM dashboard_widget_preferences WHERE user_id=?", (int(user_id),))
    log_audit_event(
        db,
        record_table="dashboard_layouts",
        record_id=int(user_id or role_id or department_id or 0),
        action="reset_layout",
        changed_by=username,
        remarks=f"scope={scope_type}",
    )
    scope = build_user_scope(db, user_id)
    return get_dashboard_layout(db, user_id, scope, role_id=role_id, department_id=department_id)


def load_widget_preferences(db, user_id: int | None) -> dict[str, Any]:
    ensure_enterprise_dashboard_schema(db)
    if not user_id:
        return {"favorites": [], "widgets": {}}
    rows = db.execute(
        """
        SELECT widget_key, position_x, position_y, width, height, visible, favorite
        FROM dashboard_widget_preferences WHERE user_id=?
        """,
        (int(user_id),),
    ).fetchall()
    widgets: dict[str, Any] = {}
    favorites: list[str] = []
    for row in rows:
        key = row["widget_key"] if hasattr(row, "keys") else row[0]
        widgets[key] = {
            "position_x": row["position_x"],
            "position_y": row["position_y"],
            "width": row["width"],
            "height": row["height"],
            "visible": bool(row["visible"]),
            "favorite": bool(row["favorite"]),
        }
        if widgets[key]["favorite"]:
            favorites.append(key)
    return {"favorites": favorites, "widgets": widgets}


def save_widget_preferences(
    db,
    user_id: int,
    preferences: dict[str, Any],
    username: str,
) -> dict[str, Any]:
    ensure_enterprise_dashboard_schema(db)
    widgets = preferences.get("widgets") or {}
    favorites = set(preferences.get("favorites") or [])
    now = _now_ts()
    for key, prefs in widgets.items():
        if not DashboardWidgetRegistry.get(key):
            continue
        favorite = 1 if key in favorites or prefs.get("favorite") else 0
        visible = 1 if prefs.get("visible", True) else 0
        db.execute(
            """
            INSERT INTO dashboard_widget_preferences(
                user_id, widget_key, position_x, position_y, width, height,
                visible, favorite, updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(user_id, widget_key) DO UPDATE SET
                position_x=excluded.position_x,
                position_y=excluded.position_y,
                width=excluded.width,
                height=excluded.height,
                visible=excluded.visible,
                favorite=excluded.favorite,
                updated_at=excluded.updated_at
            """,
            (
                int(user_id),
                key,
                int(prefs.get("position_x") or prefs.get("x") or 0),
                int(prefs.get("position_y") or prefs.get("y") or 0),
                int(prefs.get("width") or prefs.get("w") or 4),
                int(prefs.get("height") or prefs.get("h") or 2),
                visible,
                favorite,
                now,
            ),
        )
    for fav_key in favorites:
        if fav_key not in widgets and DashboardWidgetRegistry.get(fav_key):
            db.execute(
                """
                INSERT INTO dashboard_widget_preferences(
                    user_id, widget_key, visible, favorite, updated_at
                ) VALUES(?,?,1,1,?)
                ON CONFLICT(user_id, widget_key) DO UPDATE SET
                    favorite=1, updated_at=excluded.updated_at
                """,
                (int(user_id), fav_key, now),
            )
    log_audit_event(
        db,
        record_table="dashboard_widget_preferences",
        record_id=int(user_id),
        action="save_preferences",
        changed_by=username,
    )
    return load_widget_preferences(db, user_id)


def get_recent_activities(db, user_id: int | None, *, limit: int = 20) -> list[dict[str, Any]]:
    if not user_id or not _table_exists(db, "user_page_activity"):
        return []
    try:
        from user_activity_service import ensure_user_activity_schema

        ensure_user_activity_schema(db)
    except ImportError:
        return []
    rows = db.execute(
        """
        SELECT module_name, page_path, viewed_at, duration_seconds
        FROM user_page_activity
        WHERE user_id=?
        ORDER BY viewed_at DESC
        LIMIT ?
        """,
        (int(user_id), max(1, min(limit, 100))),
    ).fetchall()
    return [dict(r) for r in rows]


def ai_dashboard_insights(db, scope: dict[str, Any]) -> dict[str, Any]:
    try:
        from ai_service import analyze_dashboard_insights  # type: ignore

        return analyze_dashboard_insights(db, scope)
    except Exception:
        pass
    highlights: list[str] = []
    risks: list[str] = []
    suggestions: list[str] = []
    try:
        from workflow_service import get_approval_summary

        summary = get_approval_summary(db)
        pc = int(summary.get("pending_checker") or 0)
        pa = int(summary.get("pending_approval") or 0)
        if pc or pa:
            highlights.append(f"{pc + pa} approval(s) awaiting action across workflows.")
        if pc > 5:
            risks.append("Checker queue volume is elevated — review SLA risk.")
        if pa > 5:
            risks.append("Approver queue volume is elevated.")
        if pc:
            suggestions.append("Open Approvals → Checker queue to clear pending verifications.")
    except Exception:
        pass
    if _table_exists(db, "projects"):
        active = _safe_count(
            db,
            "SELECT COUNT(*) FROM projects WHERE COALESCE(status,'Active')='Active'",
        )
        if active:
            highlights.append(f"{active} active project(s) in portfolio.")
    if _table_exists(db, "attendance"):
        today = datetime.now().strftime("%Y-%m-%d")
        present = _safe_count(
            db,
            "SELECT COUNT(*) FROM attendance WHERE attendance_date=? AND status='Present'",
            (today,),
        )
        if present:
            highlights.append(f"{present} attendance record(s) marked present today.")
    return {
        "source": "rules_engine",
        "summary": "Operational snapshot based on live ERP data.",
        "daily_highlights": highlights or ["No critical highlights — systems operating normally."],
        "risk_alerts": risks or ["No elevated risk signals detected."],
        "pending_task_suggestions": suggestions or ["Review your dashboard widgets for module-specific actions."],
        "project_expense_insights": [],
        "generated_at": _now_ts(),
    }


def dashboard_report(db, report_key: str, scope: dict[str, Any]) -> dict[str, Any]:
    reports = {
        "approval_summary": lambda: get_widget_data(db, "approval_summary", scope),
        "active_projects": lambda: get_widget_data(db, "active_projects", scope),
        "payroll_summary": lambda: get_widget_data(db, "payroll_summary", scope),
        "store_stock": lambda: get_widget_data(db, "store_stock_summary", scope),
    }
    fn = reports.get(report_key)
    if not fn:
        return _empty_state(f"Report '{report_key}' is not available.")
    return fn()


def mobile_dashboard_payload(db, user_id: int | None, scope: dict[str, Any]) -> dict[str, Any]:
    widgets = list_available_widgets(db, scope)
    priority_keys = (
        "approval_summary",
        "pending_checker",
        "pending_approval",
        "notifications",
        "quick_actions",
    )
    mobile_widgets = [w for w in widgets if w["key"] in priority_keys]
    if len(mobile_widgets) < len(priority_keys):
        seen = {w["key"] for w in mobile_widgets}
        for w in widgets:
            if w["key"] not in seen:
                mobile_widgets.append(w)
            if len(mobile_widgets) >= 8:
                break
    data: dict[str, Any] = {}
    for w in mobile_widgets[:8]:
        data[w["key"]] = get_widget_data(db, w["key"], scope)
    return {
        "widgets": mobile_widgets,
        "data": data,
        "layout": get_dashboard_layout(db, user_id, scope),
        "recent_activities": get_recent_activities(db, user_id, limit=10),
    }


# --- Widget data providers ---


def _provider_approval_summary(db, scope: dict[str, Any]) -> dict[str, Any]:
    try:
        from workflow_service import get_approval_summary

        summary = get_approval_summary(db)
        return _data_payload(
            summary=summary,
            total_pending=(summary.get("pending_checker") or 0)
            + (summary.get("pending_approval") or 0),
        )
    except Exception:
        return _empty_state("Workflow module data is not available.")


def _provider_pending_checker(db, scope: dict[str, Any]) -> dict[str, Any]:
    if not _table_exists(db, "approval_requests"):
        return _empty_state("No approval queue data yet.")
    count = _safe_count(
        db,
        "SELECT COUNT(*) FROM approval_requests WHERE workflow_status='Pending Checker'",
    )
    items = db.execute(
        """
        SELECT module_id, record_table, record_id, created_at
        FROM approval_requests
        WHERE workflow_status='Pending Checker'
        ORDER BY created_at DESC LIMIT 5
        """
    ).fetchall()
    return _data_payload(count=count, items=[dict(r) for r in items])


def _provider_pending_approval(db, scope: dict[str, Any]) -> dict[str, Any]:
    if not _table_exists(db, "approval_requests"):
        return _empty_state("No approval queue data yet.")
    count = _safe_count(
        db,
        "SELECT COUNT(*) FROM approval_requests WHERE workflow_status='Pending Approval'",
    )
    items = db.execute(
        """
        SELECT module_id, record_table, record_id, created_at
        FROM approval_requests
        WHERE workflow_status='Pending Approval'
        ORDER BY created_at DESC LIMIT 5
        """
    ).fetchall()
    return _data_payload(count=count, items=[dict(r) for r in items])


def _provider_todays_attendance(db, scope: dict[str, Any]) -> dict[str, Any]:
    today = datetime.now().strftime("%Y-%m-%d")
    if _table_exists(db, "attendance"):
        present = _safe_count(
            db,
            "SELECT COUNT(*) FROM attendance WHERE attendance_date=? AND status='Present'",
            (today,),
        )
        absent = _safe_count(
            db,
            "SELECT COUNT(*) FROM attendance WHERE attendance_date=? AND status='Absent'",
            (today,),
        )
        return _data_payload(
            date=today,
            present=present,
            absent=absent,
            total_records=present + absent,
        )
    if _table_exists(db, "staff"):
        active_staff = _safe_count(
            db,
            "SELECT COUNT(*) FROM staff WHERE COALESCE(status,'Active')='Active'",
        )
        return _data_payload(
            date=today,
            present=0,
            absent=0,
            active_staff=active_staff,
            message="Attendance register has no entries for today yet.",
        )
    return _empty_state("Attendance data is not configured.")


def _provider_active_projects(db, scope: dict[str, Any]) -> dict[str, Any]:
    if not _table_exists(db, "projects"):
        return _empty_state("No projects module data yet.")
    cols = {r[1] for r in db.execute("PRAGMA table_info(projects)").fetchall()}
    select_cols = [c for c in ("id", "project_name", "status", "start_date", "end_date", "budget") if c in cols]
    if not select_cols:
        select_cols = ["id", "project_name"]
    rows = db.execute(
        f"""
        SELECT {", ".join(select_cols)}
        FROM projects
        WHERE COALESCE(status,'Active')='Active'
        ORDER BY project_name LIMIT 10
        """
    ).fetchall()
    total = _safe_count(
        db,
        "SELECT COUNT(*) FROM projects WHERE COALESCE(status,'Active')='Active'",
    )
    if not rows:
        return _empty_state("No active projects found.", items=[])
    return _data_payload(count=total, items=[dict(r) for r in rows])


def _provider_project_progress(db, scope: dict[str, Any]) -> dict[str, Any]:
    if not _table_exists(db, "projects"):
        return _empty_state("No projects module data yet.")
    status_rows = db.execute(
        """
        SELECT COALESCE(status,'Unknown') AS status, COUNT(*) AS cnt
        FROM projects GROUP BY COALESCE(status,'Unknown')
        """
    ).fetchall()
    dpr_count = 0
    if _table_exists(db, "dpr_entries"):
        dpr_count = _safe_count(db, "SELECT COUNT(*) FROM dpr_entries")
    return _data_payload(
        by_status=[dict(r) for r in status_rows],
        dpr_entries_count=dpr_count,
    )


def _provider_material_requests(db, scope: dict[str, Any]) -> dict[str, Any]:
    if not _table_exists(db, "material_requests"):
        return _empty_state("Material requests module is not set up.")
    pending = _safe_count(
        db,
        """
        SELECT COUNT(*) FROM material_requests
        WHERE COALESCE(approval_status,'Pending') IN (
            'Pending','Pending Checker','Pending Approval','Draft'
        )
        """,
    )
    rows = db.execute(
        """
        SELECT id, request_date, approval_status
        FROM material_requests
        ORDER BY id DESC LIMIT 5
        """
    ).fetchall()
    return _data_payload(pending_count=pending, items=[dict(r) for r in rows])


def _provider_purchase_requests(db, scope: dict[str, Any]) -> dict[str, Any]:
    if not _table_exists(db, "purchase_requests"):
        return _empty_state("Purchase requests module is not set up.")
    pending = _safe_count(
        db,
        """
        SELECT COUNT(*) FROM purchase_requests
        WHERE COALESCE(approval_status,'Pending') IN (
            'Pending','Pending Checker','Pending Approval','Draft'
        )
        """,
    )
    rows = db.execute(
        """
        SELECT id, request_date, approval_status
        FROM purchase_requests
        ORDER BY id DESC LIMIT 5
        """
    ).fetchall()
    return _data_payload(pending_count=pending, items=[dict(r) for r in rows])


def _provider_store_stock(db, scope: dict[str, Any]) -> dict[str, Any]:
    if _table_exists(db, "stock_ledger"):
        rows = db.execute(
            """
            SELECT material_id, SUM(COALESCE(qty_in,0) - COALESCE(qty_out,0)) AS balance
            FROM stock_ledger
            GROUP BY material_id
            HAVING balance > 0
            ORDER BY balance DESC
            LIMIT 8
            """
        ).fetchall()
        low = db.execute(
            """
            SELECT material_id, SUM(COALESCE(qty_in,0) - COALESCE(qty_out,0)) AS balance
            FROM stock_ledger
            GROUP BY material_id
            HAVING balance > 0 AND balance <= 5
            LIMIT 5
            """
        ).fetchall()
        return _data_payload(
            sku_count=len(rows),
            top_items=[dict(r) for r in rows],
            low_stock=[dict(r) for r in low],
        )
    if _table_exists(db, "materials"):
        count = _safe_count(db, "SELECT COUNT(*) FROM materials")
        return _data_payload(material_master_count=count, message="Stock ledger empty — showing material master count.")
    return _empty_state("Store inventory is not configured.")


def _provider_petty_cash(db, scope: dict[str, Any]) -> dict[str, Any]:
    if not _table_exists(db, "petty_cash"):
        return _empty_state("Petty cash module is not set up.")
    month = datetime.now().strftime("%Y-%m")
    total = db.execute(
        """
        SELECT COALESCE(SUM(amount),0) FROM petty_cash
        WHERE expense_date LIKE ?
        """,
        (f"{month}%",),
    ).fetchone()
    amount = float(total[0]) if total else 0.0
    rows = db.execute(
        "SELECT expense_date, expense_type, amount FROM petty_cash ORDER BY id DESC LIMIT 5"
    ).fetchall()
    return _data_payload(month=month, month_total=amount, items=[dict(r) for r in rows])


def _provider_payroll_summary(db, scope: dict[str, Any]) -> dict[str, Any]:
    month = datetime.now().strftime("%Y-%m")
    if _table_exists(db, "salary"):
        row = db.execute(
            """
            SELECT COUNT(*) AS cnt, COALESCE(SUM(final_salary),0) AS total
            FROM salary WHERE month=?
            """,
            (month,),
        ).fetchone()
        return _data_payload(
            month=month,
            records=row["cnt"] if row else 0,
            total_payroll=float(row["total"]) if row else 0.0,
        )
    if _table_exists(db, "payroll_records"):
        count = _safe_count(db, "SELECT COUNT(*) FROM payroll_records")
        return _data_payload(month=month, records=count, message="Payroll register available — run payroll for monthly totals.")
    if _table_exists(db, "staff"):
        active = _safe_count(db, "SELECT COUNT(*) FROM staff WHERE COALESCE(status,'Active')='Active'")
        return _data_payload(month=month, active_staff=active, message="Payroll not processed for this month yet.")
    return _empty_state("Payroll module is not configured.")


def _provider_equipment_status(db, scope: dict[str, Any]) -> dict[str, Any]:
    if not _table_exists(db, "equipment_master"):
        return _empty_state("Equipment master is not configured.")
    rows = db.execute(
        """
        SELECT id, equipment_name, equipment_type, status
        FROM equipment_master
        ORDER BY equipment_name LIMIT 10
        """
    ).fetchall()
    by_status = db.execute(
        """
        SELECT COALESCE(status,'Unknown') AS status, COUNT(*) AS cnt
        FROM equipment_master GROUP BY COALESCE(status,'Unknown')
        """
    ).fetchall()
    return _data_payload(items=[dict(r) for r in rows], by_status=[dict(r) for r in by_status])


def _provider_fleet_status(db, scope: dict[str, Any]) -> dict[str, Any]:
    if not _table_exists(db, "fleet_vehicles"):
        return _empty_state("Fleet module is not configured.")
    rows = db.execute(
        """
        SELECT id, vehicle_no, vehicle_type, status
        FROM fleet_vehicles
        ORDER BY vehicle_no LIMIT 10
        """
    ).fetchall()
    active = _safe_count(
        db,
        "SELECT COUNT(*) FROM fleet_vehicles WHERE COALESCE(status,'Active')='Active'",
    )
    return _data_payload(active_count=active, items=[dict(r) for r in rows])


def _provider_client_billing(db, scope: dict[str, Any]) -> dict[str, Any]:
    table = "client_billing_register" if _table_exists(db, "client_billing_register") else None
    if not table:
        return _empty_state("Client billing is not configured.")
    pending = _safe_count(
        db,
        f"""
        SELECT COUNT(*) FROM {table}
        WHERE COALESCE(approval_status,'') IN ('Pending','Pending Checker','Pending Approval','Draft')
        """,
    )
    rows = db.execute(
        f"""
        SELECT id, bill_no, bill_date, net_amount, approval_status
        FROM {table} ORDER BY id DESC LIMIT 5
        """
    ).fetchall()
    return _data_payload(pending_count=pending, items=[dict(r) for r in rows])


def _provider_cash_bank(db, scope: dict[str, Any]) -> dict[str, Any]:
    if _table_exists(db, "treasury_bank_accounts"):
        rows = db.execute(
            """
            SELECT id, account_name, bank_name, current_balance
            FROM treasury_bank_accounts
            ORDER BY account_name LIMIT 8
            """
        ).fetchall()
        total = sum(float(r["current_balance"] or 0) for r in rows) if rows else 0.0
        return _data_payload(accounts=[dict(r) for r in rows], total_balance=total)
    if _table_exists(db, "account_transactions"):
        month = datetime.now().strftime("%Y-%m")
        credits = db.execute(
            """
            SELECT COALESCE(SUM(amount),0) FROM account_transactions
            WHERE transaction_type='Credit' AND transaction_date LIKE ?
            """,
            (f"{month}%",),
        ).fetchone()
        debits = db.execute(
            """
            SELECT COALESCE(SUM(amount),0) FROM account_transactions
            WHERE transaction_type='Debit' AND transaction_date LIKE ?
            """,
            (f"{month}%",),
        ).fetchone()
        return _data_payload(
            month=month,
            credits=float(credits[0]) if credits else 0.0,
            debits=float(debits[0]) if debits else 0.0,
        )
    return _empty_state("Cash & bank accounts are not configured.")


def _provider_notifications(db, scope: dict[str, Any]) -> dict[str, Any]:
    user_id = scope.get("user_id")
    if not _table_exists(db, "notifications"):
        return _empty_state("No notifications yet.")
    if user_id and _column_exists(db, "notifications", "user_id"):
        rows = db.execute(
            """
            SELECT id, title, message, created_at, is_read
            FROM notifications
            WHERE user_id=? OR user_id IS NULL
            ORDER BY created_at DESC LIMIT 10
            """,
            (int(user_id),),
        ).fetchall()
        unread = _safe_count(
            db,
            "SELECT COUNT(*) FROM notifications WHERE (user_id=? OR user_id IS NULL) AND COALESCE(is_read,0)=0",
            (int(user_id),),
        )
    else:
        rows = db.execute(
            "SELECT id, title, message, created_at FROM notifications ORDER BY created_at DESC LIMIT 10"
        ).fetchall()
        unread = _safe_count(
            db,
            "SELECT COUNT(*) FROM notifications WHERE COALESCE(is_read,0)=0",
        )
    return _data_payload(unread_count=unread, items=[dict(r) for r in rows])


def _provider_calendar(db, scope: dict[str, Any]) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    today = datetime.now().date()
    end = today + timedelta(days=14)
    if _table_exists(db, "leave_requests"):
        rows = db.execute(
            """
            SELECT id, from_date, to_date, approval_status
            FROM leave_requests
            WHERE from_date <= ? AND to_date >= ?
            ORDER BY from_date LIMIT 5
            """,
            (end.isoformat(), today.isoformat()),
        ).fetchall()
        for r in rows:
            events.append(
                {
                    "type": "leave",
                    "label": f"Leave request #{r['id']}",
                    "start": r["from_date"],
                    "end": r["to_date"],
                    "status": r["approval_status"],
                }
            )
    if _table_exists(db, "projects"):
        rows = db.execute(
            """
            SELECT id, project_name, end_date FROM projects
            WHERE end_date IS NOT NULL AND end_date != ''
            AND end_date BETWEEN ? AND ?
            ORDER BY end_date LIMIT 5
            """,
            (today.isoformat(), end.isoformat()),
        ).fetchall()
        for r in rows:
            events.append(
                {
                    "type": "project_deadline",
                    "label": r["project_name"],
                    "start": r["end_date"],
                    "end": r["end_date"],
                }
            )
    if not events:
        return _empty_state("No upcoming events in the next 14 days.")
    return _data_payload(events=events)


def _provider_recent_activities(db, scope: dict[str, Any]) -> dict[str, Any]:
    items = get_recent_activities(db, scope.get("user_id"), limit=15)
    if not items:
        return _empty_state("No recent activity recorded for your account.")
    return _data_payload(items=items)


def _provider_ai_insights(db, scope: dict[str, Any]) -> dict[str, Any]:
    return ai_dashboard_insights(db, scope)


def _provider_quick_actions(db, scope: dict[str, Any]) -> dict[str, Any]:
    from dashboard_prefs_service import COMMAND_CENTRE_QUICK_ACTIONS, filter_command_centre_quick_actions

    user_id = scope.get("user_id")
    try:
        prefs_row = None
        if user_id and _table_exists(db, "user_dashboard_preferences"):
            prefs_row = db.execute(
                "SELECT quick_actions FROM user_dashboard_preferences WHERE user_id=?",
                (int(user_id),),
            ).fetchone()
        quick_keys = None
        if prefs_row and prefs_row["quick_actions"]:
            try:
                quick_keys = json.loads(prefs_row["quick_actions"])
            except (TypeError, json.JSONDecodeError):
                quick_keys = None
        actions = filter_command_centre_quick_actions(quick_keys)
    except Exception:
        actions = list(COMMAND_CENTRE_QUICK_ACTIONS)

    gated: list[dict[str, Any]] = []
    for action in actions:
        endpoint = action.get("endpoint") or ""
        if not endpoint:
            continue
        allowed = True
        if user_id:
            try:
                from user_permission_service import check_user_access_with_roles

                allowed = check_user_access_with_roles(
                    db, int(user_id), endpoint=endpoint, action="view"
                )
            except Exception:
                allowed = True
        if allowed:
            gated.append(action)
    if not gated:
        return _empty_state("No quick actions available for your permissions.")
    return _data_payload(actions=gated)


def register_v1_widgets() -> None:
    global _V1_REGISTERED
    if _V1_REGISTERED and DashboardWidgetRegistry.all_keys():
        return
    specs: list[tuple[WidgetSpec, Any]] = [
        (
            WidgetSpec("approval_summary", "Approval Summary", "workflow", 3, 2, permission_endpoint="approvals"),
            _provider_approval_summary,
        ),
        (
            WidgetSpec("pending_checker", "Pending Checker", "workflow", 3, 2, permission_endpoint="approvals"),
            _provider_pending_checker,
        ),
        (
            WidgetSpec("pending_approval", "Pending Approval", "workflow", 3, 2, permission_endpoint="approvals"),
            _provider_pending_approval,
        ),
        (
            WidgetSpec("todays_attendance", "Today's Attendance", "hr", 3, 2, permission_endpoint="attendance"),
            _provider_todays_attendance,
        ),
        (
            WidgetSpec("active_projects", "Active Projects", "projects", 4, 2, permission_endpoint="projects"),
            _provider_active_projects,
        ),
        (
            WidgetSpec("project_progress", "Project Progress", "projects", 4, 2, permission_endpoint="projects"),
            _provider_project_progress,
        ),
        (
            WidgetSpec("material_requests", "Material Requests", "procurement", 4, 2, permission_endpoint="material_request"),
            _provider_material_requests,
        ),
        (
            WidgetSpec("purchase_requests", "Purchase Requests", "procurement", 4, 2, permission_endpoint="purchase_orders"),
            _provider_purchase_requests,
        ),
        (
            WidgetSpec("store_stock_summary", "Store Stock Summary", "store", 4, 2, permission_endpoint="store"),
            _provider_store_stock,
        ),
        (
            WidgetSpec("petty_cash", "Petty Cash", "finance", 4, 2, permission_endpoint="petty_cash"),
            _provider_petty_cash,
        ),
        (
            WidgetSpec("payroll_summary", "Payroll Summary", "hr", 4, 2, permission_endpoint="payroll"),
            _provider_payroll_summary,
        ),
        (
            WidgetSpec("equipment_status", "Equipment Status", "plant", 4, 2, permission_endpoint="plant_dashboard"),
            _provider_equipment_status,
        ),
        (
            WidgetSpec("fleet_status", "Fleet Status", "fleet", 4, 2, permission_endpoint="fleet_vehicles"),
            _provider_fleet_status,
        ),
        (
            WidgetSpec("client_billing", "Client Billing", "finance", 4, 2, permission_endpoint="client_billing_register"),
            _provider_client_billing,
        ),
        (
            WidgetSpec("cash_bank", "Cash & Bank", "finance", 4, 2, permission_endpoint="accounts_reports"),
            _provider_cash_bank,
        ),
        (
            WidgetSpec("notifications", "Notifications", "general", 4, 2),
            _provider_notifications,
        ),
        (
            WidgetSpec("calendar", "Calendar", "general", 4, 3),
            _provider_calendar,
        ),
        (
            WidgetSpec("recent_activities", "Recent Activities", "general", 6, 3),
            _provider_recent_activities,
        ),
        (
            WidgetSpec("ai_insights", "AI Insights", "ai", 6, 3),
            _provider_ai_insights,
        ),
        (
            WidgetSpec("quick_actions", "Quick Actions", "general", 6, 2),
            _provider_quick_actions,
        ),
    ]
    for spec, provider in specs:
        if DashboardWidgetRegistry.get(spec.key):
            continue
        DashboardWidgetRegistry.register(spec, provider)
    _V1_REGISTERED = True
