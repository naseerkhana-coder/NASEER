"""MAXEK ERP Super Admin — multi-tenant customers, licenses, limits, and platform ops."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Any

CUSTOMER_STATUSES = ("Active", "Inactive", "Suspended")
CUSTOMER_PLANS = ("Standard", "Professional", "Enterprise", "Demo")

# Assignable department portal slugs (must match ui_shell_config / get_department_portals).
DEPARTMENT_PORTAL_SLUGS: tuple[str, ...] = (
    "consultancy",
    "projects",
    "accounts",
    "store",
    "hr-payroll",
    "vehicle",
    "mechanical",
    "plant-operations",
    "asphalt-plant",
    "concrete-plant",
    "precast-yard",
    "engineering",
    "planning-wbs",
    "subcontract",
    "procurement",
    "qc",
    "tender",
    "reports",
    "administration",
)

DEPARTMENT_SLUG_LABELS: dict[str, str] = {
    "consultancy": "Consultancy ERP",
    "projects": "Projects",
    "accounts": "Accounts",
    "store": "Store & Inventory",
    "hr-payroll": "HR & Payroll",
    "vehicle": "Vehicle / Fleet",
    "mechanical": "Mechanical / Equipment",
    "plant-operations": "Plant Operations",
    "asphalt-plant": "Asphalt Plant",
    "concrete-plant": "Concrete Plant",
    "precast-yard": "Precast Yard",
    "engineering": "Engineering / Smart QTO",
    "planning-wbs": "Planning & Costing",
    "subcontract": "Subcontractor",
    "procurement": "Procurement",
    "qc": "QA / QC",
    "tender": "Tender",
    "reports": "Reports",
    "administration": "Office Administration",
}

CUSTOMER_PACKAGE_SEED: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    (
        "Standard",
        "Standard",
        "Core construction ERP — projects, accounts, store, HR and admin.",
        ("projects", "accounts", "store", "hr-payroll", "administration"),
    ),
    (
        "Professional",
        "Professional",
        "Standard plus QC, subcontract, planning, fleet and procurement.",
        (
            "projects",
            "accounts",
            "store",
            "hr-payroll",
            "administration",
            "qc",
            "subcontract",
            "planning-wbs",
            "vehicle",
            "procurement",
        ),
    ),
    (
        "Enterprise",
        "Enterprise",
        "Full MAXEK ERP — all department portals enabled.",
        DEPARTMENT_PORTAL_SLUGS,
    ),
    (
        "Demo",
        "Demo",
        "Limited demo access for evaluation.",
        ("projects", "accounts", "hr-payroll"),
    ),
)
LICENSE_STATUSES = ("Active", "Expired", "Suspended", "Pending")
LICENSE_PRODUCTS = ("TRADEX ERP", "MAXEK ERP", "CONSTRUCTION ERP")
SUBSCRIPTION_STATUSES = ("Active", "Cancelled", "Expired", "Trial")
PRIORITY_LEVELS = ("Low", "Medium", "High", "Critical")
CHANGE_REQUEST_STATUSES = ("Pending", "In Progress", "Completed", "Rejected", "On Hold")
TICKET_STATUSES = ("Open", "In Progress", "Resolved", "Closed")
PLATFORM_CUSTOMER_CODE = "MAXEK"
SUPERADMIN_DEFAULT_PASSWORD = "superadmin123"
DEMO_DEFAULT_PASSWORD = "demo123"
TRD001_ADMIN_DEFAULT_PASSWORD = "password"

SAMPLE_CUSTOMERS = (
    ("TRD001", "Arabica Coffee", "Saudi Arabia", "Ahmed Al-Rashid", "+966501234567", "info@arabicacoffee.sa", "310123456789003", 3, 18, "Professional"),
    ("TRD002", "Coffee House Riyadh", "Saudi Arabia", "Faisal Khan", "+966509876543", "contact@coffeehouse.sa", "310987654321004", 2, 12, "Standard"),
    ("MAX001", "ABC Construction India", "India", "Ramesh Patel", "+919876543210", "admin@abcconstruction.in", "27AABCU9603R1ZM", 5, 22, "Professional"),
    ("MAX002", "Road Infra Saudi", "Saudi Arabia", "Khalid Omar", "+966551112233", "ops@roadinfra.sa", "310555666777008", 4, 15, "Enterprise"),
    ("DEMO001", "Demo Customer", "India", "Demo User", "+919999999999", "demo@maxek.com", "", 1, 2, "Demo"),
)

CUSTOMER_ADMIN_ROLE = "Customer Admin"
SUPER_ADMIN_ROLE = "Super Admin"
CUSTOMER_ADMIN_CREATABLE_ROLES = (
    "Manager",
    "Cashier",
    "Accountant",
    "Store Keeper",
    "HR User",
    "User",
)

ERP_ADMIN_ACTIVE_ENDPOINTS = [
    "super_admin_platform_dashboard",
    "erp_admin_customers",
    "erp_admin_customer_settings",
    "erp_admin_licenses",
    "erp_admin_subscriptions",
    "erp_admin_user_limits",
    "erp_admin_branch_limits",
    "erp_admin_storage_limits",
    "erp_admin_login_monitoring",
    "erp_admin_support_tickets",
    "erp_admin_change_requests",
    "erp_admin_settings",
    "erp_admin_audit_logs",
    "erp_admin_system_health",
    "user_management",
]

ERP_ADMIN_SUBTOOLBAR = (
    {
        "endpoint": "super_admin_platform_dashboard",
        "label": "Platform Command Centre",
        "icon": "fa-gauge-high",
        "active_endpoints": ["super_admin_platform_dashboard"],
    },
    {
        "endpoint": "erp_admin_customers",
        "label": "Customer Master",
        "icon": "fa-building",
        "active_endpoints": ["erp_admin_customers"],
        "section": "customers-licenses",
    },
    {
        "endpoint": "erp_admin_licenses",
        "label": "License Master",
        "icon": "fa-id-card",
        "active_endpoints": ["erp_admin_licenses"],
        "section": "customers-licenses",
    },
    {
        "endpoint": "erp_admin_subscriptions",
        "label": "Subscriptions",
        "icon": "fa-file-contract",
        "active_endpoints": ["erp_admin_subscriptions"],
        "section": "customers-licenses",
    },
    {
        "endpoint": "erp_admin_user_limits",
        "label": "User Limits",
        "icon": "fa-users-gear",
        "active_endpoints": ["erp_admin_user_limits"],
        "section": "customers-licenses",
    },
    {
        "endpoint": "user_management",
        "label": "Platform User Management",
        "icon": "fa-user-shield",
        "active_endpoints": ["user_management"],
        "section": "customers-licenses",
    },
    {
        "endpoint": "erp_admin_branch_limits",
        "label": "Branch Limits",
        "icon": "fa-code-branch",
        "active_endpoints": ["erp_admin_branch_limits"],
        "section": "platform-ops",
    },
    {
        "endpoint": "erp_admin_storage_limits",
        "label": "Storage Limits",
        "icon": "fa-hard-drive",
        "active_endpoints": ["erp_admin_storage_limits"],
        "section": "platform-ops",
    },
    {
        "endpoint": "erp_admin_login_monitoring",
        "label": "Login Monitoring",
        "icon": "fa-right-to-bracket",
        "active_endpoints": ["erp_admin_login_monitoring"],
        "section": "platform-ops",
    },
    {
        "endpoint": "erp_admin_support_tickets",
        "label": "Support Tickets",
        "icon": "fa-headset",
        "active_endpoints": ["erp_admin_support_tickets"],
        "section": "platform-ops",
    },
    {
        "endpoint": "erp_admin_change_requests",
        "label": "Change Requests",
        "icon": "fa-pen-to-square",
        "active_endpoints": ["erp_admin_change_requests"],
        "section": "platform-ops",
    },
    {
        "endpoint": "erp_admin_settings",
        "label": "ERP Settings",
        "icon": "fa-sliders",
        "active_endpoints": ["erp_admin_settings"],
        "section": "platform-ops",
    },
    {
        "endpoint": "erp_admin_audit_logs",
        "label": "Audit Logs",
        "icon": "fa-clipboard-list",
        "active_endpoints": ["erp_admin_audit_logs"],
        "section": "platform-ops",
    },
    {
        "endpoint": "erp_admin_system_health",
        "label": "System Health",
        "icon": "fa-heart-pulse",
        "active_endpoints": ["erp_admin_system_health"],
        "section": "platform-ops",
    },
)

ERP_ADMIN_SUBTOOLBAR_SECTIONS = (
    {
        "label": "Overview",
        "items": ERP_ADMIN_SUBTOOLBAR[:1],
    },
    {
        "label": "Customers & Licenses",
        "items": [item for item in ERP_ADMIN_SUBTOOLBAR if item.get("section") == "customers-licenses"],
    },
    {
        "label": "Platform Operations",
        "items": [item for item in ERP_ADMIN_SUBTOOLBAR if item.get("section") == "platform-ops"],
    },
)


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _table_exists(db, table: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _ensure_column(db, table: str, column: str, col_type: str) -> None:
    if not _table_exists(db, table):
        return
    cols = [row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def _row_to_dict(row) -> dict[str, Any]:
    if row is None:
        return {}
    return dict(row)


def _canonical_department_slug(slug: str) -> str:
    """Map legacy/alias slugs to canonical portal slug (dedupes dashboard tiles)."""
    try:
        from ui_shell_config import resolve_department_portal_slug

        return resolve_department_portal_slug(slug)
    except Exception:
        return slug


def _parse_department_slugs(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        items = raw
    elif isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            items = parsed if isinstance(parsed, list) else [text]
        except json.JSONDecodeError:
            items = [part.strip() for part in text.split(",") if part.strip()]
    else:
        return []
    valid = set(DEPARTMENT_PORTAL_SLUGS)
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        slug = _canonical_department_slug(str(item).strip())
        if slug in valid and slug not in seen:
            seen.add(slug)
            result.append(slug)
    return result


def _serialize_department_slugs(slugs: list[str]) -> str:
    return json.dumps(_parse_department_slugs(slugs))


def seed_customer_packages(db) -> None:
    if not _table_exists(db, "erp_customer_packages"):
        return
    now = _now_ts()
    for sort_order, (code, name, description, defaults) in enumerate(CUSTOMER_PACKAGE_SEED):
        slugs_json = _serialize_department_slugs(list(defaults))
        existing = db.execute(
            "SELECT id FROM erp_customer_packages WHERE package_code=?",
            (code,),
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE erp_customer_packages SET package_name=?, description=?, "
                "default_department_slugs=?, sort_order=?, modified_at=? WHERE package_code=?",
                (name, description, slugs_json, sort_order, now, code),
            )
        else:
            db.execute(
                "INSERT INTO erp_customer_packages("
                "package_code, package_name, description, default_department_slugs, "
                "sort_order, status, created_at, modified_at"
                ") VALUES(?,?,?,?,?,'Active',?,?)",
                (code, name, description, slugs_json, sort_order, now, now),
            )


def list_customer_packages(db) -> list[dict[str, Any]]:
    if not _table_exists(db, "erp_customer_packages"):
        return [
            {
                "package_code": code,
                "package_name": name,
                "description": description,
                "default_department_slugs": list(defaults),
            }
            for code, name, description, defaults in CUSTOMER_PACKAGE_SEED
        ]
    rows = db.execute(
        "SELECT * FROM erp_customer_packages WHERE status='Active' ORDER BY sort_order, package_name"
    ).fetchall()
    packages: list[dict[str, Any]] = []
    for row in rows:
        item = _row_to_dict(row)
        item["default_department_slugs"] = _parse_department_slugs(
            item.get("default_department_slugs")
        )
        packages.append(item)
    return packages


def get_customer_package(db, package_code: str) -> dict[str, Any] | None:
    code = (package_code or "Standard").strip()
    if _table_exists(db, "erp_customer_packages"):
        row = db.execute(
            "SELECT * FROM erp_customer_packages WHERE package_code=?",
            (code,),
        ).fetchone()
        if row:
            item = _row_to_dict(row)
            item["default_department_slugs"] = _parse_department_slugs(
                item.get("default_department_slugs")
            )
            return item
    for seed_code, name, description, defaults in CUSTOMER_PACKAGE_SEED:
        if seed_code == code:
            return {
                "package_code": seed_code,
                "package_name": name,
                "description": description,
                "default_department_slugs": list(defaults),
            }
    return None


def get_package_default_departments(db, package_code: str) -> list[str]:
    package = get_customer_package(db, package_code)
    if package:
        return list(package.get("default_department_slugs") or [])
    return list(get_package_default_departments_static(package_code))


def get_package_default_departments_static(package_code: str) -> list[str]:
    code = (package_code or "Standard").strip()
    for seed_code, _name, _description, defaults in CUSTOMER_PACKAGE_SEED:
        if seed_code == code:
            return list(defaults)
    return list(CUSTOMER_PACKAGE_SEED[0][3])


def get_customer_enabled_departments(db, customer_id: int | None) -> list[str]:
    if not customer_id or not _table_exists(db, "erp_customers"):
        return list(DEPARTMENT_PORTAL_SLUGS)
    row = db.execute(
        "SELECT package_code, plan, enabled_departments FROM erp_customers WHERE id=?",
        (customer_id,),
    ).fetchone()
    if not row:
        return list(DEPARTMENT_PORTAL_SLUGS)
    enabled = _parse_department_slugs(row["enabled_departments"])
    if enabled:
        return enabled
    package_code = (row["package_code"] or row["plan"] or "Standard").strip()
    return get_package_default_departments(db, package_code)


def backfill_customer_package_settings(db) -> None:
    if not _table_exists(db, "erp_customers"):
        return
    rows = db.execute(
        "SELECT id, plan, package_code, enabled_departments "
        "FROM erp_customers WHERE COALESCE(is_platform, 0)=0"
    ).fetchall()
    for row in rows:
        plan = (row["plan"] or "Standard").strip() or "Standard"
        package_code = (row["package_code"] or plan).strip() or "Standard"
        enabled = _parse_department_slugs(row["enabled_departments"])
        if not enabled:
            enabled = get_package_default_departments(db, package_code)
        db.execute(
            "UPDATE erp_customers SET package_code=?, plan=?, enabled_departments=? WHERE id=?",
            (package_code, package_code, _serialize_department_slugs(enabled), row["id"]),
        )


def ensure_super_admin_schema(db) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS erp_customers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_code TEXT UNIQUE NOT NULL,
            company_name TEXT NOT NULL,
            country TEXT,
            contact_person TEXT,
            mobile TEXT,
            email TEXT,
            vat_gst_number TEXT,
            num_branches INTEGER DEFAULT 0,
            num_users INTEGER DEFAULT 0,
            plan TEXT DEFAULT 'Standard',
            status TEXT DEFAULT 'Active',
            is_platform INTEGER DEFAULT 0,
            created_at TEXT,
            modified_at TEXT
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS erp_licenses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_no TEXT UNIQUE NOT NULL,
            customer_id INTEGER NOT NULL,
            product TEXT DEFAULT 'TRADEX ERP',
            plan TEXT,
            start_date TEXT,
            expiry_date TEXT,
            status TEXT DEFAULT 'Active',
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(customer_id) REFERENCES erp_customers(id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS erp_subscriptions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            plan TEXT,
            billing_cycle TEXT DEFAULT 'Annual',
            amount REAL DEFAULT 0,
            start_date TEXT,
            renewal_date TEXT,
            status TEXT DEFAULT 'Active',
            notes TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(customer_id) REFERENCES erp_customers(id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS erp_user_limits(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL UNIQUE,
            plan TEXT,
            users_allowed INTEGER DEFAULT 25,
            current_users INTEGER DEFAULT 0,
            modified_at TEXT,
            FOREIGN KEY(customer_id) REFERENCES erp_customers(id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS erp_branch_limits(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL UNIQUE,
            branches_allowed INTEGER DEFAULT 5,
            current_branches INTEGER DEFAULT 0,
            modified_at TEXT,
            FOREIGN KEY(customer_id) REFERENCES erp_customers(id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS erp_storage_limits(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL UNIQUE,
            storage_allowed_mb INTEGER DEFAULT 1024,
            current_usage_mb REAL DEFAULT 0,
            modified_at TEXT,
            FOREIGN KEY(customer_id) REFERENCES erp_customers(id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS erp_change_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_no TEXT UNIQUE NOT NULL,
            customer_id INTEGER,
            request_date TEXT,
            module TEXT,
            issue TEXT,
            priority TEXT DEFAULT 'Medium',
            status TEXT DEFAULT 'Pending',
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(customer_id) REFERENCES erp_customers(id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS erp_support_tickets(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_no TEXT UNIQUE NOT NULL,
            customer_id INTEGER,
            reported_by TEXT,
            problem TEXT,
            screenshot_path TEXT,
            priority TEXT DEFAULT 'Medium',
            status TEXT DEFAULT 'Open',
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(customer_id) REFERENCES erp_customers(id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS erp_audit_logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_time TEXT,
            customer_id INTEGER,
            user_id INTEGER,
            username TEXT,
            action TEXT,
            module TEXT,
            details TEXT,
            ip_address TEXT
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS erp_settings(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_key TEXT UNIQUE NOT NULL,
            setting_value TEXT,
            category TEXT DEFAULT 'General',
            description TEXT,
            modified_at TEXT
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS erp_customer_packages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            package_code TEXT UNIQUE NOT NULL,
            package_name TEXT NOT NULL,
            description TEXT,
            default_department_slugs TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Active',
            created_at TEXT,
            modified_at TEXT
        )
        """
    )
    _ensure_column(db, "users", "customer_id", "INTEGER")
    _ensure_column(db, "users", "status", "TEXT DEFAULT 'Active'")
    for column, col_type in (
        ("company_name", "TEXT"),
        ("country", "TEXT"),
        ("contact_person", "TEXT"),
        ("mobile", "TEXT"),
        ("email", "TEXT"),
        ("vat_gst_number", "TEXT"),
        ("num_branches", "INTEGER DEFAULT 0"),
        ("num_users", "INTEGER DEFAULT 0"),
        ("plan", "TEXT DEFAULT 'Standard'"),
        ("status", "TEXT DEFAULT 'Active'"),
        ("is_platform", "INTEGER DEFAULT 0"),
        ("created_at", "TEXT"),
        ("modified_at", "TEXT"),
        ("package_code", "TEXT DEFAULT 'Standard'"),
        ("enabled_departments", "TEXT"),
        ("logo_path", "TEXT"),
        ("theme", "TEXT"),
        ("address", "TEXT"),
        ("financial_year", "TEXT"),
        ("currency", "TEXT DEFAULT 'INR'"),
        ("timezone", "TEXT DEFAULT 'Asia/Kolkata'"),
        ("email_settings", "TEXT"),
        ("dashboard_theme", "TEXT DEFAULT 'command-centre'"),
    ):
        _ensure_column(db, "erp_customers", column, col_type)
    _ensure_column(db, "users", "email", "TEXT")
    _ensure_column(db, "users", "mobile", "TEXT")
    for table, columns in (
        (
            "erp_user_limits",
            (
                ("plan", "TEXT"),
                ("users_allowed", "INTEGER DEFAULT 25"),
                ("current_users", "INTEGER DEFAULT 0"),
                ("modified_at", "TEXT"),
            ),
        ),
        (
            "erp_branch_limits",
            (
                ("branches_allowed", "INTEGER DEFAULT 5"),
                ("current_branches", "INTEGER DEFAULT 0"),
                ("modified_at", "TEXT"),
            ),
        ),
        (
            "erp_storage_limits",
            (
                ("storage_allowed_mb", "INTEGER DEFAULT 1024"),
                ("current_usage_mb", "REAL DEFAULT 0"),
                ("modified_at", "TEXT"),
            ),
        ),
    ):
        for column, col_type in columns:
            _ensure_column(db, table, column, col_type)
    for column, col_type in (
        ("license_no", "TEXT"),
        ("customer_id", "INTEGER"),
        ("product", "TEXT DEFAULT 'TRADEX ERP'"),
        ("plan", "TEXT"),
        ("start_date", "TEXT"),
        ("expiry_date", "TEXT"),
        ("status", "TEXT DEFAULT 'Active'"),
        ("created_at", "TEXT"),
        ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "erp_licenses", column, col_type)
    if _table_exists(db, "erp_customers"):
        db.execute(
            "UPDATE erp_customers SET is_platform=0 WHERE is_platform IS NULL"
        )
        db.execute(
            "UPDATE erp_customers SET status='Active' "
            "WHERE status IS NULL OR TRIM(status)=''"
        )
        db.execute(
            "UPDATE erp_customers SET plan='Standard' "
            "WHERE plan IS NULL OR TRIM(plan)=''"
        )
        db.execute(
            "UPDATE erp_customers SET package_code=plan "
            "WHERE package_code IS NULL OR TRIM(package_code)=''"
        )
    seed_customer_packages(db)
    backfill_customer_package_settings(db)
    backfill_customer_limit_rows(db)
    try:
        from tenant_isolation import migrate_users_composite_username

        migrate_users_composite_username(db)
    except Exception:
        pass


