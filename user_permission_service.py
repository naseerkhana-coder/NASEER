"""Department-scoped tab/module permissions for MAXEK ERP users."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable

from ui_shell_config import MAIN_DASHBOARD_DEPARTMENT_SLUGS

# Department portals used in Settings > Users permission assignment (slug, label).
PERMISSION_DEPARTMENT_CHOICES: list[tuple[str, str]] = [
    ("accounts", "Accounts"),
    ("projects", "Projects"),
    ("store", "Store"),
    ("procurement", "Procurement"),
    ("hr-payroll", "HR & Payroll"),
    ("vehicle", "Vehicle & Fleet"),
    ("plant-machinery", "Plant & Machinery"),
    ("plant-operations", "Plant Operations"),
    ("asphalt-plant", "Asphalt Plant"),
    ("concrete-plant", "Concrete Plant"),
    ("precast-yard", "Precast Yard"),
    ("mechanical", "Mechanical"),
    ("engineering", "Engineering & Planning"),
    ("subcontract", "Subcontractor"),
    ("qc", "Quality Control"),
    ("administration", "Administration & Compliance"),
    ("tender", "Tender"),
    ("reports", "Reports"),
    ("consultancy", "Consultancy"),
]

# Main Command Centre departments — primary permission assignment UI (Step 1).
MAIN_PERMISSION_DEPARTMENT_CHOICES: list[tuple[str, str]] = list(MAIN_DASHBOARD_DEPARTMENT_SLUGS)

PERMISSION_ACTION_KEYS: tuple[str, ...] = (
    "view",
    "create",
    "edit",
    "delete",
    "approve",
    "print",
    "export",
)

PERMISSION_ACTION_LABELS: dict[str, str] = {
    "view": "View",
    "create": "Create",
    "edit": "Edit",
    "delete": "Delete",
    "approve": "Approve",
    "print": "Print",
    "export": "Export",
}


def empty_permission_actions() -> dict[str, bool]:
    return {key: False for key in PERMISSION_ACTION_KEYS}


def full_permission_actions() -> dict[str, bool]:
    return {key: True for key in PERMISSION_ACTION_KEYS}


def view_only_permission_actions() -> dict[str, bool]:
    actions = empty_permission_actions()
    actions["view"] = True
    return actions


def normalize_permission_actions(raw: Any) -> dict[str, bool]:
    """Coerce stored/UI action map to canonical booleans."""
    base = empty_permission_actions()
    if not isinstance(raw, dict):
        return base
    for key in PERMISSION_ACTION_KEYS:
        base[key] = bool(raw.get(key))
    return base


def actions_grant_tab_access(actions: dict[str, bool]) -> bool:
    """Tab appears in menus when View is granted (security model unchanged)."""
    return bool(actions.get("view"))


# Predefined role templates — UI presets only; persisted rows still use user_tab_permissions.
PERMISSION_ROLE_TEMPLATES: dict[str, dict[str, Any]] = {
    "project_manager": {
        "label": "Project Manager",
        "departments": ["projects", "planning-wbs", "boq", "dpr", "procurement", "reports"],
        "actions": full_permission_actions(),
    },
    "site_engineer": {
        "label": "Site Engineer",
        "departments": ["projects", "dpr", "boq"],
        "actions": {
            "view": True,
            "create": True,
            "edit": True,
            "delete": False,
            "approve": False,
            "print": True,
            "export": True,
        },
    },
    "store_keeper": {
        "label": "Store Keeper",
        "departments": ["store", "procurement"],
        "actions": {
            "view": True,
            "create": True,
            "edit": True,
            "delete": False,
            "approve": False,
            "print": True,
            "export": True,
        },
    },
    "accountant": {
        "label": "Accountant",
        "departments": ["accounts", "reports"],
        "actions": {
            "view": True,
            "create": True,
            "edit": True,
            "delete": False,
            "approve": True,
            "print": True,
            "export": True,
        },
    },
    "hr_officer": {
        "label": "HR Officer",
        "departments": ["hr-payroll", "reports"],
        "actions": {
            "view": True,
            "create": True,
            "edit": True,
            "delete": False,
            "approve": True,
            "print": True,
            "export": True,
        },
    },
    "procurement_officer": {
        "label": "Procurement Officer",
        "departments": ["procurement", "store"],
        "actions": {
            "view": True,
            "create": True,
            "edit": True,
            "delete": False,
            "approve": True,
            "print": True,
            "export": True,
        },
    },
    "qa_engineer": {
        "label": "QA Engineer",
        "departments": ["qc", "reports"],
        "actions": {
            "view": True,
            "create": True,
            "edit": True,
            "delete": False,
            "approve": True,
            "print": True,
            "export": True,
        },
    },
    "plant_manager": {
        "label": "Plant Manager",
        "departments": ["plant-operations", "qc", "reports"],
        "actions": full_permission_actions(),
    },
}


def list_permission_role_templates() -> list[dict[str, Any]]:
    return [
        {"id": template_id, "label": spec["label"]}
        for template_id, spec in PERMISSION_ROLE_TEMPLATES.items()
    ]


def get_permission_role_template(template_id: str) -> dict[str, Any] | None:
    spec = PERMISSION_ROLE_TEMPLATES.get(template_id)
    if not spec:
        return None
    return {
        "id": template_id,
        "label": spec["label"],
        "departments": list(spec.get("departments") or []),
        "actions": normalize_permission_actions(spec.get("actions")),
    }


def get_main_permission_department_slugs() -> set[str]:
    return {slug for slug, _ in MAIN_PERMISSION_DEPARTMENT_CHOICES}


def tab_key_for_item(item: dict[str, Any]) -> str:
    """Stable key for a portal/nav menu item."""
    endpoint = (item.get("endpoint") or "").strip()
    anchor = (item.get("anchor") or "").strip()
    label = (item.get("label") or "").strip()
    if anchor:
        return f"{endpoint}#{anchor}"
    if label:
        return f"{endpoint}::{label}"
    return endpoint


def _dedupe_tabs(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    tabs: list[dict[str, Any]] = []
    for raw in items:
        if not raw.get("endpoint"):
            continue
        key = tab_key_for_item(raw)
        if key in seen:
            continue
        seen.add(key)
        tabs.append(
            {
                "tab_key": key,
                "endpoint": raw.get("endpoint", ""),
                "label": raw.get("label", key),
                "icon": raw.get("icon", "fa-folder"),
                "active_endpoints": list(raw.get("active_endpoints") or [raw.get("endpoint")]),
            }
        )
    return tabs


def build_department_tab_catalog(
    department_slug: str,
    *,
    portal: dict[str, Any] | None,
    nav_group: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Tabs/modules assignable for a department — portal menu only (never NAV_GROUPS)."""
    _ = department_slug
    _ = nav_group
    items: list[dict[str, Any]] = []
    if portal:
        items.extend(portal.get("menu") or [])
        items.extend(portal.get("quick_tabs") or [])
    return _dedupe_tabs(items)


