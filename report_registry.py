"""Central registry of standardized MAXEK ERP report types."""

from __future__ import annotations

from typing import Any

# status: wired = existing print route; stub = standard template placeholder; screen = on-screen only
REPORT_CATEGORIES: list[dict[str, Any]] = [
    {
        "slug": "engineering",
        "label": "Engineering",
        "icon": "fa-compass-drafting",
        "reports": [
            {"slug": "bbs_report", "label": "BBS Report", "status": "wired", "print_endpoint": "bbs_print", "print_param": "bbs_id", "doc_type_key": "boq_no"},
            {"slug": "dpr_report", "label": "DPR Report", "status": "stub", "doc_type_key": "dpr_no"},
            {"slug": "quantity_report", "label": "Quantity Report", "status": "stub", "doc_type_key": "boq_no"},
            {"slug": "progress_report", "label": "Progress Report", "status": "stub", "doc_type_key": "dpr_no"},
            {"slug": "measurement_sheet", "label": "Measurement Sheet", "status": "wired", "print_endpoint": "dpr_client_bill_print_one", "print_param": "measurement_id", "doc_type_key": "dpr_no"},
            {"slug": "material_reconciliation", "label": "Material Reconciliation", "status": "stub", "doc_type_key": "store_issue_no"},
        ],
    },
    {
        "slug": "billing",
        "label": "Billing",
        "icon": "fa-file-invoice-dollar",
        "reports": [
            {"slug": "client_ra_bill", "label": "Client RA Bill", "status": "wired", "print_endpoint": "client_billing_print", "print_param": "bill_id", "doc_type_key": "bill_no"},
            {"slug": "client_invoice", "label": "Client Invoice", "status": "wired", "print_endpoint": "client_billing_gst_print", "print_param": "gst_bill_id", "doc_type_key": "bill_no"},
            {"slug": "subcontractor_bill", "label": "Subcontractor Bill", "status": "wired", "print_endpoint": "sub_billing_print", "print_param": "bill_id", "doc_type_key": "bill_no"},
            {"slug": "work_order_bill", "label": "Work Order Bill", "status": "stub", "doc_type_key": "bill_no"},
            {"slug": "final_bill", "label": "Final Bill", "status": "stub", "doc_type_key": "bill_no"},
        ],
    },
    {
        "slug": "payroll",
        "label": "Payroll",
        "icon": "fa-money-check-dollar",
        "reports": [
            {"slug": "timesheet", "label": "Timesheet", "status": "wired", "print_endpoint": "employee_timesheets_print", "print_param": "timesheet_id", "doc_type_key": None},
            {"slug": "payroll_summary", "label": "Payroll Summary", "status": "wired", "print_endpoint": "payroll_print_run", "print_param": "run_id", "doc_type_key": None},
            {"slug": "salary_slip", "label": "Salary Slip", "status": "wired", "print_endpoint": "payroll_print_slip", "print_param": "line_id", "doc_type_key": None},
            {"slug": "wage_register", "label": "Wage Register", "status": "stub", "doc_type_key": None},
            {"slug": "attendance_register", "label": "Attendance Register", "status": "screen", "screen_endpoint": "reports", "doc_type_key": None},
            {"slug": "ot_register", "label": "OT Register", "status": "stub", "doc_type_key": None},
        ],
    },
    {
        "slug": "accounts",
        "label": "Accounts",
        "icon": "fa-landmark",
        "reports": [
            {"slug": "payment_voucher", "label": "Payment Voucher", "status": "stub", "doc_type_key": "payment_voucher_no"},
            {"slug": "receipt_voucher", "label": "Receipt Voucher", "status": "stub", "doc_type_key": "receipt_voucher_no"},
            {"slug": "journal_voucher", "label": "Journal Voucher", "status": "stub", "doc_type_key": None},
            {"slug": "petty_cash_voucher", "label": "Petty Cash Voucher", "status": "stub", "doc_type_key": None},
            {"slug": "gst_register", "label": "GST Register", "status": "stub", "doc_type_key": None},
            {"slug": "tds_register", "label": "TDS Register", "status": "stub", "doc_type_key": None},
        ],
    },
    {
        "slug": "stores",
        "label": "Stores",
        "icon": "fa-warehouse",
        "reports": [
            {"slug": "material_request", "label": "Material Request", "status": "stub", "doc_type_key": "pr_no"},
            {"slug": "purchase_requisition", "label": "Purchase Requisition", "status": "stub", "doc_type_key": "pr_no"},
            {"slug": "purchase_order", "label": "Purchase Order", "status": "wired", "print_endpoint": "purchase_order_print", "print_param": "po_id", "doc_type_key": "po_no"},
            {"slug": "grn", "label": "GRN", "status": "stub", "doc_type_key": "grn_no"},
            {"slug": "material_issue_note", "label": "Material Issue Note", "status": "stub", "doc_type_key": "store_issue_no"},
            {"slug": "stock_report", "label": "Stock Report", "status": "screen", "screen_endpoint": "inventory", "doc_type_key": None},
        ],
    },
    {
        "slug": "fleet_mechanical",
        "label": "Fleet & Mechanical",
        "icon": "fa-truck",
        "reports": [
            {"slug": "vehicle_log_book", "label": "Vehicle Log Book", "status": "wired", "print_endpoint": "fleet_vehicle_print", "print_param": "vehicle_id", "doc_type_key": None},
            {"slug": "fuel_register", "label": "Fuel Register", "status": "stub", "doc_type_key": None},
            {"slug": "maintenance_report", "label": "Maintenance Report", "status": "stub", "doc_type_key": None},
            {"slug": "breakdown_report", "label": "Breakdown Report", "status": "stub", "doc_type_key": None},
            {"slug": "tyre_register", "label": "Tyre Register", "status": "stub", "doc_type_key": None},
        ],
    },
    {
        "slug": "plant_operations",
        "label": "Plant Operations",
        "icon": "fa-industry",
        "reports": [
            {"slug": "asphalt_plant_production", "label": "Asphalt Plant Production Report", "status": "wired", "print_endpoint": "plant_asphalt_dispatch_print", "print_param": "dispatch_id", "doc_type_key": None},
            {"slug": "concrete_plant_production", "label": "Concrete Plant Production Report", "status": "wired", "print_endpoint": "plant_rmc_dispatch_print", "print_param": "dispatch_id", "doc_type_key": None},
            {"slug": "daily_plant_utilization", "label": "Daily Plant Utilization", "status": "stub", "doc_type_key": None},
            {"slug": "diesel_consumption", "label": "Diesel Consumption Report", "status": "stub", "doc_type_key": None},
        ],
    },
    {
        "slug": "management",
        "label": "Management",
        "icon": "fa-chart-line",
        "reports": [
            {"slug": "profit_loss", "label": "Profit & Loss", "status": "screen", "screen_endpoint": "accounts_reports", "doc_type_key": None},
            {"slug": "balance_sheet", "label": "Balance Sheet", "status": "screen", "screen_endpoint": "accounts_reports", "doc_type_key": None},
            {"slug": "trial_balance", "label": "Trial Balance", "status": "screen", "screen_endpoint": "accounts_reports", "doc_type_key": None},
            {"slug": "project_profitability", "label": "Project Profitability", "status": "screen", "screen_endpoint": "accounts_reports", "doc_type_key": None},
            {"slug": "cost_vs_budget", "label": "Cost vs Budget Report", "status": "screen", "screen_endpoint": "cost_planning_reports", "doc_type_key": None},
        ],
    },
]


def all_reports() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for cat in REPORT_CATEGORIES:
        for report in cat["reports"]:
            items.append({**report, "category": cat["label"], "category_slug": cat["slug"]})
    return items


def get_report_def(slug: str) -> dict[str, Any] | None:
    for item in all_reports():
        if item["slug"] == slug:
            return item
    return None


def reports_by_category() -> list[dict[str, Any]]:
    return REPORT_CATEGORIES


def count_by_status() -> dict[str, int]:
    counts = {"wired": 0, "stub": 0, "screen": 0}
    for item in all_reports():
        status = item.get("status", "stub")
        counts[status] = counts.get(status, 0) + 1
    return counts
