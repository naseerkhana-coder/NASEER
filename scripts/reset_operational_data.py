#!/usr/bin/env python3
"""Reset MAXEK ERP operational data while preserving master/lookup tables.

Does NOT run unless --confirm RESET is passed (or --dry-run to preview only).

Typical VPS usage (after backup):
  cd /var/www/maxek-erp-flask
  source venv/bin/activate
  python scripts/reset_operational_data.py --dry-run
  python scripts/reset_operational_data.py --confirm RESET --new-admin-password 'YourSecurePass!'
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

DEFAULT_DB = os.path.join(ROOT, "database", "maxek.db")

# Master / lookup / platform config — rows are kept (may be re-seeded idempotently).
KEEP_TABLES: frozenset[str] = frozenset({
    # HR / org lookups
    "designations",
    "departments",
    "trades",
    # Accounts master
    "chart_of_accounts",
    # Workflow configuration (not queue)
    "workflow_master",
    # DPR / QC reference masters
    "steel_shapes",
    "qc_tests",
    # App & platform configuration
    "app_settings",
    "erp_settings",
    "erp_customers",
    "erp_licenses",
    "erp_subscriptions",
    "erp_user_limits",
    "erp_branch_limits",
    "erp_storage_limits",
    # Document numbering definitions (counters reset separately)
    "number_sequences",
    "document_number_sequences",
    # Help / templates
    "help_topics",
    "corporate_report_templates",
    # Company country field config (schema metadata)
    "company_country_field_config",
    # SQLite internal
    "sqlite_sequence",
})

# Operational / transactional — DELETE FROM (order: child tables before parents).
CLEAR_TABLES: tuple[str, ...] = (
    # Attachments & audit (first — FK to many parents)
    "erp_attachments",
    "erp_record_audit",
    "account_attachments",
    "dpr_attachments",
    "petty_cash_attachments",
    "security_guarantee_attachments",
    "client_bill_attachments",
    "corporate_dms_versions",
    # Approvals & notifications
    "approval_audit",
    "approval_requests",
    "notifications",
    "user_maker_assignments",
    "user_page_activity",
    "user_idle_periods",
    "user_login_sessions",
    "user_work_context",
    "user_dashboard_preferences",
    "user_tab_permissions",
    # Platform ops logs (optional clear — support history)
    "erp_audit_logs",
    "erp_change_requests",
    "erp_support_tickets",
    "treasury_audit_log",
    "backup_runs",
    "system_alerts",
    # Payroll & HR transactional
    "payroll_lines",
    "payroll_runs",
    "payroll_records",
    "salary_payments",
    "salary_revisions",
    "staff_salary_increments",
    "staff_salary_components",
    "staff_travel_tiers",
    "staff_bonus",
    "salary",
    "holiday_applicability",
    "holidays",
    "staff_monthly_attendance",
    "employee_timesheet_days",
    "employee_monthly_timesheets",
    "attendance",
    "leave_requests",
    "daily_timesheets",
    "staff",
    "workers",
    # Subcontract
    "subcontract_payment_entries",
    "subcontract_work_orders",
    "subcontractor_bill_lines",
    "subcontractor_bills",
    "subcontractor_manpower_rates",
    "subcontractor_boq_rates",
    "subcontract_requests",
    "subcontractors",
    # Projects & engineering
    "bbs_lines",
    "bbs_reports",
    "project_client_bill_submissions",
    "project_guarantees",
    "security_guarantees",
    "client_gst_bill_lines",
    "client_gst_bills",
    "client_bill_deductions",
    "client_bill_extra_lines",
    "client_bill_lines",
    "client_bills",
    "project_photos",
    "project_documents",
    "equipment_cost_entries",
    "labour_productivity_entries",
    "project_claims",
    "project_contracts",
    "project_budgets",
    "micro_plan_entries",
    "cost_plan_machinery",
    "cost_plan_manpower",
    "cost_plan_materials",
    "cost_plan_activities",
    "cost_plans",
    "dpr_manpower",
    "dpr_steel_lines",
    "dpr_measurements",
    "dpr_entries",
    "boq_items",
    "boq_master",
    "manager_tasks",
    "project_expenses",
    "head_office_expenses",
    "projects",
    "clients",
    # Store & procurement
    "po_quotations",
    "material_transfer_lines",
    "material_transfers",
    "store_receipt_lines",
    "store_receipts",
    "store_issues",
    "purchase_order_lines",
    "purchase_orders",
    "purchase_requests",
    "material_requests",
    "stock_ledger",
    "vendor_documents",
    "materials",
    "vendors",
    # Accounts transactional
    "payment_allocations",
    "journal_entry_lines",
    "journal_entries",
    "receipt_vouchers",
    "payment_vouchers",
    "account_expense_lines",
    "account_expenses",
    "account_transactions",
    "gst_filing_periods",
    "tds_register",
    "pf_esi_register",
    "petty_cash_expenses",
    "petty_cash_transfers",
    "petty_cash_requests",
    "petty_cash",
    # Treasury
    "bank_documents",
    "payment_approval_matrix",
    "treasury_security_deposits",
    "letters_of_credit",
    "fixed_deposits",
    "pdc_register",
    "bank_cheques",
    "bank_reconciliation",
    "bank_overdrafts",
    "bank_guarantees",
    "bank_receipts",
    "bank_payments",
    "bank_accounts",
    # Plant / fleet / office
    "plant_maintenance_jobs",
    "plant_material_rates",
    "plant_qc_records",
    "crusher_production",
    "precast_dispatch",
    "precast_production",
    "wetmix_production",
    "rmc_dispatch",
    "rmc_production",
    "plant_stock",
    "asphalt_dispatch",
    "asphalt_production",
    "plants",
    "precast_yards",
    "fleet_breakdowns",
    "fleet_service_history",
    "diesel_ledger",
    "diesel_issues",
    "diesel_purchases",
    "fleet_running_log",
    "fleet_vehicle_documents",
    "fleet_vehicles",
    "office_legal_documents",
    "office_agreements",
    "office_quotation_lines",
    "office_quotations",
    "office_letters",
    "office_outward",
    "office_inward",
    "corporate_dms_documents",
    "corporate_dms_folders",
    "equipment_master",
    # Company master (operational entities — recreate per tenant)
    "company_documents",
    "company_directors_partners",
    "company_gst_registrations",
    "company_branches",
    "companies",
)

KEEP_USERNAMES: frozenset[str] = frozenset({"superadmin", "admin"})


def _list_tables(db: sqlite3.Connection) -> set[str]:
    rows = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {r[0] for r in rows}


def _table_exists(db: sqlite3.Connection, table: str) -> bool:
    row = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _count_rows(db: sqlite3.Connection, table: str) -> int:
    try:
        return int(db.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0])
    except sqlite3.Error:
        return -1


def _clear_table(db: sqlite3.Connection, table: str, *, dry_run: bool) -> int:
    if not _table_exists(db, table):
        return 0
    before = _count_rows(db, table)
    if before <= 0:
        return 0
    if not dry_run:
        db.execute(f"DELETE FROM [{table}]")
    return before


def _reset_sequence_tables(db: sqlite3.Connection, *, dry_run: bool) -> None:
    for table in ("number_sequences", "document_number_sequences"):
        if not _table_exists(db, table):
            continue
        cols = {r[1] for r in db.execute(f"PRAGMA table_info({table})").fetchall()}
        if "next_value" in cols and not dry_run:
            db.execute(f"UPDATE [{table}] SET next_value=1")
        elif "last_number" in cols and not dry_run:
            db.execute(f"UPDATE [{table}] SET last_number=0")


def _prune_users(
    db: sqlite3.Connection,
    *,
    dry_run: bool,
    new_admin_password: str | None,
) -> dict[str, int | str]:
    if not _table_exists(db, "users"):
        return {"removed": 0, "kept": 0}

    all_users = db.execute("SELECT id, username FROM users").fetchall()
    keep_ids = [r["id"] for r in all_users if r["username"] in KEEP_USERNAMES]
    remove_ids = [r["id"] for r in all_users if r["username"] not in KEEP_USERNAMES]

    stats: dict[str, int | str] = {
        "removed": len(remove_ids),
        "kept": len(keep_ids),
    }

    if not dry_run and remove_ids:
        placeholders = ",".join("?" * len(remove_ids))
        db.execute(f"DELETE FROM users WHERE id IN ({placeholders})", remove_ids)

    if new_admin_password and not dry_run:
        import bcrypt

        hashed = bcrypt.hashpw(
            new_admin_password.encode("utf-8"),
            bcrypt.gensalt(),
        ).decode("utf-8")
        db.execute(
            "UPDATE users SET password=?, status='Active' WHERE username='admin'",
            (hashed,),
        )
        stats["admin_password"] = "reset (bcrypt)"
    elif new_admin_password and dry_run:
        stats["admin_password"] = "would reset (bcrypt)"

    return stats


DEFAULT_DEPARTMENTS = (
    "Head Office",
    "Accounts",
    "Site Operations",
    "Store",
    "Purchase",
    "HR & Payroll",
    "Projects",
    "Management",
)


def _ensure_department_defaults(db: sqlite3.Connection) -> None:
    if not _table_exists(db, "departments"):
        return
    count = db.execute("SELECT COUNT(*) FROM departments").fetchone()[0]
    if int(count) == 0:
        db.executemany(
            "INSERT INTO departments(department_name, status) VALUES(?, 'Active')",
            [(name,) for name in DEFAULT_DEPARTMENTS],
        )


def _reseed_masters(db: sqlite3.Connection, *, dry_run: bool) -> list[str]:
    if dry_run:
        return ["would re-seed designations, departments, chart_of_accounts, workflow_master"]

    actions: list[str] = []
    try:
        _ensure_department_defaults(db)
        actions.append("departments: ensured defaults")
    except Exception as exc:
        actions.append(f"departments: skip ({exc})")

    try:
        from workflow_service import seed_designations, seed_workflow_master

        seed_designations(db)
        seed_workflow_master(db)
        actions.append("designations + workflow_master: re-seeded")
    except Exception as exc:
        actions.append(f"workflow seed: skip ({exc})")

    try:
        from accounts_service import seed_chart_of_accounts

        seed_chart_of_accounts(db)
        actions.append("chart_of_accounts: idempotent seed")
    except Exception as exc:
        actions.append(f"chart_of_accounts: skip ({exc})")

    return actions


def run_reset(
    db_path: str,
    *,
    dry_run: bool,
    confirm: str | None,
    new_admin_password: str | None,
    reseed: bool,
) -> int:
    if not os.path.isfile(db_path):
        print(f"ERROR: database not found: {db_path}")
        return 1

    if not dry_run and confirm != "RESET":
        print("ERROR: pass --confirm RESET to execute (or use --dry-run to preview).")
        return 1

    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    existing = _list_tables(db)
    unknown = sorted(existing - KEEP_TABLES - set(CLEAR_TABLES))
    if unknown:
        print("NOTE: tables present but not in KEEP/CLEAR lists (left unchanged):")
        for name in unknown:
            print(f"  ? {name} ({_count_rows(db, name)} rows)")

    print("=" * 60)
    print("MAXEK ERP — operational data reset")
    print("=" * 60)
    print(f"Database: {db_path}")
    print(f"Mode:     {'DRY RUN' if dry_run else 'LIVE RESET'}")
    print(f"Time:     {datetime.now().isoformat(timespec='seconds')}")
    print()

    cleared: list[tuple[str, int]] = []
    try:
        db.execute("PRAGMA foreign_keys=OFF")
        for table in CLEAR_TABLES:
            deleted = _clear_table(db, table, dry_run=dry_run)
            if deleted > 0:
                cleared.append((table, deleted))

        user_stats = _prune_users(
            db,
            dry_run=dry_run,
            new_admin_password=new_admin_password,
        )
        _reset_sequence_tables(db, dry_run=dry_run)

        reseed_actions: list[str] = []
        if reseed:
            reseed_actions = _reseed_masters(db, dry_run=dry_run)

        if not dry_run:
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.execute("PRAGMA foreign_keys=ON")
        db.close()

    print(f"Cleared {len(cleared)} tables:")
    for table, count in cleared:
        print(f"  - {table}: {count} rows")
    print()
    print("Users:")
    print(f"  removed: {user_stats.get('removed', 0)}")
    print(f"  kept (superadmin, admin): {user_stats.get('kept', 0)}")
    if user_stats.get("admin_password"):
        print(f"  admin password: {user_stats['admin_password']}")
    if reseed_actions:
        print()
        print("Re-seed:")
        for line in reseed_actions:
            print(f"  - {line}")

    print()
    if dry_run:
        print("DRY RUN complete — no changes written.")
    else:
        print("RESET complete. Restart gunicorn/systemd and verify login.")
    print("=" * 60)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset MAXEK ERP operational data")
    parser.add_argument(
        "--db",
        default=os.environ.get("MAXEK_DB_PATH", DEFAULT_DB),
        help=f"Path to maxek.db (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview counts only; do not modify the database",
    )
    parser.add_argument(
        "--confirm",
        metavar="RESET",
        help="Required for live run: --confirm RESET",
    )
    parser.add_argument(
        "--new-admin-password",
        help="Set bcrypt password for username 'admin' after reset",
    )
    parser.add_argument(
        "--no-reseed",
        action="store_true",
        help="Skip idempotent master re-seed (designations, departments, COA, workflow)",
    )
    args = parser.parse_args()

    return run_reset(
        args.db,
        dry_run=args.dry_run,
        confirm=args.confirm,
        new_admin_password=args.new_admin_password,
        reseed=not args.no_reseed,
    )


if __name__ == "__main__":
    raise SystemExit(main())