def backfill_customer_limit_rows(db) -> None:
    """Ensure limit rows exist for every tenant customer (legacy VPS DBs)."""
    if not _table_exists(db, "erp_customers"):
        return
    rows = db.execute(
        "SELECT id, plan FROM erp_customers WHERE COALESCE(is_platform, 0)=0"
    ).fetchall()
    for row in rows:
        plan = str(row["plan"] or "Standard").strip() or "Standard"
        ensure_customer_limits(db, int(row["id"]), plan)


def get_user_limit_row(db, customer_id: int):
    return db.execute(
        "SELECT * FROM erp_user_limits WHERE customer_id=?",
        (customer_id,),
    ).fetchone()


def get_branch_limit_row(db, customer_id: int):
    return db.execute(
        "SELECT * FROM erp_branch_limits WHERE customer_id=?",
        (customer_id,),
    ).fetchone()


def assert_user_limit_not_exceeded(db, customer_id: int) -> None:
    sync_customer_usage_counts(db, customer_id)
    row = get_user_limit_row(db, customer_id)
    if not row:
        return
    allowed = int(row["users_allowed"] or 0)
    current = int(row["current_users"] or 0)
    if allowed > 0 and current >= allowed:
        raise ValueError(
            f"User limit reached ({current}/{allowed}). Upgrade plan or deactivate users."
        )


