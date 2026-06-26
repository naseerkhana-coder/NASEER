"""MAXEK ERP — Final UI/UX shell configuration (Construction ERP standard)."""

from __future__ import annotations

APP_VERSION_LABEL = "MAXEK ERP v1.0"

GLOBAL_SEARCH_CATEGORIES = [
    {"key": "project", "label": "Project", "icon": "fa-diagram-project"},
    {"key": "boq", "label": "BOQ", "icon": "fa-table-list"},
    {"key": "dpr", "label": "DPR", "icon": "fa-clipboard-list"},
    {"key": "material", "label": "Material", "icon": "fa-boxes-stacked"},
    {"key": "employee", "label": "Employee", "icon": "fa-user"},
    {"key": "vendor", "label": "Vendor", "icon": "fa-truck-field"},
    {"key": "vehicle", "label": "Vehicle", "icon": "fa-truck"},
    {"key": "purchase_order", "label": "Purchase Order", "icon": "fa-file-invoice"},
    {"key": "invoice", "label": "Invoice", "icon": "fa-file-invoice-dollar"},
    {"key": "bill", "label": "Bill", "icon": "fa-file-invoice-dollar"},
    {"key": "work_order", "label": "Work Order", "icon": "fa-helmet-safety"},
]

HELP_CENTER_ITEMS = [
    {"label": "User Manual", "icon": "fa-book", "endpoint": "help_desk", "query": {}},
    {"label": "Video Tutorials", "icon": "fa-circle-play", "endpoint": "help_desk", "query": {"tab": "videos"}},
    {"label": "Contact Support", "icon": "fa-headset", "endpoint": "help_contact", "query": {}},
    {
        "label": "WhatsApp Support",
        "icon": "fa-brands fa-whatsapp",
        "href": "https://wa.me/919876543210",
        "external": True,
    },
    {"label": "Remote Support", "icon": "fa-desktop", "endpoint": "help_contact", "query": {"mode": "remote"}},
]

# Main toolbar: ordered slugs with display labels per UI/UX standard.
MAIN_TOOLBAR_SLUGS = [
    ("dashboard", "Dashboard"),
    ("project-management", "Projects"),
    ("engineering-smartqto", "Planning"),
    ("store-procurement", "Procurement"),
    ("store-section", "Store"),
    ("accounts-finance", "Accounts"),
    ("hr-payroll", "HR & Payroll"),
    ("fleet-mechanical", "Fleet & Mechanical"),
    ("plant-operations", "Plant Operations"),
    ("qc", "Quality Control"),
    ("admin-compliance", "Administration"),
    ("reports-analytics", "Reports"),
    ("settings", "Settings"),
]