def ensure_user_tab_permissions_schema(db) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS user_tab_permissions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            department_slug TEXT NOT NULL,
            tab_key TEXT NOT NULL,
            endpoint TEXT,
            label TEXT,
            granted INTEGER NOT NULL DEFAULT 1,
            action_flags TEXT,
            updated_at TEXT,
            UNIQUE(user_id, department_slug, tab_key),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_tab_perm_user "
        "ON user_tab_permissions(user_id, department_slug)"
    )
    _ensure_action_flags_column(db)


def _ensure_action_flags_column(db) -> None:
    cols = {row[1] for row in db.execute("PRAGMA table_info(user_tab_permissions)").fetchall()}
    if "action_flags" not in cols:
        db.execute("ALTER TABLE user_tab_permissions ADD COLUMN action_flags TEXT")


def _parse_action_flags(raw: Any, *, granted: bool) -> dict[str, bool]:
    if raw:
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            return normalize_permission_actions(parsed)
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    if granted:
        return view_only_permission_actions()
    return empty_permission_actions()


def _serialize_action_flags(actions: dict[str, bool]) -> str:
    return json.dumps(normalize_permission_actions(actions), sort_keys=True)


def get_user_configured_permission_departments(db, user_id: int) -> list[str]:
    ensure_user_tab_permissions_schema(db)
    rows = db.execute(
        """
        SELECT DISTINCT department_slug FROM user_tab_permissions
        WHERE user_id=?
        ORDER BY department_slug
        """,
        (user_id,),
    ).fetchall()
    return [row["department_slug"] for row in rows]