def assert_branch_limit_not_exceeded(db, customer_id: int) -> None:
    sync_customer_usage_counts(db, customer_id)
    row = get_branch_limit_row(db, customer_id)
    if not row:
        return
    allowed = int(row["branches_allowed"] or 0)
    current = int(row["current_branches"] or 0)
    if allowed > 0 and current >= allowed:
        raise ValueError(
            f"Branch limit reached ({current}/{allowed}). Upgrade plan or remove branches."
        )


def get_customer_by_code(db, customer_code: str):
    code = (customer_code or "").strip().upper()
    if not code:
        return None
    try:
        return db.execute(
            "SELECT * FROM erp_customers WHERE UPPER(customer_code)=?",
            (code,),
        ).fetchone()
    except Exception:
        return None


def get_customer_by_id(db, customer_id: int):
    try:
        return db.execute(
            "SELECT * FROM erp_customers WHERE id=?",
            (customer_id,),
        ).fetchone()
    except Exception:
        return None


def is_platform_super_admin(db, user_row) -> bool:
    """True only for MAXEK platform Super Admin (not tenant Customer/Company Admin)."""
    if user_row is None:
        return False
    role = str(user_row["role"] or "").strip().lower() if "role" in user_row.keys() else ""
    if role not in ("super admin", "superadmin"):
        return False
    customer_id = user_row["customer_id"] if "customer_id" in user_row.keys() else None
    if not customer_id:
        return True
    try:
        customer = get_customer_by_id(db, customer_id)
    except Exception:
        return False
    return bool(customer and customer["is_platform"])


def is_super_admin_user(db, user_row) -> bool:
    return is_platform_super_admin(db, user_row)


def is_customer_admin_user(user_row) -> bool:
    if user_row is None:
        return False
    role = str(user_row["role"] or "").strip().lower() if "role" in user_row.keys() else ""
    return role == "customer admin"


def authenticate_tenant_user(
    db,
    company_code: str,
    username: str,
    password: str,
    *,
    verify_password_fn,
    user_is_active_fn,
):
    company_code = (company_code or "").strip().upper()
    username = (username or "").strip()
    if not username or not password:
        return None, "Username and password are required."

    customer = get_customer_by_code(db, company_code) if company_code else None
    if company_code and not customer:
        return None, "Invalid company code."
    if customer and str(customer["status"] or "").lower() not in ("active",):
        return None, "Customer account is not active."

    if customer:
        user = db.execute(
            "SELECT * FROM users WHERE username=? AND customer_id=?",
            (username, customer["id"]),
        ).fetchone()
        if not user and not customer["is_platform"]:
            legacy_user = db.execute(
                "SELECT * FROM users WHERE username=? AND (customer_id IS NULL OR customer_id=0)",
                (username,),
            ).fetchone()
            legacy_role = (
                str(legacy_user["role"] or "").strip().lower()
                if legacy_user and "role" in legacy_user.keys()
                else ""
            )
            if (
                legacy_user
                and username.lower() not in ("admin", "superadmin")
                and legacy_role not in ("super admin", "platform super admin")
                and user_is_active_fn(legacy_user)
                and verify_password_fn(legacy_user["password"], password)
            ):
                db.execute(
                    "UPDATE users SET customer_id=? WHERE id=?",
                    (customer["id"], legacy_user["id"]),
                )
                sync_customer_usage_counts(db, customer["id"])
                user = db.execute(
                    "SELECT * FROM users WHERE id=?",
                    (legacy_user["id"],),
                ).fetchone()
        if not user and customer["is_platform"]:
            user = db.execute(
                "SELECT * FROM users WHERE username=? AND (customer_id=? OR customer_id IS NULL)",
                (username, customer["id"]),
            ).fetchone()
    else:
        user = db.execute(
            "SELECT * FROM users WHERE username=? AND (customer_id IS NULL OR customer_id=0)",
            (username,),
        ).fetchone()

    if not user:
        return None, "Invalid username or password, or account is inactive."
    if not user_is_active_fn(user):
        return None, "Invalid username or password, or account is inactive."
    if not verify_password_fn(user["password"], password):
        return None, "Invalid username or password, or account is inactive."
    return user, None