# Virtual toolbar entries (not in NAV_GROUPS) — split plant/fleet and store.
VIRTUAL_TOOLBAR_ENTRIES: dict[str, dict] = {
    "store-section": {
        "label": "Store",
        "icon": "fa-warehouse",
        "endpoint": "store",
        "active_endpoints": ["store", "store_receipt", "store_issue", "material_transfer"],
        "items": [
            {"endpoint": "store_receipt", "label": "Material Receipt", "active_endpoints": ["store_receipt"]},
            {"endpoint": "store_issue", "label": "Material Issue", "active_endpoints": ["store_issue"]},
            {"endpoint": "material_transfer", "label": "Transfer", "active_endpoints": ["material_transfer"]},
            {"endpoint": "store", "label": "Stock Verification", "active_endpoints": ["store"]},
        ],
    },
    "fleet-mechanical": {
        "label": "Fleet & Mechanical",
        "icon": "fa-truck",
        "endpoint": "fleet_dashboard",
        "active_endpoints": [
            "fleet_dashboard",
            "fleet_vehicles",
            "fleet_running_log",
            "fleet_diesel_issue",
            "fleet_diesel_purchase",
            "fleet_diesel_stock",
            "fleet_vehicle_documents",
        ],
        "items": [
            {"endpoint": "fleet_vehicles", "label": "Vehicle Master", "active_endpoints": ["fleet_vehicles"]},
            {"endpoint": "fleet_diesel_issue", "label": "Fuel Entry", "active_endpoints": ["fleet_diesel_issue"]},
            {"endpoint": "plant_maintenance", "label": "Job Card", "active_endpoints": ["plant_maintenance"]},
            {"endpoint": "fleet_vehicle_documents", "label": "Tyre Register", "active_endpoints": ["fleet_vehicle_documents"]},
            {"endpoint": "fleet_running_log", "label": "Breakdown Register", "active_endpoints": ["fleet_running_log"]},
        ],
    },
    "plant-operations": {
        "label": "Plant Operations",
        "icon": "fa-industry",
        "endpoint": "plant_dashboard",
        "active_endpoints": [
            "plant_dashboard",
            "plant_asphalt_production",
            "plant_rmc_production",
            "plant_crusher_production",
            "plant_wetmix_production",
        ],
        "items": [
            {"endpoint": "plant_asphalt_production", "label": "Asphalt Plant", "active_endpoints": ["plant_asphalt_production"]},
            {"endpoint": "plant_rmc_production", "label": "RMC Plant", "active_endpoints": ["plant_rmc_production"]},
            {"endpoint": "plant_crusher_production", "label": "Crusher Plant", "active_endpoints": ["plant_crusher_production"]},
            {"endpoint": "plant_asphalt_production", "label": "Production", "active_endpoints": ["plant_asphalt_production", "plant_rmc_production"]},
            {"endpoint": "plant_asphalt_dispatch", "label": "Dispatch", "active_endpoints": ["plant_asphalt_dispatch", "plant_rmc_dispatch"]},
        ],
    },
}

# Standard sub-toolbar labels per department (slug → ordered label filters).
STANDARD_SUB_LABELS: dict[str, list[str]] = {
    "project-management": [
        "Project Master",
        "BOQ",
        "DPR",
        "Client Billing",
        "Photos",
        "Documents",
    ],
    "engineering-smartqto": [
        "Costing",
        "WBS",
        "Resource Planning",
        "Micro Planning",
        "Progress Tracking",
    ],
    "store-procurement": [
        "Material Request",
        "Purchase Request",
        "RFQ",
        "Quotation Comparison",
        "Purchase Order",
        "GRN",
    ],
    "store-section": [
        "Material Receipt",
        "Material Issue",
        "Transfer",
        "Stock Verification",
    ],
    "accounts-finance": [
        "Payment Voucher",
        "Receipt Voucher",
        "Journal Voucher",
        "GST",
        "TDS",
        "Reports",
    ],
    "hr-payroll": [
        "Employee Master",
        "Attendance",
        "Timesheet",
        "Payroll",
        "Leave",
    ],
    "fleet-mechanical": [
        "Vehicle Master",
        "Fuel Entry",
        "Job Card",
        "Tyre Register",
        "Breakdown Register",
    ],
    "plant-operations": [
        "Asphalt Plant",
        "RMC Plant",
        "Crusher Plant",
        "Production",
        "Dispatch",
    ],
    "qc": [
        "Material Testing",
        "Cube Register",
        "Asphalt Testing",
        "NCR Register",
    ],
}

# Label aliases: map existing nav item labels to standard sub-toolbar names.
SUB_LABEL_ALIASES: dict[str, str] = {
    "Project List": "Project Master",
    "Create Project": "Project Master",
    "BOQ Master": "BOQ",
    "Client Billing": "Client Billing",
    "Project Photos": "Photos",
    "Project Documents": "Documents",
    "Cost Planning": "Costing",
    "Planning": "Costing",
    "WBS": "WBS",
    "Material Request": "Material Request",
    "Purchase Request": "Purchase Request",
    "Purchase Order": "Purchase Order",
    "GRN": "GRN",
    "Staff Master": "Employee Master",
    "Attendance": "Attendance",
    "Payroll": "Payroll",
    "Leave Management": "Leave",
    "Vehicle Master": "Vehicle Master",
    "Diesel Issue": "Fuel Entry",
    "Running Log": "Breakdown Register",
    "QC Master": "Material Testing",
    "NCR": "NCR Register",
}