def user_has_tab_restrictions(db, user_id: int) -> bool:
    ensure_user_tab_permissions_schema(db)
    row = db.execute(
        "SELECT 1 FROM user_tab_permissions WHERE user_id=? AND granted=1 LIMIT 1",
        (user_id,),
    ).fetchone()
    return row is not None


def get_granted_tab_keys_for_department(db, user_id: int, department_slug: str) -> set[str]:
    ensure_user_tab_permissions_schema(db)
    rows = db.execute(
        """
        SELECT tab_key FROM user_tab_permissions
        WHERE user_id=? AND department_slug=? AND granted=1
        """,
        (user_id, department_slug),
    ).fetchall()
    return {row["tab_key"] for row in rows}


def get_user_tab_action_map_for_department(
    db, user_id: int, department_slug: str
) -> dict[str, dict[str, bool]]:
    """Return tab_key -> action flags for a department (UI restore only)."""
    ensure_user_tab_permissions_schema(db)
    rows = db.execute(
        """
        SELECT tab_key, granted, action_flags FROM user_tab_permissions
        WHERE user_id=? AND department_slug=?
        """,
        (user_id, department_slug),
    ).fetchall()
    result: dict[str, dict[str, bool]] = {}
    for row in rows:
        granted = bool(row["granted"])
        result[row["tab_key"]] = _parse_action_flags(row["action_flags"], granted=granted)
    return result


def get_granted_endpoints_for_user(db, user_id: int) -> set[str]:
    ensure_user_tab_permissions_schema(db)
    rows = db.execute(
        """
        SELECT endpoint FROM user_tab_permissions
        WHERE user_id=? AND granted=1 AND endpoint IS NOT NULL AND TRIM(endpoint)!=''
        """,
        (user_id,),
    ).fetchall()
    return {(row["endpoint"] or "").strip() for row in rows if row["endpoint"]}