def sync_customer_usage_counts(db, customer_id: int) -> None:
    customer = get_customer_by_id(db, customer_id)
    if not customer:
        return
    plan = str(customer["plan"] or "Standard").strip() or "Standard"
    ensure_customer_limits(db, customer_id, plan)

    user_count = 0
    if _table_exists(db, "users"):
        user_cols = {
            row[1] for row in db.execute("PRAGMA table_info(users)").fetchall()
        }
        if "customer_id" in user_cols:
            if "status" in user_cols:
                user_count = db.execute(
                    "SELECT COUNT(*) AS c FROM users "
                    "WHERE customer_id=? AND status='Active'",
                    (customer_id,),
                ).fetchone()["c"]
            else:
                user_count = db.execute(
                    "SELECT COUNT(*) AS c FROM users WHERE customer_id=?",
                    (customer_id,),
                ).fetchone()["c"]

    branch_count = 0
    if _table_exists(db, "company_branches"):
        branch_cols = {
            row[1]
            for row in db.execute("PRAGMA table_info(company_branches)").fetchall()
        }
        if "customer_id" in branch_cols:
            branch_count = db.execute(
                "SELECT COUNT(*) AS c FROM company_branches WHERE customer_id=?",
                (customer_id,),
            ).fetchone()["c"]

    now = _now_ts()
    if _table_exists(db, "erp_customers"):
        customer_cols = {
            row[1] for row in db.execute("PRAGMA table_info(erp_customers)").fetchall()
        }
        updates: list[str] = []
        params: list[Any] = []
        if "num_users" in customer_cols:
            updates.append("num_users=?")
            params.append(user_count)
        if "num_branches" in customer_cols:
            updates.append("num_branches=?")
            params.append(branch_count)
        if "modified_at" in customer_cols:
            updates.append("modified_at=?")
            params.append(now)
        if updates:
            params.append(customer_id)
            db.execute(
                f"UPDATE erp_customers SET {', '.join(updates)} WHERE id=?",
                params,
            )
    if _table_exists(db, "erp_user_limits"):
        db.execute(
            "UPDATE erp_user_limits SET current_users=?, modified_at=? "
            "WHERE customer_id=?",
            (user_count, now, customer_id),
        )
    if _table_exists(db, "erp_branch_limits"):
        db.execute(
            "UPDATE erp_branch_limits SET current_branches=?, modified_at=? "
            "WHERE customer_id=?",
            (branch_count, now, customer_id),
        )


def ensure_customer_limits(db, customer_id: int, plan: str = "Standard") -> None:
    plan_limits = {
        "Standard": (10, 2, 512),
        "Professional": (25, 5, 2048),
        "Enterprise": (100, 20, 10240),
        "Demo": (5, 1, 256),
    }
    users_allowed, branches_allowed, storage_mb = plan_limits.get(plan, plan_limits["Standard"])
    now = _now_ts()
    if not db.execute(
        "SELECT id FROM erp_user_limits WHERE customer_id=?", (customer_id,)
    ).fetchone():
        db.execute(
            "INSERT INTO erp_user_limits(customer_id, plan, users_allowed, current_users, modified_at) "
            "VALUES(?,?,?,0,?)",
            (customer_id, plan, users_allowed, now),
        )
    if not db.execute(
        "SELECT id FROM erp_branch_limits WHERE customer_id=?", (customer_id,)
    ).fetchone():
        db.execute(
            "INSERT INTO erp_branch_limits(customer_id, branches_allowed, current_branches, modified_at) "
            "VALUES(?,?,0,?)",
            (customer_id, branches_allowed, now),
        )
    if not db.execute(
        "SELECT id FROM erp_storage_limits WHERE customer_id=?", (customer_id,)
    ).fetchone():
        db.execute(
            "INSERT INTO erp_storage_limits(customer_id, storage_allowed_mb, current_usage_mb, modified_at) "
            "VALUES(?,?,0,?)",
            (customer_id, storage_mb, now),
        )


def list_customers(db, search: str = "") -> list[dict[str, Any]]:
    if not _table_exists(db, "erp_customers"):
        return []
    clauses = ["is_platform=0"]
    params: list[Any] = []
    if search:
        clauses.append(
            "(customer_code LIKE ? OR company_name LIKE ? OR country LIKE ? OR email LIKE ?)"
        )
        like = f"%{search}%"
        params.extend([like, like, like, like])
    where = " AND ".join(clauses)
    try:
        rows = db.execute(
            f"SELECT * FROM erp_customers WHERE {where} ORDER BY customer_code",
            params,
        ).fetchall()
    except Exception:
        return []
    return [_row_to_dict(r) for r in rows]


def _count_customer_users(db, customer_id: int) -> int:
    if not _table_exists(db, "users"):
        return 0
    user_cols = {row[1] for row in db.execute("PRAGMA table_info(users)").fetchall()}
    if "customer_id" not in user_cols:
        return 0
    try:
        return int(
            db.execute(
                "SELECT COUNT(*) AS c FROM users WHERE customer_id=?",
                (customer_id,),
            ).fetchone()["c"]
        )
    except Exception:
        return 0


def _count_customer_licenses(db, customer_id: int) -> int:
    if not _table_exists(db, "erp_licenses"):
        return 0
    try:
        return int(
            db.execute(
                "SELECT COUNT(*) AS c FROM erp_licenses WHERE customer_id=?",
                (customer_id,),
            ).fetchone()["c"]
        )
    except Exception:
        return 0


def _customer_code_prefix(company_name: str) -> str:
    letters = "".join(ch for ch in (company_name or "").upper() if ch.isalnum())
    if len(letters) >= 3:
        return letters[:3]
    return (letters + "CUS")[:3]


def _next_customer_sequence(db) -> int:
    rows = db.execute(
        "SELECT customer_code FROM erp_customers WHERE customer_code NOT LIKE 'MAXEK%'"
    ).fetchall()
    max_num = 0
    for row in rows:
        code = str(row["customer_code"] or "").upper()
        suffix = code[3:] if len(code) > 3 else ""
        if suffix.isdigit():
            max_num = max(max_num, int(suffix))
    return max_num + 1


def save_customer(db, data: dict[str, Any], record_id: int | None = None) -> int:
    ensure_super_admin_schema(db)
    now = _now_ts()
    company_name = (data.get("company_name") or "").strip()
    code = (data.get("customer_code") or "").strip().upper()
    if not record_id and not code:
        code = next_customer_code(db, company_name)
    if not code:
        raise ValueError("Customer code is required.")
    if not company_name:
        raise ValueError("Company name is required.")
    package_code = (data.get("package_code") or data.get("plan") or "Standard").strip()
    if package_code not in CUSTOMER_PLANS:
        raise ValueError(f"Invalid package: {package_code}")
    enabled_departments = _parse_department_slugs(data.get("enabled_departments"))
    if not enabled_departments:
        enabled_departments = get_package_default_departments(db, package_code)
    if not enabled_departments:
        raise ValueError("Select at least one department portal for this customer.")
    enabled_json = _serialize_department_slugs(enabled_departments)
    fields = (
        code,
        company_name,
        (data.get("country") or "").strip(),
        (data.get("contact_person") or "").strip(),
        (data.get("mobile") or "").strip(),
        (data.get("email") or "").strip(),
        (data.get("vat_gst_number") or "").strip(),
        int(data.get("num_branches") or 0),
        int(data.get("num_users") or 0),
        package_code,
        package_code,
        enabled_json,
        (data.get("status") or "Active").strip(),
        now,
    )
    if record_id:
        db.execute(
            "UPDATE erp_customers SET customer_code=?, company_name=?, country=?, contact_person=?, "
            "mobile=?, email=?, vat_gst_number=?, num_branches=?, num_users=?, plan=?, package_code=?, "
            "enabled_departments=?, status=?, modified_at=? WHERE id=? AND is_platform=0",
            (*fields, record_id),
        )
        ensure_customer_limits(db, record_id, fields[9])
        sync_customer_usage_counts(db, record_id)
        log_audit(db, None, None, "Update", "Customer Master", f"Updated customer {code}")
        return record_id
    existing = get_customer_by_code(db, code)
    if existing:
        raise ValueError(f"Customer code {code} already exists.")
    cur = db.execute(
        "INSERT INTO erp_customers("
        "customer_code, company_name, country, contact_person, mobile, email, vat_gst_number, "
        "num_branches, num_users, plan, package_code, enabled_departments, status, created_at, modified_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (*fields, now),
    )
    customer_id = cur.lastrowid
    ensure_customer_limits(db, customer_id, fields[9])
    log_audit(db, None, None, "Create", "Customer Master", f"Created customer {code}")
    return customer_id


def _delete_customer_related_rows(db, customer_id: int) -> None:
    """Remove platform rows linked to a tenant customer."""
    if _table_exists(db, "users"):
        try:
            db.execute("DELETE FROM users WHERE customer_id=?", (customer_id,))
        except Exception:
            pass
    for table in (
        "erp_user_limits",
        "erp_branch_limits",
        "erp_storage_limits",
        "erp_subscriptions",
        "erp_support_tickets",
        "erp_change_requests",
        "erp_licenses",
    ):
        if _table_exists(db, table):
            try:
                db.execute(f"DELETE FROM {table} WHERE customer_id=?", (customer_id,))
            except Exception:
                pass


def delete_customer(db, customer_id: int, *, cascade: bool = False) -> None:
    """Remove a tenant customer and related platform rows when safe to do so."""
    ensure_super_admin_schema(db)
    customer_row = get_customer_by_id(db, customer_id)
    if not customer_row:
        raise ValueError("Customer not found.")
    customer = _row_to_dict(customer_row)
    if int(customer.get("is_platform") or 0):
        raise ValueError("Cannot delete the platform customer.")
    code = str(customer.get("customer_code") or "").strip()

    user_count = _count_customer_users(db, customer_id)
    license_count = _count_customer_licenses(db, customer_id)

    if cascade:
        _delete_customer_related_rows(db, customer_id)
        if not _table_exists(db, "erp_customers"):
            raise ValueError("Customer master table is not available.")
        db.execute("DELETE FROM erp_customers WHERE id=? AND is_platform=0", (customer_id,))
        detail = f"Deleted customer {code}"
        if user_count or license_count:
            detail += (
                f" (cascade: {user_count} user(s), {license_count} license(s) removed)"
            )
        log_audit(db, None, None, "Delete", "Customer Master", detail)
        return

    if user_count:
        raise ValueError(
            f"Cannot delete {code} — {user_count} user account(s) exist. "
            "Use Delete with cascade confirmation or set status to Inactive."
        )

    if license_count:
        raise ValueError(
            f"Cannot delete {code} — {license_count} license(s) exist. "
            "Remove licenses first or set status to Inactive."
        )

    _delete_customer_related_rows(db, customer_id)
    if not _table_exists(db, "erp_customers"):
        raise ValueError("Customer master table is not available.")
    db.execute("DELETE FROM erp_customers WHERE id=? AND is_platform=0", (customer_id,))
    log_audit(db, None, None, "Delete", "Customer Master", f"Deleted customer {code}")