# Accounts department sub-toolbar — grouped sections (Masters | Transactions | Books).
ACCOUNTS_SUBTOOLBAR_SECTIONS: list[dict] = [
    {
        "label": "Masters",
        "items": [
            {"endpoint": "accounts_hub", "label": "Accounts Hub", "active_endpoints": ["accounts_hub"]},
            {"endpoint": "accounts_chart_of_accounts", "label": "Chart of Accounts", "active_endpoints": ["accounts_chart_of_accounts"]},
            {"endpoint": "treasury_bank_accounts", "label": "Bank Master", "active_endpoints": ["treasury_bank_accounts"]},
            {"endpoint": "petty_cash", "label": "Petty Cash", "active_endpoints": ["petty_cash"]},
        ],
    },
    {
        "label": "Transactions",
        "items": [
            {"endpoint": "head_office_expenses", "label": "Daily Expenses", "active_endpoints": ["head_office_expenses", "accounts_expenses"]},
            {"endpoint": "accounts_expenses", "label": "Expense / Purchase", "active_endpoints": ["accounts_expenses"]},
            {"endpoint": "accounts_receipts", "label": "Receipts", "active_endpoints": ["accounts_receipts"]},
            {"endpoint": "accounts_payments", "label": "Payments", "active_endpoints": ["accounts_payments"]},
        ],
    },
    {
        "label": "Books",
        "items": [
            {"endpoint": "accounts_cash_book_v2", "label": "Cash Book", "active_endpoints": ["accounts_cash_book_v2", "cash_book"]},
            {"endpoint": "accounts_bank_book_v2", "label": "Bank Book", "active_endpoints": ["accounts_bank_book_v2", "bank_book"]},
            {"endpoint": "accounts_day_book", "label": "Day Book", "active_endpoints": ["accounts_day_book"]},
            {"endpoint": "accounts_general_ledger", "label": "General Ledger", "active_endpoints": ["accounts_general_ledger", "ledger"]},
            {"endpoint": "accounts_gst_register", "label": "GST", "active_endpoints": ["accounts_gst_register", "account_gst"]},
            {"endpoint": "account_tds", "label": "TDS", "active_endpoints": ["account_tds", "accounts_tds_register"]},
            {"endpoint": "accounts_reports", "label": "Reports", "active_endpoints": ["accounts_reports"]},
        ],
    },
]


def accounts_sub_toolbar_sections() -> list[dict]:
    """Return grouped accounts sub-toolbar (no horizontal scroll grouping)."""
    return ACCOUNTS_SUBTOOLBAR_SECTIONS


# Context quick-panel links per active nav slug.
QUICK_PANEL_LINKS: dict[str, list[dict]] = {
    "project-management": [
        {"label": "New BOQ", "endpoint": "boq_management", "icon": "fa-table-list"},
        {"label": "New DPR", "endpoint": "dpr_entry", "icon": "fa-clipboard-list"},
        {"label": "New Bill", "endpoint": "client_billing_register", "icon": "fa-file-invoice-dollar"},
        {"label": "Project Dashboard", "endpoint": "projects_dashboard", "icon": "fa-gauge-high"},
    ],
    "store-procurement": [
        {"label": "New Material Request", "endpoint": "material_request", "icon": "fa-box"},
        {"label": "New Purchase Order", "endpoint": "purchase_orders", "icon": "fa-file-invoice"},
        {"label": "Store Dashboard", "endpoint": "store", "icon": "fa-warehouse"},
    ],
    "accounts-finance": [
        {"label": "Payment Voucher", "endpoint": "accounts_payments", "icon": "fa-money-bill-transfer"},
        {"label": "Receipt Voucher", "endpoint": "accounts_receipts", "icon": "fa-receipt"},
        {"label": "Accounts Hub", "endpoint": "accounts_hub", "icon": "fa-landmark"},
    ],
    "hr-payroll": [
        {"label": "New Employee", "endpoint": "staff", "icon": "fa-user-plus"},
        {"label": "Mark Attendance", "endpoint": "attendance", "icon": "fa-calendar-check"},
        {"label": "Run Payroll", "endpoint": "payroll", "icon": "fa-money-check-dollar"},
    ],
    "dashboard": [
        {"label": "Active Projects", "endpoint": "projects_dashboard", "icon": "fa-diagram-project"},
        {"label": "Pending Approvals", "endpoint": "approvals", "icon": "fa-clipboard-check"},
        {"label": "Notifications", "endpoint": "notifications", "icon": "fa-bell"},
    ],
}