def get_user_department_tab_state(
    db,
    user_id: int,
    department_slug: str,
    catalog: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return catalog tabs with granted flag and action matrix for UI."""
    granted = get_granted_tab_keys_for_department(db, user_id, department_slug)
    action_map = get_user_tab_action_map_for_department(db, user_id, department_slug)
    has_dept_rows = bool(
        db.execute(
            "SELECT 1 FROM user_tab_permissions WHERE user_id=? AND department_slug=? LIMIT 1",
            (user_id, department_slug),
        ).fetchone()
    )
    result: list[dict[str, Any]] = []
    for tab in catalog:
        entry = dict(tab)
        if not has_dept_rows:
            entry["granted"] = True
            entry["actions"] = full_permission_actions()
        else:
            tab_granted = tab["tab_key"] in granted
            entry["granted"] = tab_granted
            entry["actions"] = action_map.get(
                tab["tab_key"],
                view_only_permission_actions() if tab_granted else empty_permission_actions(),
            )
        result.append(entry)
    return result


def save_user_department_tab_permissions(
    db,
    user_id: int,
    department_slug: str,
    granted_tab_keys: list[str],
    catalog: list[dict[str, Any]],
    *,
    tab_actions: dict[str, dict[str, bool]] | None = None,
) -> None:
    ensure_user_tab_permissions_schema(db)
    catalog_by_key = {tab["tab_key"]: tab for tab in catalog}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "DELETE FROM user_tab_permissions WHERE user_id=? AND department_slug=?",
        (user_id, department_slug),
    )
    for tab_key in granted_tab_keys:
        tab = catalog_by_key.get(tab_key)
        if not tab:
            continue
        actions = normalize_permission_actions((tab_actions or {}).get(tab_key))
        if not actions_grant_tab_access(actions):
            continue
        db.execute(
            """
            INSERT INTO user_tab_permissions(
                user_id, department_slug, tab_key, endpoint, label, granted, action_flags, updated_at
            ) VALUES(?,?,?,?,?,1,?,?)
            """,
            (
                user_id,
                department_slug,
                tab_key,
                tab.get("endpoint"),
                tab.get("label"),
                _serialize_action_flags(actions),
                now,
            ),
        )


def save_user_department_tab_entries(
    db,
    user_id: int,
    department_slug: str,
    entries: list[dict[str, Any]],
    catalog: list[dict[str, Any]],
) -> int:
    """Save permission matrix entries; returns count of granted tabs."""
    granted_keys: list[str] = []
    tab_actions: dict[str, dict[str, bool]] = {}
    for entry in entries:
        tab_key = str(entry.get("tab_key") or "").strip()
        if not tab_key:
            continue
        actions = normalize_permission_actions(entry.get("actions"))
        if actions_grant_tab_access(actions):
            granted_keys.append(tab_key)
            tab_actions[tab_key] = actions
    save_user_department_tab_permissions(
        db,
        user_id,
        department_slug,
        granted_keys,
        catalog,
        tab_actions=tab_actions,
    )
    return len(granted_keys)


def save_user_permissions_matrix(
    db,
    user_id: int,
    departments_payload: dict[str, list[dict[str, Any]]],
    *,
    catalog_resolver: Callable[[str], list[dict[str, Any]]],
) -> dict[str, int]:
    """Bulk save matrix for multiple departments."""
    saved: dict[str, int] = {}
    for department_slug, entries in departments_payload.items():
        catalog = catalog_resolver(department_slug)
        saved[department_slug] = save_user_department_tab_entries(
            db, user_id, department_slug, entries, catalog
        )
    return saved


def copy_user_permissions_matrix(
    db,
    source_user_id: int,
    target_user_id: int,
    *,
    department_slugs: list[str] | None = None,
) -> None:
    """Copy tab grants (and action flags) from one user to another."""
    ensure_user_tab_permissions_schema(db)
    params: list[Any] = [source_user_id]
    query = """
        SELECT department_slug, tab_key, endpoint, label, granted, action_flags
        FROM user_tab_permissions WHERE user_id=?
    """
    if department_slugs:
        placeholders = ",".join("?" for _ in department_slugs)
        query += f" AND department_slug IN ({placeholders})"
        params.extend(department_slugs)
    rows = db.execute(query, params).fetchall()
    if department_slugs:
        for slug in department_slugs:
            db.execute(
                "DELETE FROM user_tab_permissions WHERE user_id=? AND department_slug=?",
                (target_user_id, slug),
            )
    else:
        db.execute("DELETE FROM user_tab_permissions WHERE user_id=?", (target_user_id,))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for row in rows:
        if not row["granted"]:
            continue
        db.execute(
            """
            INSERT INTO user_tab_permissions(
                user_id, department_slug, tab_key, endpoint, label, granted, action_flags, updated_at
            ) VALUES(?,?,?,?,?,1,?,?)
            """,
            (
                target_user_id,
                row["department_slug"],
                row["tab_key"],
                row["endpoint"],
                row["label"],
                row["action_flags"],
                now,
            ),
        )


def _item_allowed(
    item: dict[str, Any],
    *,
    granted_keys: set[str],
    granted_endpoints: set[str],
    has_dept_restrictions: bool,
    scope_endpoints_to_department: bool = False,
) -> bool:
    if not has_dept_restrictions:
        return True
    key = tab_key_for_item(item)
    if key in granted_keys:
        return True
    if scope_endpoints_to_department:
        return False
    active = item.get("active_endpoints") or [item.get("endpoint")]
    return any(ep in granted_endpoints for ep in active if ep)


def filter_portal_menu_for_user(
    db,
    user_id: int,
    department_slug: str,
    menu: list[dict[str, Any]],
    *,
    full_access: bool,
) -> list[dict[str, Any]]:
    if full_access or not user_has_tab_restrictions(db, user_id):
        return menu
    granted_keys = get_granted_tab_keys_for_department(db, user_id, department_slug)
    has_dept_rows = bool(
        db.execute(
            "SELECT 1 FROM user_tab_permissions WHERE user_id=? AND department_slug=? LIMIT 1",
            (user_id, department_slug),
        ).fetchone()
    )
    if not has_dept_rows:
        return menu
    return [
        item
        for item in menu
        if _item_allowed(
            item,
            granted_keys=granted_keys,
            granted_endpoints=set(),
            has_dept_restrictions=True,
            scope_endpoints_to_department=True,
        )
    ]


def apply_user_tab_permissions_to_nav_groups(
    db,
    user_id: int,
    nav_groups: list[dict[str, Any]],
    *,
    full_access: bool,
    department_slug_for_nav: Callable[[str], str | None] | None = None,
) -> list[dict[str, Any]]:
    """Filter nav group items based on per-department tab grants."""
    if full_access or not user_has_tab_restrictions(db, user_id):
        return nav_groups

    granted_endpoints = get_granted_endpoints_for_user(db, user_id)
    dept_grants: dict[str, set[str]] = {}

    def grants_for_slug(dept_slug: str) -> tuple[set[str], bool]:
        if dept_slug not in dept_grants:
            dept_grants[dept_slug] = get_granted_tab_keys_for_department(db, user_id, dept_slug)
        keys = dept_grants[dept_slug]
        has_rows = bool(
            db.execute(
                "SELECT 1 FROM user_tab_permissions WHERE user_id=? AND department_slug=? LIMIT 1",
                (user_id, dept_slug),
            ).fetchone()
        )
        return keys, has_rows

    filtered: list[dict[str, Any]] = []
    for group in nav_groups:
        slug = group.get("slug") or ""
        dept_slug = department_slug_for_nav(slug) if department_slug_for_nav else slug
        if not dept_slug:
            filtered.append(group)
            continue
        granted_keys, has_dept_rows = grants_for_slug(dept_slug)
        if not has_dept_rows:
            filtered.append(group)
            continue
        items = group.get("items") or []
        kept = [
            item
            for item in items
            if _item_allowed(
                item,
                granted_keys=granted_keys,
                granted_endpoints=granted_endpoints,
                has_dept_restrictions=True,
            )
        ]
        if not kept:
            continue
        copy = dict(group)
        copy["items"] = kept
        filtered.append(copy)
    return filtered


def nav_slug_to_permission_department(nav_slug: str) -> str | None:
    """Map NAV_GROUPS slug to primary permission department slug."""
    mapping = {
        "dashboard": "reports",
        "project-management": "projects",
        "engineering-smartqto": "engineering",
        "store-procurement": "procurement",
        "accounts-finance": "accounts",
        "hr-payroll": "hr-payroll",
        "plant-machinery": "plant-machinery",
        "qc": "qc",
        "subcontract-management": "subcontract",
        "admin-compliance": "administration",
        "reports-analytics": "reports",
        "settings": None,
        "approvals": None,
        "erp-administration": None,
        "fleet-mechanical": "vehicle",
        "plant-operations": "plant-machinery",
        "store-section": "store",
    }
    return mapping.get(nav_slug, nav_slug or None)