def save_customer_tenant_settings(db, customer_id: int, data: dict[str, Any]) -> None:
    """Per-tenant branding and regional settings (Customer Admin)."""
    if not customer_id:
        raise ValueError("Customer context required.")
    ensure_super_admin_schema(db)
    fields = {
        "company_name": (data.get("company_name") or "").strip(),
        "logo_path": (data.get("logo_path") or "").strip(),
        "theme": (data.get("theme") or "").strip(),
        "address": (data.get("address") or "").strip(),
        "vat_gst_number": (data.get("vat_gst_number") or "").strip(),
        "financial_year": (data.get("financial_year") or "").strip(),
        "currency": (data.get("currency") or "INR").strip(),
        "timezone": (data.get("timezone") or "Asia/Kolkata").strip(),
        "email_settings": (data.get("email_settings") or "").strip(),
        "dashboard_theme": (data.get("dashboard_theme") or "").strip() or "command-centre",
    }
    if not fields["company_name"]:
        raise ValueError("Company name is required.")
    now = _now_ts()
    db.execute(
        "UPDATE erp_customers SET company_name=?, logo_path=?, theme=?, address=?, "
        "vat_gst_number=?, financial_year=?, currency=?, timezone=?, email_settings=?, "
        "dashboard_theme=?, modified_at=? "
        "WHERE id=? AND COALESCE(is_platform, 0)=0",
        (
            fields["company_name"],
            fields["logo_path"] or None,
            fields["theme"] or None,
            fields["address"] or None,
            fields["vat_gst_number"] or None,
            fields["financial_year"] or None,
            fields["currency"],
            fields["timezone"],
            fields["email_settings"] or None,
            fields["dashboard_theme"],
            now,
            customer_id,
        ),
    )
    log_audit(
        db,
        customer_id,
        None,
        "Update",
        "Tenant Settings",
        f"Updated branding/settings for customer id {customer_id}",
    )


def create_customer_admin_user(
    db,
    customer_id: int,
    *,
    username: str,
    password: str,
    confirm_password: str,
    display_name: str = "",
    email: str = "",
    mobile: str = "",
    hash_password_fn,
) -> None:
    """Create the first Customer Admin for a new tenant."""
    username = (username or "").strip()
    password = (password or "").strip()
    confirm_password = (confirm_password or "").strip()
    email = (email or "").strip()
    mobile = (mobile or "").strip()
    if not username:
        raise ValueError("Admin username is required when onboarding a new customer.")

    if not password:
        raise ValueError("Admin password is required when creating a first admin account.")
    if password != confirm_password:
        raise ValueError("Admin password and confirmation do not match.")
    if len(password) < 4:
        raise ValueError("Admin password must be at least 4 characters.")
    if not email:
        raise ValueError("Admin email is required for the Customer Administrator account.")
    if not mobile:
        raise ValueError("Admin mobile number is required for the Customer Administrator account.")

    customer = get_customer_by_id(db, customer_id)
    if not customer:
        raise ValueError("Customer not found.")
    customer_code = str(customer["customer_code"] or "").strip()

    assert_user_limit_not_exceeded(db, customer_id)

    existing = db.execute(
        "SELECT id FROM users WHERE username=? AND customer_id=?",
        (username, customer_id),
    ).fetchone()
    if existing:
        raise ValueError(
            f"Username '{username}' already exists for customer {customer_code}."
        )

    employee_name = (display_name or "").strip() or username
    db.execute(
        "INSERT INTO users(username, password, role, workflow_role, employee_name, email, mobile, "
        "status, customer_id) VALUES(?,?,?,?,?,?,?,?,?)",
        (
            username,
            hash_password_fn(password),
            CUSTOMER_ADMIN_ROLE,
            "Administrator",
            employee_name,
            email,
            mobile,
            "Active",
            customer_id,
        ),
    )
    sync_customer_usage_counts(db, customer_id)
    log_audit(
        db,
        customer_id,
        None,
        "Create",
        "Customer Onboarding",
        f"Created Customer Admin '{username}' for {customer_code}",
        username=username,
    )


def get_platform_dashboard_data(db) -> dict[str, Any]:
    """Metrics and lists for the Super Admin platform dashboard."""
    ensure_super_admin_schema(db)
    total_companies = db.execute(
        "SELECT COUNT(*) AS c FROM erp_customers WHERE COALESCE(is_platform, 0)=0"
    ).fetchone()["c"]
    active_companies = db.execute(
        "SELECT COUNT(*) AS c FROM erp_customers WHERE COALESCE(is_platform, 0)=0 AND status='Active'"
    ).fetchone()["c"]
    active_users = db.execute(
        "SELECT COUNT(*) AS c FROM users WHERE status='Active'"
    ).fetchone()["c"]
    active_projects = 0
    try:
        active_projects = db.execute(
            "SELECT COUNT(*) AS c FROM projects WHERE status='Active'"
        ).fetchone()["c"]
    except Exception:
        pass
    pending_approvals = 0
    try:
        pending_approvals = db.execute(
            "SELECT COUNT(*) AS c FROM approval_requests "
            "WHERE workflow_status NOT IN ('approved', 'rejected')"
        ).fetchone()["c"]
    except Exception:
        pass
    active_licenses = db.execute(
        "SELECT COUNT(*) AS c FROM erp_licenses WHERE status='Active'"
    ).fetchone()["c"]
    total_licenses = db.execute("SELECT COUNT(*) AS c FROM erp_licenses").fetchone()["c"]
    open_tickets = db.execute(
        "SELECT COUNT(*) AS c FROM erp_support_tickets WHERE status IN ('Open','In Progress')"
    ).fetchone()["c"]
    pending_change_requests = db.execute(
        "SELECT COUNT(*) AS c FROM erp_change_requests WHERE status IN ('Open','Pending','In Progress')"
    ).fetchone()["c"]
    storage_used_mb = 0.0
    storage_allowed_mb = 0
    try:
        usage_row = db.execute(
            "SELECT COALESCE(SUM(current_usage_mb), 0) AS used, "
            "COALESCE(SUM(storage_allowed_mb), 0) AS allowed FROM erp_storage_limits"
        ).fetchone()
        storage_used_mb = round(float(usage_row["used"] if usage_row else 0), 1)
        storage_allowed_mb = int(usage_row["allowed"] if usage_row else 0)
    except Exception:
        pass
    db_path = os.environ.get("DATABASE_PATH") or os.environ.get("MAXEK_DB_PATH") or "maxek_erp.db"
    db_size_mb = round(os.path.getsize(db_path) / (1024 * 1024), 1) if os.path.isfile(db_path) else 0.0
    system_health = "Healthy" if os.path.isfile(db_path) else "Check DB"
    if open_tickets > 5:
        system_health = "Attention"
    license_status = f"{active_licenses}/{total_licenses} active" if total_licenses else "No licenses"
    backup_status = "Configured"
    try:
        backup_row = db.execute(
            "SELECT value FROM erp_settings WHERE key='last_backup_at' LIMIT 1"
        ).fetchone()
        backup_status = backup_row["value"] if backup_row and backup_row["value"] else "Not recorded"
    except Exception:
        backup_status = "Not recorded"
    server_status = "Online"
    recent_rows = db.execute(
        """
        SELECT customer_code, company_name, country, plan, status, created_at
        FROM erp_customers
        WHERE COALESCE(is_platform, 0)=0
        ORDER BY COALESCE(created_at, modified_at, '') DESC, id DESC
        LIMIT 8
        """
    ).fetchall()
    metric_cards = [
        {"label": "Total Companies", "value": total_companies},
        {"label": "Active Companies", "value": active_companies},
        {"label": "Active Users", "value": active_users},
        {"label": "Active Projects", "value": active_projects},
        {"label": "Pending Approvals", "value": pending_approvals, "warn": pending_approvals > 0},
        {"label": "System Health", "value": system_health},
        {"label": "License Status", "value": license_status},
        {
            "label": "Storage Used",
            "value": f"{storage_used_mb:.0f} MB" + (f" / {storage_allowed_mb} MB" if storage_allowed_mb else ""),
        },
        {"label": "Backup Status", "value": backup_status},
        {"label": "Server Status", "value": server_status},
    ]
    return {
        "metrics": {
            "total_companies": total_companies,
            "active_companies": active_companies,
            "active_users": active_users,
            "active_projects": active_projects,
            "pending_approvals": pending_approvals,
            "system_health": system_health,
            "license_status": license_status,
            "storage_used_mb": storage_used_mb,
            "database_mb": db_size_mb,
            "open_tickets": open_tickets,
            "pending_change_requests": pending_change_requests,
            "backup_status": backup_status,
            "server_status": server_status,
        },
        "metric_cards": metric_cards,
        "recent_customers": [_row_to_dict(row) for row in recent_rows],
    }