# Badge keys for sub-toolbar items (endpoint → context key).
SUB_TOOLBAR_BADGE_KEYS: dict[str, str] = {
    "material_request": "material_request_count",
    "purchase_request": "purchase_request_count",
    "approvals": "approval_total",
}


def build_main_toolbar(nav_groups: list[dict]) -> list[dict]:
    """Build ordered main toolbar from NAV_GROUPS + virtual entries."""
    by_slug = {g["slug"]: dict(g) for g in nav_groups if g.get("slug")}
    by_slug.pop("plant-machinery", None)
    by_slug.pop("subcontract-management", None)
    by_slug.pop("approvals", None)
    by_slug.pop("erp-administration", None)

    toolbar: list[dict] = []
    for slug, label in MAIN_TOOLBAR_SLUGS:
        if slug in VIRTUAL_TOOLBAR_ENTRIES:
            entry = dict(VIRTUAL_TOOLBAR_ENTRIES[slug])
            entry["slug"] = slug
            entry["label"] = label
            toolbar.append(entry)
            continue
        group = by_slug.get(slug)
        if not group:
            continue
        group = dict(group)
        group["label"] = label
        toolbar.append(group)
    return toolbar


def filter_sub_toolbar_items(nav_group: dict | None) -> list[dict]:
    """Return sub-toolbar items aligned to UI standard where possible."""
    if not nav_group:
        return []
    slug = nav_group.get("slug", "")
    if slug in VIRTUAL_TOOLBAR_ENTRIES:
        return list(VIRTUAL_TOOLBAR_ENTRIES[slug].get("items", []))

    items = list(nav_group.get("items") or [])
    standard_labels = STANDARD_SUB_LABELS.get(slug)
    if not standard_labels:
        return items

    label_to_item: dict[str, dict] = {}
    for item in items:
        raw = item.get("label", "")
        canonical = SUB_LABEL_ALIASES.get(raw, raw)
        if canonical not in label_to_item:
            label_to_item[canonical] = dict(item)
            label_to_item[canonical]["label"] = canonical

    filtered: list[dict] = []
    for std_label in standard_labels:
        if std_label in label_to_item:
            filtered.append(label_to_item[std_label])
        else:
            for item in items:
                if item.get("label") == std_label:
                    filtered.append(item)
                    break
    return filtered if filtered else items


def quick_panel_for_slug(slug: str | None) -> list[dict]:
    if not slug:
        return QUICK_PANEL_LINKS.get("dashboard", [])
    return QUICK_PANEL_LINKS.get(slug, QUICK_PANEL_LINKS.get("dashboard", []))


def resolve_active_toolbar_slug(endpoint: str, nav_slug: str | None, nav_groups: list[dict]) -> str | None:
    """Map current route to main toolbar slug (including virtual entries)."""
    for vslug, ventry in VIRTUAL_TOOLBAR_ENTRIES.items():
        if endpoint in ventry.get("active_endpoints", []):
            return vslug
    for group in nav_groups:
        for item in group.get("items") or []:
            if endpoint in item.get("active_endpoints", []):
                return group.get("slug")
        if endpoint in group.get("active_endpoints", []):
            return group.get("slug")
    if nav_slug:
        return nav_slug
    return "dashboard"