def list_licenses(db, search: str = "") -> list[dict[str, Any]]:
    ensure_super_admin_schema(db)
    clauses = ["1=1"]
    params: list[Any] = []
    if search:
        clauses.append(
            "(l.license_no LIKE ? OR c.customer_code LIKE ? OR c.company_name LIKE ? OR l.product LIKE ?)"
        )
        like = f"%{search}%"
        params.extend([like, like, like, like])
    where = " AND ".join(clauses)
    rows = db.execute(
        f"""
        SELECT l.*, c.customer_code, c.company_name, c.contact_person, c.mobile, c.email,
               c.num_users, c.plan AS customer_plan, ul.users_allowed
        FROM erp_licenses l
        JOIN erp_customers c ON c.id = l.customer_id
        LEFT JOIN erp_user_limits ul ON ul.customer_id = c.id
        WHERE {where}
        ORDER BY l.id DESC
        """,
        params,
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def next_license_no(db) -> str:
    ensure_super_admin_schema(db)
    year = datetime.now().strftime("%Y")
    prefix = f"LIC-{year}-"
    rows = db.execute(
        "SELECT license_no FROM erp_licenses WHERE license_no LIKE ?",
        (f"{prefix}%",),
    ).fetchall()
    max_seq = 0
    for row in rows:
        raw = str(row["license_no"] or "")
        suffix = raw.replace(prefix, "", 1)
        if suffix.isdigit():
            max_seq = max(max_seq, int(suffix))
    return f"{prefix}{max_seq + 1:04d}"


def save_license(db, data: dict[str, Any], record_id: int | None = None) -> int:
    ensure_super_admin_schema(db)
    now = _now_ts()
    license_no = (data.get("license_no") or "").strip()
    customer_code = (data.get("customer_code") or "").strip().upper()
    if not license_no:
        raise ValueError("License number is required.")
    customer = get_customer_by_code(db, customer_code)
    if not customer:
        raise ValueError("Customer code not found.")
    customer_plan = (
        str(customer["plan"] or "Standard").strip()
        if "plan" in customer.keys()
        else "Standard"
    )
    product = (data.get("product") or "TRADEX ERP").strip()
    plan = (data.get("plan") or customer_plan or "Standard").strip()
    start_date = (data.get("start_date") or _today()).strip()
    expiry_date = (data.get("expiry_date") or "").strip()
    status = (data.get("status") or "Active").strip()
    update_fields = (
        license_no,
        customer["id"],
        product,
        plan,
        start_date,
        expiry_date,
        status,
        now,
    )
    if record_id:
        db.execute(
            "UPDATE erp_licenses SET license_no=?, customer_id=?, product=?, plan=?, "
            "start_date=?, expiry_date=?, status=?, modified_at=? WHERE id=?",
            (*update_fields, record_id),
        )
        log_audit(db, None, None, "Update", "License Master", f"Updated license {license_no}")
        return record_id
    cur = db.execute(
        "INSERT INTO erp_licenses("
        "license_no, customer_id, product, plan, start_date, expiry_date, status, created_at, modified_at"
        ") VALUES(?,?,?,?,?,?,?,?,?)",
        (
            license_no,
            customer["id"],
            product,
            plan,
            start_date,
            expiry_date,
            status,
            now,
            now,
        ),
    )
    log_audit(db, None, None, "Create", "License Master", f"Created license {license_no}")
    return int(cur.lastrowid)


def get_license_handover_details(db, license_id: int) -> dict[str, Any] | None:
    ensure_super_admin_schema(db)
    row = db.execute(
        """
        SELECT l.*, c.customer_code, c.company_name, c.country, c.contact_person,
               c.mobile, c.email, c.vat_gst_number, c.num_branches, c.num_users,
               c.plan AS customer_plan, c.package_code, c.address,
               ul.users_allowed, ul.current_users,
               bl.branches_allowed, bl.current_branches,
               sl.storage_allowed_mb, sl.current_usage_mb
        FROM erp_licenses l
        JOIN erp_customers c ON c.id = l.customer_id
        LEFT JOIN erp_user_limits ul ON ul.customer_id = c.id
        LEFT JOIN erp_branch_limits bl ON bl.customer_id = c.id
        LEFT JOIN erp_storage_limits sl ON sl.customer_id = c.id
        WHERE l.id=?
        """,
        (license_id,),
    ).fetchone()
    if not row:
        return None
    data = _row_to_dict(row)
    user = db.execute(
        """
        SELECT username, role, employee_name, email, mobile
        FROM users
        WHERE customer_id=?
        ORDER BY CASE WHEN role IN ('admin', 'super_admin', 'Super Admin') THEN 0 ELSE 1 END, id
        LIMIT 1
        """,
        (data["customer_id"],),
    ).fetchone()
    data["login_user"] = _row_to_dict(user) if user else {}
    return data


def delete_license(db, license_id: int | None) -> None:
    ensure_super_admin_schema(db)
    if not license_id:
        raise ValueError("Invalid license.")
    row = db.execute(
        "SELECT license_no FROM erp_licenses WHERE id=?",
        (license_id,),
    ).fetchone()
    if not row:
        raise ValueError("License not found.")
    db.execute("DELETE FROM erp_licenses WHERE id=?", (license_id,))
    log_audit(
        db,
        None,
        None,
        "Delete",
        "License Master",
        f"Deleted license {row['license_no']}",
    )


def list_subscriptions(db) -> list[dict[str, Any]]:
    rows = db.execute(
        """
        SELECT s.*, c.customer_code, c.company_name
        FROM erp_subscriptions s
        JOIN erp_customers c ON c.id = s.customer_id
        WHERE c.is_platform=0
        ORDER BY s.renewal_date DESC, c.customer_code
        """
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def save_subscription(db, data: dict[str, Any], record_id: int | None = None) -> int:
    now = _now_ts()
    customer_code = (data.get("customer_code") or "").strip().upper()
    customer = get_customer_by_code(db, customer_code)
    if not customer:
        raise ValueError("Customer code not found.")
    fields = (
        customer["id"],
        (data.get("plan") or customer["plan"] or "Standard").strip(),
        (data.get("billing_cycle") or "Annual").strip(),
        float(data.get("amount") or 0),
        (data.get("start_date") or _today()).strip(),
        (data.get("renewal_date") or "").strip(),
        (data.get("status") or "Active").strip(),
        (data.get("notes") or "").strip(),
        now,
    )
    if record_id:
        db.execute(
            "UPDATE erp_subscriptions SET customer_id=?, plan=?, billing_cycle=?, amount=?, "
            "start_date=?, renewal_date=?, status=?, notes=?, modified_at=? WHERE id=?",
            (*fields, record_id),
        )
        return record_id
    db.execute(
        "INSERT INTO erp_subscriptions("
        "customer_id, plan, billing_cycle, amount, start_date, renewal_date, status, notes, "
        "created_at, modified_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?)",
        (*fields, now),
    )
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def list_user_limits(db) -> list[dict[str, Any]]:
    ensure_super_admin_schema(db)
    rows = db.execute(
        """
        SELECT ul.*, c.customer_code, c.company_name, c.plan AS customer_plan
        FROM erp_user_limits ul
        JOIN erp_customers c ON c.id = ul.customer_id
        WHERE COALESCE(c.is_platform, 0)=0
        ORDER BY c.customer_code
        """
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def list_branch_limits(db) -> list[dict[str, Any]]:
    ensure_super_admin_schema(db)
    rows = db.execute(
        """
        SELECT bl.*, c.customer_code, c.company_name
        FROM erp_branch_limits bl
        JOIN erp_customers c ON c.id = bl.customer_id
        WHERE COALESCE(c.is_platform, 0)=0
        ORDER BY c.customer_code
        """
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def list_storage_limits(db) -> list[dict[str, Any]]:
    ensure_super_admin_schema(db)
    rows = db.execute(
        """
        SELECT sl.*, c.customer_code, c.company_name
        FROM erp_storage_limits sl
        JOIN erp_customers c ON c.id = sl.customer_id
        WHERE COALESCE(c.is_platform, 0)=0
        ORDER BY c.customer_code
        """
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def update_user_limit(db, customer_code: str, users_allowed: int, plan: str = "") -> None:
    customer = get_customer_by_code(db, customer_code)
    if not customer:
        raise ValueError("Customer not found.")
    sync_customer_usage_counts(db, customer["id"])
    db.execute(
        "UPDATE erp_user_limits SET users_allowed=?, plan=COALESCE(?, plan), modified_at=? "
        "WHERE customer_id=?",
        (users_allowed, plan or None, _now_ts(), customer["id"]),
    )


def update_branch_limit(db, customer_code: str, branches_allowed: int) -> None:
    customer = get_customer_by_code(db, customer_code)
    if not customer:
        raise ValueError("Customer not found.")
    sync_customer_usage_counts(db, customer["id"])
    db.execute(
        "UPDATE erp_branch_limits SET branches_allowed=?, modified_at=? WHERE customer_id=?",
        (branches_allowed, _now_ts(), customer["id"]),
    )


def update_storage_limit(db, customer_code: str, storage_allowed_mb: int) -> None:
    customer = get_customer_by_code(db, customer_code)
    if not customer:
        raise ValueError("Customer not found.")
    db.execute(
        "UPDATE erp_storage_limits SET storage_allowed_mb=?, modified_at=? WHERE customer_id=?",
        (storage_allowed_mb, _now_ts(), customer["id"]),
    )


def list_change_requests(db, search: str = "") -> list[dict[str, Any]]:
    clauses = ["1=1"]
    params: list[Any] = []
    if search:
        clauses.append(
            "(cr.request_no LIKE ? OR c.company_name LIKE ? OR cr.module LIKE ? OR cr.issue LIKE ?)"
        )
        like = f"%{search}%"
        params.extend([like, like, like, like])
    where = " AND ".join(clauses)
    rows = db.execute(
        f"""
        SELECT cr.*, c.customer_code, c.company_name
        FROM erp_change_requests cr
        LEFT JOIN erp_customers c ON c.id = cr.customer_id
        WHERE {where}
        ORDER BY cr.request_date DESC, cr.request_no DESC
        """,
        params,
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def save_change_request(db, data: dict[str, Any], record_id: int | None = None) -> int:
    now = _now_ts()
    request_no = (data.get("request_no") or "").strip()
    customer_code = (data.get("customer_code") or "").strip().upper()
    customer = get_customer_by_code(db, customer_code) if customer_code else None
    if not request_no:
        raise ValueError("Request number is required.")
    fields = (
        request_no,
        customer["id"] if customer else None,
        (data.get("request_date") or _today()).strip(),
        (data.get("module") or "").strip(),
        (data.get("issue") or "").strip(),
        (data.get("priority") or "Medium").strip(),
        (data.get("status") or "Pending").strip(),
        (data.get("created_by") or "system").strip(),
        now,
    )
    if record_id:
        db.execute(
            "UPDATE erp_change_requests SET request_no=?, customer_id=?, request_date=?, module=?, "
            "issue=?, priority=?, status=?, modified_at=? WHERE id=?",
            (fields[0], fields[1], fields[2], fields[3], fields[4], fields[5], fields[6], now, record_id),
        )
        return record_id
    db.execute(
        "INSERT INTO erp_change_requests("
        "request_no, customer_id, request_date, module, issue, priority, status, created_by, "
        "created_at, modified_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?)",
        fields,
    )
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def list_support_tickets(db, customer_id: int | None = None, search: str = "") -> list[dict[str, Any]]:
    clauses = ["1=1"]
    params: list[Any] = []
    if customer_id:
        clauses.append("t.customer_id=?")
        params.append(customer_id)
    if search:
        clauses.append("(t.ticket_no LIKE ? OR t.problem LIKE ? OR c.company_name LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])
    where = " AND ".join(clauses)
    rows = db.execute(
        f"""
        SELECT t.*, c.customer_code, c.company_name
        FROM erp_support_tickets t
        LEFT JOIN erp_customers c ON c.id = t.customer_id
        WHERE {where}
        ORDER BY t.created_at DESC, t.ticket_no DESC
        """,
        params,
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def save_support_ticket(
    db,
    data: dict[str, Any],
    screenshot_path: str | None = None,
    record_id: int | None = None,
    customer_id: int | None = None,
) -> int:
    now = _now_ts()
    ticket_no = (data.get("ticket_no") or "").strip()
    if not ticket_no:
        count = db.execute("SELECT COUNT(*) AS c FROM erp_support_tickets").fetchone()["c"]
        ticket_no = f"TKT-{count + 1:04d}"
    customer_code = (data.get("customer_code") or "").strip().upper()
    cust_id = customer_id
    if customer_code and not cust_id:
        customer = get_customer_by_code(db, customer_code)
        cust_id = customer["id"] if customer else None
    fields = (
        ticket_no,
        cust_id,
        (data.get("reported_by") or data.get("created_by") or "").strip(),
        (data.get("problem") or "").strip(),
        screenshot_path or (data.get("screenshot_path") or "").strip() or None,
        (data.get("priority") or "Medium").strip(),
        (data.get("status") or "Open").strip(),
        now,
    )
    if record_id:
        db.execute(
            "UPDATE erp_support_tickets SET ticket_no=?, customer_id=?, reported_by=?, problem=?, "
            "screenshot_path=COALESCE(?, screenshot_path), priority=?, status=?, modified_at=? "
            "WHERE id=?",
            (*fields, record_id),
        )
        return record_id
    db.execute(
        "INSERT INTO erp_support_tickets("
        "ticket_no, customer_id, reported_by, problem, screenshot_path, priority, status, "
        "created_at, modified_at"
        ") VALUES(?,?,?,?,?,?,?,?,?)",
        fields,
    )
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def list_audit_logs(db, limit: int = 200) -> list[dict[str, Any]]:
    rows = db.execute(
        """
        SELECT a.*, c.customer_code, c.company_name
        FROM erp_audit_logs a
        LEFT JOIN erp_customers c ON c.id = a.customer_id
        ORDER BY a.event_time DESC, a.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def log_audit(
    db,
    customer_id: int | None,
    user_id: int | None,
    action: str,
    module: str,
    details: str,
    username: str | None = None,
    ip_address: str | None = None,
) -> None:
    if not _table_exists(db, "erp_audit_logs"):
        return
    db.execute(
        "INSERT INTO erp_audit_logs("
        "event_time, customer_id, user_id, username, action, module, details, ip_address"
        ") VALUES(?,?,?,?,?,?,?,?)",
        (_now_ts(), customer_id, user_id, username, action, module, details, ip_address),
    )


def list_erp_settings(db) -> list[dict[str, Any]]:
    rows = db.execute(
        "SELECT * FROM erp_settings ORDER BY category, setting_key"
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def save_erp_setting(db, key: str, value: str, category: str = "General", description: str = "") -> None:
    now = _now_ts()
    existing = db.execute(
        "SELECT id FROM erp_settings WHERE setting_key=?", (key,)
    ).fetchone()
    if existing:
        db.execute(
            "UPDATE erp_settings SET setting_value=?, category=?, description=?, modified_at=? "
            "WHERE setting_key=?",
            (value, category, description, now, key),
        )
    else:
        db.execute(
            "INSERT INTO erp_settings(setting_key, setting_value, category, description, modified_at) "
            "VALUES(?,?,?,?,?)",
            (key, value, category, description, now),
        )


def get_system_health(db, db_path: str) -> dict[str, Any]:
    checks = []
    db_size_mb = 0.0
    if os.path.isfile(db_path):
        db_size_mb = round(os.path.getsize(db_path) / (1024 * 1024), 2)
    checks.append({"name": "Database", "status": "OK" if os.path.isfile(db_path) else "Error", "detail": f"{db_size_mb} MB"})
    customer_count = db.execute("SELECT COUNT(*) AS c FROM erp_customers WHERE is_platform=0").fetchone()["c"]
    active_licenses = db.execute(
        "SELECT COUNT(*) AS c FROM erp_licenses WHERE status='Active'"
    ).fetchone()["c"]
    user_count = db.execute("SELECT COUNT(*) AS c FROM users WHERE status='Active'").fetchone()["c"]
    open_tickets = db.execute(
        "SELECT COUNT(*) AS c FROM erp_support_tickets WHERE status IN ('Open','In Progress')"
    ).fetchone()["c"]
    return {
        "checks": checks,
        "metrics": {
            "customers": customer_count,
            "active_licenses": active_licenses,
            "active_users": user_count,
            "open_tickets": open_tickets,
            "database_mb": db_size_mb,
        },
    }


def next_customer_code(db, company_name: str = "") -> str:
    prefix = _customer_code_prefix(company_name)
    return f"{prefix}{_next_customer_sequence(db):03d}"


def _seed_report() -> dict[str, list[str]]:
    return {"created": [], "skipped": [], "errors": []}


def _ensure_platform_customer(db, report: dict[str, list[str]]) -> int | None:
    now = _now_ts()
    platform = get_customer_by_code(db, PLATFORM_CUSTOMER_CODE)
    if platform:
        report["skipped"].append(f"customer:{PLATFORM_CUSTOMER_CODE}")
        return platform["id"]
    db.execute(
        "INSERT INTO erp_customers("
        "customer_code, company_name, country, contact_person, mobile, email, plan, status, "
        "is_platform, created_at, modified_at"
        ") VALUES(?,?,?,?,?,?,?,?,1,?,?)",
        (
            PLATFORM_CUSTOMER_CODE,
            "MAXEK Technologies Platform",
            "India",
            "Platform Admin",
            "",
            "platform@maxek.com",
            "Enterprise",
            "Active",
            now,
            now,
        ),
    )
    platform_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    report["created"].append(f"customer:{PLATFORM_CUSTOMER_CODE}")
    return platform_id


def _ensure_sample_customer(
    db,
    report: dict[str, list[str]],
    code: str,
    name: str,
    country: str,
    contact: str,
    mobile: str,
    email: str,
    vat: str,
    branches: int,
    users: int,
    plan: str,
) -> int | None:
    existing = get_customer_by_code(db, code)
    if existing:
        report["skipped"].append(f"customer:{code}")
        ensure_customer_limits(db, existing["id"], plan)
        return existing["id"]
    now = _now_ts()
    cur = db.execute(
        "INSERT INTO erp_customers("
        "customer_code, company_name, country, contact_person, mobile, email, vat_gst_number, "
        "num_branches, num_users, plan, status, created_at, modified_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (code, name, country, contact, mobile, email, vat, branches, users, plan, "Active", now, now),
    )
    customer_id = cur.lastrowid
    ensure_customer_limits(db, customer_id, plan)
    report["created"].append(f"customer:{code}")
    return customer_id


def _ensure_license(
    db,
    report: dict[str, list[str]],
    license_no: str,
    customer_id: int,
    product: str,
    plan: str,
) -> None:
    if db.execute(
        "SELECT id FROM erp_licenses WHERE license_no=?",
        (license_no,),
    ).fetchone():
        report["skipped"].append(f"license:{license_no}")
        return
    now = _now_ts()
    db.execute(
        "INSERT INTO erp_licenses("
        "license_no, customer_id, product, plan, start_date, expiry_date, status, created_at, modified_at"
        ") VALUES(?,?,?,?,?,?,?,?,?)",
        (
            license_no,
            customer_id,
            product,
            plan,
            "2026-01-01",
            "2027-12-31",
            "Active",
            now,
            now,
        ),
    )
    report["created"].append(f"license:{license_no}")


def seed_super_admin_data(
    db,
    hash_password_fn=None,
    *,
    include_sample_tenants: bool | None = None,
) -> dict[str, list[str]]:
    """Idempotent platform bootstrap. Always seeds MAXEK + superadmin; sample tenants optional."""
    report = _seed_report()
    if include_sample_tenants is None:
        include_sample_tenants = not os.environ.get("MAXEK_SKIP_DEMO_SEED")

    platform_id = _ensure_platform_customer(db, report)
    if platform_id:
        ensure_customer_limits(db, platform_id, "Enterprise")

    customer_ids: dict[str, int] = {}
    if include_sample_tenants:
        for code, name, country, contact, mobile, email, vat, branches, users, plan in SAMPLE_CUSTOMERS:
            customer_id = _ensure_sample_customer(
                db,
                report,
                code,
                name,
                country,
                contact,
                mobile,
                email,
                vat,
                branches,
                users,
                plan,
            )
            if customer_id:
                customer_ids[code] = customer_id

        license_specs = (
            ("LIC-2026-001", "TRD001", "TRADEX ERP", "Professional"),
            ("LIC-2026-002", "TRD002", "TRADEX ERP", "Standard"),
            ("LIC-2026-003", "MAX001", "MAXEK ERP", "Professional"),
            ("LIC-2026-004", "MAX002", "MAXEK ERP", "Enterprise"),
            ("LIC-2026-005", "DEMO001", "TRADEX ERP", "Demo"),
        )
        for license_no, code, product, plan in license_specs:
            customer_id = customer_ids.get(code)
            if customer_id:
                _ensure_license(db, report, license_no, customer_id, product, plan)

        trd001_id = customer_ids.get("TRD001")
        if trd001_id and not db.execute(
            "SELECT id FROM erp_change_requests WHERE request_no=?",
            ("CR-001",),
        ).fetchone():
            now = _now_ts()
            db.execute(
                "INSERT INTO erp_change_requests("
                "request_no, customer_id, request_date, module, issue, priority, status, created_by, "
                "created_at, modified_at"
                ") VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    "CR-001",
                    trd001_id,
                    _today(),
                    "POS",
                    "Need Arabic receipt",
                    "High",
                    "Pending",
                    "system",
                    now,
                    now,
                ),
            )
            report["created"].append("change_request:CR-001")
        elif trd001_id:
            report["skipped"].append("change_request:CR-001")

        if trd001_id and not db.execute(
            "SELECT id FROM erp_subscriptions WHERE customer_id=?",
            (trd001_id,),
        ).fetchone():
            now = _now_ts()
            db.execute(
                "INSERT INTO erp_subscriptions("
                "customer_id, plan, billing_cycle, amount, start_date, renewal_date, status, notes, "
                "created_at, modified_at"
                ") VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    trd001_id,
                    "Professional",
                    "Annual",
                    120000,
                    "2026-01-01",
                    "2027-01-01",
                    "Active",
                    "Annual TRADEX ERP subscription",
                    now,
                    now,
                ),
            )
            report["created"].append("subscription:TRD001")
        elif trd001_id:
            report["skipped"].append("subscription:TRD001")

        default_settings = (
            ("platform_name", "MAXEK ERP", "General", "Platform display name"),
            ("default_timezone", "Asia/Kolkata", "General", "Default tenant timezone"),
            ("support_email", "support@maxek.com", "Support", "Support contact email"),
            ("maintenance_mode", "off", "System", "Maintenance mode flag"),
        )
        for key, value, category, description in default_settings:
            if db.execute("SELECT id FROM erp_settings WHERE setting_key=?", (key,)).fetchone():
                report["skipped"].append(f"setting:{key}")
            else:
                save_erp_setting(db, key, value, category, description)
                report["created"].append(f"setting:{key}")

    _seed_users_if_missing(db, hash_password_fn, report, include_sample_tenants=include_sample_tenants)
    return report


def bootstrap_super_admin(db, hash_password_fn=None, *, include_sample_tenants: bool | None = None) -> dict[str, list[str]]:
    """Ensure schema and run idempotent platform seed."""
    ensure_super_admin_schema(db)
    return seed_super_admin_data(
        db,
        hash_password_fn=hash_password_fn,
        include_sample_tenants=include_sample_tenants,
    )


def _seed_users_if_missing(
    db,
    hash_password_fn=None,
    report: dict[str, list[str]] | None = None,
    *,
    include_sample_tenants: bool = True,
) -> None:
    if not hash_password_fn:
        if report is not None:
            report["errors"].append("users:hash_password_fn_missing")
        return
    if report is None:
        report = _seed_report()

    platform = get_customer_by_code(db, PLATFORM_CUSTOMER_CODE)
    platform_id = platform["id"] if platform else None
    trd001 = get_customer_by_code(db, "TRD001") if include_sample_tenants else None
    demo = get_customer_by_code(db, "DEMO001") if include_sample_tenants else None

    admin_row = db.execute(
        "SELECT id, customer_id FROM users WHERE username='admin' AND customer_id IS NULL"
    ).fetchone()
    if admin_row and trd001:
        existing_tenant_admin = db.execute(
            "SELECT id FROM users WHERE username='admin' AND customer_id=?",
            (trd001["id"],),
        ).fetchone()
        if existing_tenant_admin and existing_tenant_admin["id"] != admin_row["id"]:
            report["skipped"].append("user:legacy_admin_mapped_to_TRD001")
        else:
            try:
                db.execute(
                    "UPDATE users SET customer_id=?, role=?, password=?, employee_name=? WHERE id=?",
                    (
                        trd001["id"],
                        CUSTOMER_ADMIN_ROLE,
                        hash_password_fn(TRD001_ADMIN_DEFAULT_PASSWORD),
                        "Arabica Coffee Admin",
                        admin_row["id"],
                    ),
                )
                report["created"].append("user:legacy_admin_mapped_to_TRD001")
            except sqlite3.IntegrityError:
                report["skipped"].append("user:legacy_admin_mapped_to_TRD001")

    superadmin_row = db.execute(
        "SELECT id FROM users WHERE username='superadmin' AND customer_id=?",
        (platform_id,),
    ).fetchone()
    if platform_id and not superadmin_row:
        db.execute(
            "INSERT INTO users(username, password, role, workflow_role, employee_name, status, customer_id) "
            "VALUES(?,?,?,?,?,?,?)",
            (
                "superadmin",
                hash_password_fn(SUPERADMIN_DEFAULT_PASSWORD),
                SUPER_ADMIN_ROLE,
                "Administrator",
                "Platform Super Admin",
                "Active",
                platform_id,
            ),
        )
        report["created"].append("user:superadmin")
    elif platform_id and superadmin_row:
        report["skipped"].append("user:superadmin")
    elif not platform_id:
        report["errors"].append("user:superadmin_missing_platform_customer")

    if include_sample_tenants:
        demo_row = db.execute(
            "SELECT id FROM users WHERE username='demo' AND customer_id=?",
            (demo["id"],),
        ).fetchone() if demo else None
        if demo and not demo_row:
            db.execute(
                "INSERT INTO users(username, password, role, workflow_role, employee_name, status, customer_id) "
                "VALUES(?,?,?,?,?,?,?)",
                (
                    "demo",
                    hash_password_fn(DEMO_DEFAULT_PASSWORD),
                    CUSTOMER_ADMIN_ROLE,
                    "Administrator",
                    "Demo Customer Admin",
                    "Active",
                    demo["id"],
                ),
            )
            report["created"].append("user:demo")
        elif demo and demo_row:
            report["skipped"].append("user:demo")

        if trd001 and not db.execute(
            "SELECT id FROM users WHERE username='admin' AND customer_id=?",
            (trd001["id"],),
        ).fetchone():
            db.execute(
                "INSERT INTO users(username, password, role, workflow_role, employee_name, status, customer_id) "
                "VALUES(?,?,?,?,?,?,?)",
                (
                    "admin",
                    hash_password_fn(TRD001_ADMIN_DEFAULT_PASSWORD),
                    CUSTOMER_ADMIN_ROLE,
                    "Administrator",
                    "Arabica Coffee Admin",
                    "Active",
                    trd001["id"],
                ),
            )
            report["created"].append("user:TRD001_admin")
        elif trd001:
            report["skipped"].append("user:TRD001_admin")
