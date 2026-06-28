#!/usr/bin/env python3
"""Roll out erp_module_toolbar mode='standard' to base_maxek list/CRUD templates."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"

# Hub / dashboard / form-only / print — no standard list toolbar
SKIP = {
    "templates/dashboard.html",
    "templates/department_dashboard.html",
    "templates/department_hub.html",
    "templates/department_workspace.html",
    "templates/module_placeholder.html",
    "templates/module_request.html",
    "templates/notifications.html",
    "templates/approval_detail.html",
    "templates/report_verify.html",
    "templates/employee_profile.html",
    "templates/help_contact.html",
    "templates/help_desk.html",
    "templates/help_desk_admin.html",
    "templates/erp_admin/platform_dashboard.html",
    "templates/treasury/hub.html",
    "templates/treasury/command_center.html",
    "templates/treasury/control_center.html",
    "templates/treasury/daily_dashboard.html",
    "templates/treasury/coming_soon.html",
    "templates/treasury/account_dashboard.html",
    "templates/accounts_hub.html",
    "templates/fleet_dashboard.html",
    "templates/plant_dashboard.html",
    "templates/office_dashboard.html",
    "templates/store_dashboard.html",
    "templates/corporate_reports_hub.html",
    "templates/treasury/cash_flow_forecast.html",
    "templates/treasury/project_profitability_detail.html",
    "templates/treasury/labour_productivity_detail.html",
    "templates/treasury/equipment_detail.html",
    "templates/treasury/fd_view.html",
    "templates/treasury/pdc_view.html",
    "templates/treasury/cheque_view.html",
    "templates/treasury/contract_view.html",
    "templates/treasury/claim_view.html",
    "templates/treasury/document_view.html",
    "templates/treasury/account_360.html",
    "templates/client_billing_form.html",
    "templates/client_billing_gst_form.html",
    "templates/sub_billing_form.html",
    "templates/bbs_form.html",
    "templates/boq_multiple_entry.html",
    "templates/employee_timesheet_form.html",
    "templates/treasury/budget_form.html",
    "templates/treasury/cheque_form.html",
    "templates/treasury/claim_form.html",
    "templates/treasury/contract_form.html",
    "templates/treasury/cost_entry_form.html",
    "templates/treasury/equipment_form.html",
    "templates/treasury/fd_form.html",
    "templates/treasury/labour_productivity_form.html",
    "templates/treasury/numbering_config_form.html",
    "templates/treasury/pdc_form.html",
    "templates/treasury/document_upload.html",
    "templates/erp_admin/customer_settings.html",
}

# Per-template toolbar configuration (relative to ROOT)
TOOLBAR: dict[str, dict] = {
    "templates/clients.html": {
        "search_placeholder": "Search clients...",
        "export_name": "clients",
        "print_target": "#client-records",
        "form_panel_id": "add-client",
        "table_panel_id": "client-records",
        "new_url": "url_for('clients') ~ '#add-client'",
    },
    "templates/purchase_vendors.html": {
        "search_placeholder": "Search vendors...",
        "export_name": "vendors",
        "print_target": "#vendor-records",
        "form_panel_id": "add-vendor",
        "table_panel_id": "vendor-records",
        "new_url": "url_for('purchase_vendors') ~ '#add-vendor'",
        "settings_url": "url_for('subcontractors')",
    },
    "templates/subcontractors.html": {
        "search_placeholder": "Search subcontractors...",
        "export_name": "subcontractors",
        "print_target": "#subcontractor-records",
        "form_panel_id": "add-subcontractor",
        "table_panel_id": "subcontractor-records",
        "new_url": "url_for('subcontractors') ~ 'add-subcontractor'",
        "reports_url": "url_for('sub_billing_register')",
    },
    "templates/workers.html": {
        "search_placeholder": "Search workers...",
        "export_name": "workers",
        "print_target": "#worker-records",
        "form_panel_id": "add-worker",
        "table_panel_id": "worker-records",
        "new_url": "url_for('workers') ~ 'add-worker'",
    },
    "templates/users.html": {
        "search_placeholder": "Search users...",
        "export_name": "users",
        "print_target": "#user-records",
        "form_panel_id": "user-form",
        "table_panel_id": "user-records",
        "new_url": "url_for('user_settings') ~ 'user-form'",
        "settings_url": "url_for('settings')",
    },
    "templates/user_management.html": {
        "search_placeholder": "Search users...",
        "export_name": "user_management",
        "print_target": "#user-mgmt-records",
        "form_panel_id": "user-mgmt-form",
        "table_panel_id": "user-mgmt-records",
        "new_url": "url_for('user_management') ~ 'user-mgmt-form'",
    },
    "templates/company_master.html": {
        "search_placeholder": "Search companies...",
        "search_name": "q",
        "export_name": "companies",
        "print_target": "#company-records",
        "table_panel_id": "company-records",
        "form_panel_id": "company-form",
        "new_url": "url_for('company_master', new=1) ~ 'company-form'",
        "settings_url": "url_for('settings')",
    },
    "templates/settings.html": {
        "search_placeholder": "Search settings modules...",
        "export_name": "settings",
        "print_target": "#settings-modules",
        "table_panel_id": "settings-modules",
        "show_run_report": False,
        "print_enabled": False,
    },
    "templates/petty_cash.html": {
        "search_placeholder": "Search petty cash requests...",
        "export_name": "petty_cash",
        "print_target": "#petty-cash-records",
        "form_panel_id": "new-request",
        "table_panel_id": "petty-cash-records",
        "new_url": "url_for('petty_cash', new=1) ~ 'new-request'",
        "filter_status_options": ["Draft", "Pending Checker", "Pending Approval", "Approved", "Rejected by Checker", "Rejected by Approver"],
        "hide_unless": "not view_record",
    },
    "templates/accounts_expenses.html": {
        "search_placeholder": "Search expenses...",
        "export_name": "accounts_expenses",
        "print_target": "#expense-records",
        "form_panel_id": "expense-form",
        "table_panel_id": "expense-records",
        "new_url": "url_for('accounts_expenses', new=1) ~ 'expense-form'",
        "reports_url": "url_for('accounts_reports')",
        "filter_status_options": ["Pending Checker", "Pending Approval", "Approved", "Rejected by Checker", "Rejected by Approver"],
        "hide_unless": "not view_record",
    },
    "templates/accounts_receipt_voucher.html": {
        "search_placeholder": "Search receipts...",
        "export_name": "receipt_vouchers",
        "print_target": "#receipt-records",
        "form_panel_id": "receipt-form",
        "table_panel_id": "receipt-records",
        "new_url": "url_for('accounts_receipt_voucher', new=1) ~ 'receipt-form'",
        "filter_status_options": ["Pending Checker", "Pending Approval", "Approved", "Rejected by Checker", "Rejected by Approver"],
        "hide_unless": "not view_record",
    },
    "templates/accounts_chart_of_accounts.html": {
        "search_placeholder": "Search chart of accounts...",
        "export_name": "chart_of_accounts",
        "print_target": "#coa-records",
        "form_panel_id": "coa-form",
        "table_panel_id": "coa-records",
        "new_url": "url_for('accounts_chart_of_accounts') ~ 'coa-form'",
    },
    "templates/accounts_gst_register.html": {
        "search_placeholder": "Search GST entries...",
        "export_name": "gst_register",
        "print_target": "#gst-records",
        "table_panel_id": "gst-records",
        "reports_url": "url_for('accounts_reports')",
    },
    "templates/accounts_tds_register.html": {
        "search_placeholder": "Search TDS entries...",
        "export_name": "tds_register",
        "print_target": "#tds-records",
        "table_panel_id": "tds-records",
        "reports_url": "url_for('accounts_reports')",
    },
    "templates/accounts_book.html": {
        "search_placeholder": "Search journal entries...",
        "export_name": "accounts_book",
        "print_target": "#journal-records",
        "form_panel_id": "journal-form",
        "table_panel_id": "journal-records",
        "new_url": "url_for('accounts_book', new=1) ~ 'journal-form'",
    },
    "templates/accounts_book_v2.html": {
        "search_placeholder": "Search journal entries...",
        "export_name": "accounts_book_v2",
        "print_target": "#journal-records",
        "form_panel_id": "journal-form",
        "table_panel_id": "journal-records",
        "new_url": "url_for('accounts_book_v2', new=1) ~ 'journal-form'",
    },
    "templates/accounts_reports.html": {
        "search_placeholder": "Search reports...",
        "export_name": "accounts_reports",
        "print_target": "#accounts-reports",
        "table_panel_id": "accounts-reports",
        "show_run_report": True,
    },
    "templates/accounts_party_ledger.html": {
        "search_placeholder": "Search party ledger...",
        "export_name": "party_ledger",
        "print_target": "#party-ledger",
        "table_panel_id": "party-ledger",
        "show_run_report": True,
    },
    "templates/accounts_pf_esi_register.html": {
        "search_placeholder": "Search PF/ESI...",
        "export_name": "pf_esi",
        "print_target": "#pf-esi-records",
        "table_panel_id": "pf-esi-records",
    },
    "templates/accounts_tally_export.html": {
        "search_placeholder": "Filter export batches...",
        "export_name": "tally_export",
        "print_target": "#tally-export-records",
        "table_panel_id": "tally-export-records",
    },
    "templates/timesheet.html": {
        "search_placeholder": "Search timesheets...",
        "export_name": "timesheets",
        "print_target": "#timesheet-records",
        "form_panel_id": "add-attendance",
        "table_panel_id": "timesheet-records",
        "new_url": "url_for('timesheet') ~ 'add-attendance'",
        "filter_status_options": ["Pending Checker", "Pending Approval", "Approved", "Rejected by Checker", "Rejected by Approver"],
        "hide_unless": "not view_record",
    },
    "templates/salary.html": {
        "search_placeholder": "Search salary records...",
        "export_name": "salary",
        "print_target": "#salary-records",
        "table_panel_id": "salary-records",
        "reports_url": "url_for('payroll')",
    },
    "templates/fleet_running_log.html": {
        "search_placeholder": "Search running log...",
        "export_name": "fleet_running_log",
        "print_target": "#running-log-records",
        "form_panel_id": "log-form",
        "table_panel_id": "running-log-records",
        "new_url": "url_for('fleet_running_log', new=1) ~ 'log-form'",
        "reports_url": "url_for('fleet_vehicles')",
    },
    "templates/fleet_diesel_stock.html": {
        "search_placeholder": "Search diesel stock...",
        "export_name": "diesel_stock",
        "print_target": "#diesel-stock-records",
        "table_panel_id": "diesel-stock-records",
    },
    "templates/fleet_diesel_purchase.html": {
        "search_placeholder": "Search diesel purchases...",
        "export_name": "diesel_purchase",
        "print_target": "#diesel-purchase-records",
        "form_panel_id": "diesel-purchase-form",
        "table_panel_id": "diesel-purchase-records",
        "new_url": "url_for('fleet_diesel_purchase', new=1) ~ 'diesel-purchase-form'",
    },
    "templates/fleet_diesel_issue.html": {
        "search_placeholder": "Search diesel issues...",
        "export_name": "diesel_issue",
        "print_target": "#diesel-issue-records",
        "form_panel_id": "diesel-issue-form",
        "table_panel_id": "diesel-issue-records",
        "new_url": "url_for('fleet_diesel_issue', new=1) ~ 'diesel-issue-form'",
    },
    "templates/fleet_vehicle_documents.html": {
        "search_placeholder": "Search vehicle documents...",
        "export_name": "vehicle_documents",
        "print_target": "#vehicle-doc-records",
        "table_panel_id": "vehicle-doc-records",
    },
    "templates/plant_rmc_production.html": {
        "search_placeholder": "Search RMC production...",
        "export_name": "rmc_production",
        "print_target": "#rmc-production-records",
        "form_panel_id": "production-form",
        "table_panel_id": "rmc-production-records",
        "new_url": "url_for('plant_rmc_production', new=1) ~ 'production-form'",
    },
    "templates/plant_rmc_dispatch.html": {
        "search_placeholder": "Search RMC dispatch...",
        "export_name": "rmc_dispatch",
        "print_target": "#rmc-dispatch-records",
        "form_panel_id": "dispatch-form",
        "table_panel_id": "rmc-dispatch-records",
        "new_url": "url_for('plant_rmc_dispatch', new=1) ~ 'dispatch-form'",
    },
    "templates/plant_asphalt_production.html": {
        "search_placeholder": "Search asphalt production...",
        "export_name": "asphalt_production",
        "print_target": "#asphalt-production-records",
        "form_panel_id": "production-form",
        "table_panel_id": "asphalt-production-records",
        "new_url": "url_for('plant_asphalt_production', new=1) ~ 'production-form'",
    },
    "templates/plant_asphalt_dispatch.html": {
        "search_placeholder": "Search asphalt dispatch...",
        "export_name": "asphalt_dispatch",
        "print_target": "#asphalt-dispatch-records",
        "form_panel_id": "dispatch-form",
        "table_panel_id": "asphalt-dispatch-records",
        "new_url": "url_for('plant_asphalt_dispatch', new=1) ~ 'dispatch-form'",
    },
    "templates/plant_precast_production.html": {
        "search_placeholder": "Search precast production...",
        "export_name": "precast_production",
        "print_target": "#precast-production-records",
        "form_panel_id": "production-form",
        "table_panel_id": "precast-production-records",
        "new_url": "url_for('plant_precast_production', new=1) ~ 'production-form'",
    },
    "templates/plant_precast_dispatch.html": {
        "search_placeholder": "Search precast dispatch...",
        "export_name": "precast_dispatch",
        "print_target": "#precast-dispatch-records",
        "form_panel_id": "dispatch-form",
        "table_panel_id": "precast-dispatch-records",
        "new_url": "url_for('plant_precast_dispatch', new=1) ~ 'dispatch-form'",
    },
    "templates/plant_crusher_production.html": {
        "search_placeholder": "Search crusher production...",
        "export_name": "crusher_production",
        "print_target": "#crusher-production-records",
        "form_panel_id": "production-form",
        "table_panel_id": "crusher-production-records",
        "new_url": "url_for('plant_crusher_production', new=1) ~ 'production-form'",
    },
    "templates/plant_wetmix_production.html": {
        "search_placeholder": "Search wet mix production...",
        "export_name": "wetmix_production",
        "print_target": "#wetmix-production-records",
        "form_panel_id": "production-form",
        "table_panel_id": "wetmix-production-records",
        "new_url": "url_for('plant_wetmix_production', new=1) ~ 'production-form'",
    },
    "templates/plant_qc.html": {
        "search_placeholder": "Search QC records...",
        "export_name": "plant_qc",
        "print_target": "#plant-qc-records",
        "form_panel_id": "qc-form",
        "table_panel_id": "plant-qc-records",
        "new_url": "url_for('plant_qc', new=1) ~ 'qc-form'",
    },
    "templates/plant_maintenance.html": {
        "search_placeholder": "Search maintenance...",
        "export_name": "plant_maintenance",
        "print_target": "#maintenance-records",
        "form_panel_id": "maintenance-form",
        "table_panel_id": "maintenance-records",
        "new_url": "url_for('plant_maintenance', new=1) ~ 'maintenance-form'",
    },
    "templates/plant_costing.html": {
        "search_placeholder": "Search plant costing...",
        "export_name": "plant_costing",
        "print_target": "#plant-costing-records",
        "table_panel_id": "plant-costing-records",
        "show_run_report": True,
    },
    "templates/plant_360.html": {
        "search_placeholder": "Search plant overview...",
        "export_name": "plant_360",
        "print_target": "#plant-360-records",
        "table_panel_id": "plant-360-records",
    },
    "templates/office_inward.html": {
        "search_placeholder": "Search inward register...",
        "export_name": "office_inward",
        "print_target": "#inward-records",
        "form_panel_id": "inward-form",
        "table_panel_id": "inward-records",
        "new_url": "url_for('office_inward', new=1) ~ 'inward-form'",
    },
    "templates/office_outward.html": {
        "search_placeholder": "Search outward register...",
        "export_name": "office_outward",
        "print_target": "#outward-records",
        "form_panel_id": "outward-form",
        "table_panel_id": "outward-records",
        "new_url": "url_for('office_outward', new=1) ~ 'outward-form'",
    },
    "templates/office_letters.html": {
        "search_placeholder": "Search letters...",
        "export_name": "office_letters",
        "print_target": "#letters-records",
        "form_panel_id": "letter-form",
        "table_panel_id": "letters-records",
        "new_url": "url_for('office_letters', new=1) ~ 'letter-form'",
    },
    "templates/office_legal.html": {
        "search_placeholder": "Search legal records...",
        "export_name": "office_legal",
        "print_target": "#legal-records",
        "form_panel_id": "legal-form",
        "table_panel_id": "legal-records",
        "new_url": "url_for('office_legal', new=1) ~ 'legal-form'",
    },
    "templates/office_agreements.html": {
        "search_placeholder": "Search agreements...",
        "export_name": "office_agreements",
        "print_target": "#agreements-records",
        "form_panel_id": "agreement-form",
        "table_panel_id": "agreements-records",
        "new_url": "url_for('office_agreements', new=1) ~ 'agreement-form'",
    },
    "templates/office_quotations.html": {
        "search_placeholder": "Search quotations...",
        "export_name": "office_quotations",
        "print_target": "#quotations-records",
        "form_panel_id": "quotation-form",
        "table_panel_id": "quotations-records",
        "new_url": "url_for('office_quotations', new=1) ~ 'quotation-form'",
    },
    "templates/office_po_register.html": {
        "search_placeholder": "Search PO register...",
        "export_name": "office_po",
        "print_target": "#po-records",
        "table_panel_id": "po-records",
    },
    "templates/client_billing_register.html": {
        "search_placeholder": "Search client bills...",
        "search_name": "q",
        "export_name": "client_billing",
        "print_target": "#client-billing-records",
        "table_panel_id": "client-billing-records",
        "new_url": "url_for('client_billing_form', new=1)",
        "reports_url": "url_for('client_billing_reports')",
        "filter_status_options": ["Pending Checker", "Pending Approval", "Approved", "Rejected by Checker", "Rejected by Approver"],
    },
    "templates/client_billing_reports.html": {
        "search_placeholder": "Search billing reports...",
        "export_name": "client_billing_reports",
        "print_target": "#billing-reports",
        "table_panel_id": "billing-reports",
        "show_run_report": True,
    },
    "templates/sub_billing_register.html": {
        "search_placeholder": "Search sub bills...",
        "export_name": "sub_billing",
        "print_target": "#sub-billing-records",
        "table_panel_id": "sub-billing-records",
        "new_url": "url_for('sub_billing_form', new=1)",
        "filter_status_options": ["Pending Checker", "Pending Approval", "Approved", "Rejected by Checker", "Rejected by Approver"],
    },
    "templates/subcontract_payments.html": {
        "search_placeholder": "Search subcontract payments...",
        "export_name": "subcontract_payments",
        "print_target": "#sub-payments-records",
        "table_panel_id": "sub-payments-records",
    },
    "templates/corporate_dms_register.html": {
        "search_placeholder": "Search documents...",
        "search_name": "q",
        "export_name": "corporate_dms",
        "print_target": "#dms-records",
        "table_panel_id": "dms-records",
        "add_trigger_selector": "#dms-upload-trigger",
    },
    "templates/corporate_template_master.html": {
        "search_placeholder": "Search templates...",
        "export_name": "corporate_templates",
        "print_target": "#template-records",
        "form_panel_id": "template-form",
        "table_panel_id": "template-records",
        "new_url": "url_for('corporate_template_master') ~ 'template-form'",
    },
    "templates/store_inventory.html": {
        "search_placeholder": "Search inventory...",
        "export_name": "store_inventory",
        "print_target": "#inventory-records",
        "table_panel_id": "inventory-records",
    },
    "templates/store_issue.html": {
        "search_placeholder": "Search issue notes...",
        "export_name": "store_issue",
        "print_target": "#issue-records",
        "form_panel_id": "issue-form",
        "table_panel_id": "issue-records",
        "new_url": "url_for('store_issue', new=1) ~ 'issue-form'",
    },
    "templates/material_transfer.html": {
        "search_placeholder": "Search transfers...",
        "export_name": "material_transfer",
        "print_target": "#transfer-records",
        "form_panel_id": "transfer-form",
        "table_panel_id": "transfer-records",
        "new_url": "url_for('material_transfer', new=1) ~ 'transfer-form'",
    },
    "templates/advances.html": {
        "search_placeholder": "Search advances...",
        "export_name": "advances",
        "print_target": "#advance-records",
        "form_panel_id": "advance-form",
        "table_panel_id": "advance-records",
        "new_url": "url_for('advances', new=1) ~ 'advance-form'",
    },
    "templates/bbs_register.html": {
        "search_placeholder": "Search BBS records...",
        "export_name": "bbs_register",
        "print_target": "#bbs-records",
        "table_panel_id": "bbs-records",
        "new_url": "url_for('bbs_form', new=1)",
    },
    "templates/project_documents_register.html": {
        "search_placeholder": "Search project documents...",
        "export_name": "project_documents",
        "print_target": "#project-doc-records",
        "table_panel_id": "project-doc-records",
    },
    "templates/project_photos_register.html": {
        "search_placeholder": "Search photo albums...",
        "export_name": "project_photos",
        "print_target": "#photo-records",
        "table_panel_id": "photo-records",
    },
    "templates/project_photos_reports.html": {
        "search_placeholder": "Search photo reports...",
        "export_name": "project_photos_reports",
        "print_target": "#photo-reports",
        "table_panel_id": "photo-reports",
        "show_run_report": True,
    },
    "templates/project_photos_timeline.html": {
        "search_placeholder": "Filter timeline...",
        "export_name": "project_photos_timeline",
        "print_target": "#photo-timeline",
        "table_panel_id": "photo-timeline",
    },
    "templates/precast_yard.html": {
        "search_placeholder": "Search precast yard...",
        "export_name": "precast_yard",
        "print_target": "#precast-yard-records",
        "table_panel_id": "precast-yard-records",
    },
    "templates/precast_yard_yards.html": {
        "search_placeholder": "Search yards...",
        "export_name": "precast_yards",
        "print_target": "#yards-records",
        "table_panel_id": "yards-records",
    },
    "templates/securities_guarantees.html": {
        "search_placeholder": "Search securities...",
        "export_name": "securities",
        "print_target": "#securities-records",
        "table_panel_id": "securities-records",
    },
    "templates/head_office_expenses.html": {
        "search_placeholder": "Search HO expenses...",
        "export_name": "ho_expenses",
        "print_target": "#ho-expense-records",
        "table_panel_id": "ho-expense-records",
    },
    "templates/staff_bonus.html": {
        "search_placeholder": "Search bonus records...",
        "export_name": "staff_bonus",
        "print_target": "#bonus-records",
        "table_panel_id": "bonus-records",
    },
    "templates/payroll_revisions.html": {
        "search_placeholder": "Search payroll revisions...",
        "export_name": "payroll_revisions",
        "print_target": "#revision-records",
        "table_panel_id": "revision-records",
    },
    "templates/payroll_payments.html": {
        "search_placeholder": "Search payroll payments...",
        "export_name": "payroll_payments",
        "print_target": "#payment-records",
        "table_panel_id": "payment-records",
    },
    "templates/payroll_holidays.html": {
        "search_placeholder": "Search holidays...",
        "export_name": "payroll_holidays",
        "print_target": "#holiday-records",
        "form_panel_id": "holiday-form",
        "table_panel_id": "holiday-records",
        "new_url": "url_for('payroll_holidays') ~ 'holiday-form'",
    },
    "templates/employee_timesheets.html": {
        "search_placeholder": "Search employee timesheets...",
        "export_name": "employee_timesheets",
        "print_target": "#emp-timesheet-records",
        "table_panel_id": "emp-timesheet-records",
    },
    "templates/user_activity.html": {
        "search_placeholder": "Search activity log...",
        "export_name": "user_activity",
        "print_target": "#activity-records",
        "table_panel_id": "activity-records",
    },
    "templates/workflow_settings.html": {
        "search_placeholder": "Search workflow modules...",
        "export_name": "workflow_settings",
        "print_target": "#workflow-modules",
        "table_panel_id": "workflow-modules",
    },
    "templates/workflow_audit_report.html": {
        "search_placeholder": "Search audit entries...",
        "export_name": "workflow_audit",
        "print_target": "#workflow-audit-records",
        "table_panel_id": "workflow-audit-records",
        "show_run_report": True,
    },
    "templates/approvals.html": {
        "search_placeholder": "Search approvals...",
        "export_name": "approvals",
        "print_target": "#approval-records",
        "table_panel_id": "approval-records",
    },
    "templates/cost_planning_reports.html": {
        "search_placeholder": "Search cost reports...",
        "export_name": "cost_planning_reports",
        "print_target": "#cost-reports",
        "table_panel_id": "cost-reports",
        "show_run_report": True,
    },
    "templates/erp_admin/licenses.html": {
        "search_placeholder": "Search licenses...",
        "export_name": "licenses",
        "print_target": "#license-records",
        "form_panel_id": "license-form",
        "table_panel_id": "license-records",
        "new_url": "url_for('erp_admin_licenses') ~ 'license-form'",
    },
    "templates/erp_admin/limits.html": {
        "search_placeholder": "Search limits...",
        "export_name": "limits",
        "print_target": "#limits-records",
        "table_panel_id": "limits-records",
    },
    "templates/erp_admin/subscriptions.html": {
        "search_placeholder": "Search subscriptions...",
        "export_name": "subscriptions",
        "print_target": "#subscription-records",
        "table_panel_id": "subscription-records",
    },
    "templates/erp_admin/support_tickets.html": {
        "search_placeholder": "Search support tickets...",
        "export_name": "support_tickets",
        "print_target": "#ticket-records",
        "table_panel_id": "ticket-records",
    },
    "templates/erp_admin/audit_logs.html": {
        "search_placeholder": "Search audit logs...",
        "export_name": "audit_logs",
        "print_target": "#audit-records",
        "table_panel_id": "audit-records",
    },
    "templates/erp_admin/change_requests.html": {
        "search_placeholder": "Search change requests...",
        "export_name": "change_requests",
        "print_target": "#change-request-records",
        "table_panel_id": "change-request-records",
    },
    "templates/erp_admin/login_monitoring.html": {
        "search_placeholder": "Search login events...",
        "export_name": "login_monitoring",
        "print_target": "#login-records",
        "table_panel_id": "login-records",
    },
    "templates/erp_admin/system_health.html": {
        "search_placeholder": "Filter health checks...",
        "export_name": "system_health",
        "print_target": "#health-records",
        "table_panel_id": "health-records",
    },
    "templates/erp_admin/settings.html": {
        "search_placeholder": "Search platform settings...",
        "export_name": "erp_admin_settings",
        "print_target": "#platform-settings",
        "table_panel_id": "platform-settings",
    },
    "templates/treasury/bank_accounts.html": {
        "search_placeholder": "Search bank accounts...",
        "export_name": "bank_accounts",
        "print_target": "#bank-account-records",
        "table_panel_id": "bank-account-records",
    },
    "templates/treasury/payments.html": {
        "search_placeholder": "Search payments...",
        "export_name": "treasury_payments",
        "print_target": "#treasury-payment-records",
        "table_panel_id": "treasury-payment-records",
    },
    "templates/treasury/receipts.html": {
        "search_placeholder": "Search receipts...",
        "export_name": "treasury_receipts",
        "print_target": "#treasury-receipt-records",
        "table_panel_id": "treasury-receipt-records",
    },
    "templates/treasury/reconciliation.html": {
        "search_placeholder": "Search reconciliation...",
        "export_name": "reconciliation",
        "print_target": "#reconciliation-records",
        "table_panel_id": "reconciliation-records",
    },
    "templates/treasury/bank_guarantees.html": {
        "search_placeholder": "Search bank guarantees...",
        "export_name": "bank_guarantees",
        "print_target": "#bg-records",
        "table_panel_id": "bg-records",
    },
    "templates/treasury/security_deposits.html": {
        "search_placeholder": "Search security deposits...",
        "export_name": "security_deposits",
        "print_target": "#sd-records",
        "table_panel_id": "sd-records",
    },
    "templates/treasury/letters_of_credit.html": {
        "search_placeholder": "Search letters of credit...",
        "export_name": "letters_of_credit",
        "print_target": "#lc-records",
        "table_panel_id": "lc-records",
    },
    "templates/treasury/overdrafts.html": {
        "search_placeholder": "Search overdrafts...",
        "export_name": "overdrafts",
        "print_target": "#od-records",
        "table_panel_id": "od-records",
    },
    "templates/treasury/fixed_deposits.html": {
        "search_placeholder": "Search fixed deposits...",
        "export_name": "fixed_deposits",
        "print_target": "#fd-records",
        "table_panel_id": "fd-records",
    },
    "templates/treasury/pdc_register.html": {
        "search_placeholder": "Search PDC register...",
        "export_name": "pdc_register",
        "print_target": "#pdc-records",
        "table_panel_id": "pdc-records",
    },
    "templates/treasury/cheques.html": {
        "search_placeholder": "Search cheques...",
        "export_name": "cheques",
        "print_target": "#cheque-records",
        "table_panel_id": "cheque-records",
    },
    "templates/treasury/document_vault.html": {
        "search_placeholder": "Search document vault...",
        "export_name": "document_vault",
        "print_target": "#vault-records",
        "table_panel_id": "vault-records",
    },
    "templates/treasury/document_numbering.html": {
        "search_placeholder": "Search numbering rules...",
        "export_name": "document_numbering",
        "print_target": "#numbering-records",
        "table_panel_id": "numbering-records",
    },
    "templates/treasury/contract_management.html": {
        "search_placeholder": "Search contracts...",
        "export_name": "contracts",
        "print_target": "#contract-records",
        "table_panel_id": "contract-records",
    },
    "templates/treasury/project_contracts.html": {
        "search_placeholder": "Search project contracts...",
        "export_name": "project_contracts",
        "print_target": "#project-contract-records",
        "table_panel_id": "project-contract-records",
    },
    "templates/treasury/claims.html": {
        "search_placeholder": "Search claims...",
        "export_name": "claims",
        "print_target": "#claim-records",
        "table_panel_id": "claim-records",
    },
    "templates/treasury/budget_control.html": {
        "search_placeholder": "Search budget control...",
        "export_name": "budget_control",
        "print_target": "#budget-control-records",
        "table_panel_id": "budget-control-records",
    },
    "templates/treasury/project_budget.html": {
        "search_placeholder": "Search project budgets...",
        "export_name": "project_budget",
        "print_target": "#project-budget-records",
        "table_panel_id": "project-budget-records",
    },
    "templates/treasury/project_profitability.html": {
        "search_placeholder": "Search profitability...",
        "export_name": "project_profitability",
        "print_target": "#profitability-records",
        "table_panel_id": "profitability-records",
        "show_run_report": True,
    },
    "templates/treasury/project_labour_summary.html": {
        "search_placeholder": "Search labour summary...",
        "export_name": "labour_summary",
        "print_target": "#labour-summary-records",
        "table_panel_id": "labour-summary-records",
        "show_run_report": True,
    },
    "templates/treasury/labour_productivity.html": {
        "search_placeholder": "Search productivity...",
        "export_name": "labour_productivity",
        "print_target": "#productivity-records",
        "table_panel_id": "productivity-records",
    },
    "templates/treasury/equipment_costing.html": {
        "search_placeholder": "Search equipment costing...",
        "export_name": "equipment_costing",
        "print_target": "#equipment-cost-records",
        "table_panel_id": "equipment-cost-records",
    },
    "templates/treasury/reports.html": {
        "search_placeholder": "Search treasury reports...",
        "export_name": "treasury_reports",
        "print_target": "#treasury-reports",
        "table_panel_id": "treasury-reports",
        "show_run_report": True,
    },
    "templates/treasury/alert_engine.html": {
        "search_placeholder": "Search alerts...",
        "export_name": "alert_engine",
        "print_target": "#alert-records",
        "table_panel_id": "alert-records",
    },
    "templates/treasury/alert_settings.html": {
        "search_placeholder": "Search alert settings...",
        "export_name": "alert_settings",
        "print_target": "#alert-settings-records",
        "table_panel_id": "alert-settings-records",
    },
    "templates/treasury/backup_system.html": {
        "search_placeholder": "Search backups...",
        "export_name": "backup_system",
        "print_target": "#backup-records",
        "table_panel_id": "backup-records",
    },
    "templates/treasury/backup_settings.html": {
        "search_placeholder": "Search backup settings...",
        "export_name": "backup_settings",
        "print_target": "#backup-settings-records",
        "table_panel_id": "backup-settings-records",
    },
}


def render_toolbar_call(cfg: dict) -> str:
    lines = ["  {{ erp_module_toolbar(", "    mode='standard',"]
    for key in (
        "search_placeholder",
        "search_name",
        "export_name",
        "export_url",
        "print_target",
        "form_panel_id",
        "table_panel_id",
        "new_url",
        "add_trigger_selector",
        "reports_url",
        "settings_url",
    ):
        if key in cfg and cfg[key]:
            val = cfg[key]
            if key == "add_trigger_selector":
                lines.append(f"    {key}='{val}',")
            elif key in ("new_url", "export_url", "reports_url", "settings_url"):
                # Jinja expression (url_for(...) ~ '#anchor')
                lines.append(f"    {key}={val},")
            else:
                lines.append(f"    {key}='{val}',")
    if cfg.get("show_run_report"):
        lines.append("    show_run_report=true,")
    if cfg.get("print_enabled") is False:
        lines.append("    print_enabled=false,")
    if cfg.get("filter_status_options"):
        opts = ", ".join(f"'{o}'" for o in cfg["filter_status_options"])
        lines.append(f"    filter_status_options=[{opts}],")
    if cfg.get("show_delete"):
        lines.append("    show_delete=true,")
        if cfg.get("delete_form_id"):
            lines.append(f"    delete_form_id='{cfg['delete_form_id']}',")
    lines.append("  ) }}")
    return "\n".join(lines)


def ensure_import(text: str) -> str:
    if "erp_module_toolbar" in text:
        return text
    macro_line = re.search(r"(\{% from 'macros/erp_ui.html' import [^%]+%\})", text)
    if macro_line:
        old = macro_line.group(1)
        if "erp_module_toolbar" not in old:
            new = old.replace(" import ", " import erp_module_toolbar, ", 1)
            if new == old:
                new = old.replace("{% from 'macros/erp_ui.html' import ", "{% from 'macros/erp_ui.html' import erp_module_toolbar, ")
            text = text.replace(old, new, 1)
    else:
        insert_after = re.search(r"(\{% extends 'base_maxek.html' %\}\n)", text)
        if insert_after:
            pos = insert_after.end()
            text = text[:pos] + "{% from 'macros/erp_ui.html' import erp_module_toolbar %}\n" + text[pos:]
    return text


def upgrade_existing_toolbar(text: str, call: str) -> str:
    if "mode='standard'" in text or 'mode="standard"' in text:
        return text
    pattern = re.compile(
        r"\{\{\s*erp_module_toolbar\(\s*[\s\S]*?\)\s*\}\}",
        re.MULTILINE,
    )
    match = pattern.search(text)
    if match:
        hide = re.search(r"hide_unless", call)
        replacement = call
        return text[: match.start()] + replacement + text[match.end() :]
    return text


def has_toolbar_call(text: str) -> bool:
    return "{{ erp_module_toolbar" in text


def insert_toolbar(text: str, call: str, cfg: dict) -> str:
    if has_toolbar_call(text):
        return upgrade_existing_toolbar(text, call)

    hide_unless = cfg.get("hide_unless")
    wrapper_open = '<div class="erp-module-layout">\n'
    wrapper_close = "</div>\n"
    toolbar_block = call + "\n"

    if hide_unless:
        toolbar_block = f"{{% if {hide_unless} %}}\n{call}\n{{% endif %}}\n"

    # Insert after block content, before first major layout
    m = re.search(r"(\{% block content %\}\n)", text)
    if not m:
        return text
    pos = m.end()

    # Skip past view_record blocks (common pattern)
    view_end = re.search(
        r"\{% endif %\}\n\n(?=\{% if show_form|\{% if not view|<div class=\"module-layout|<div class=\"erp-module-layout)",
        text[pos:],
    )
    if view_end and hide_unless:
        pos += view_end.end()

    if '<div class="erp-module-layout">' not in text and '<div class="module-layout">' in text:
        text = text.replace('<div class="module-layout">', wrapper_open + toolbar_block, 1)
    elif '<div class="erp-module-layout">' not in text:
        text = text[:pos] + wrapper_open + toolbar_block + text[pos:]
    else:
        text = re.sub(
            r'(<div class="erp-module-layout">)\n',
            r"\1\n" + toolbar_block,
            text,
            count=1,
        )
    return text


def ensure_table_panel_id(text: str, panel_id: str) -> str:
    if f'id="{panel_id}"' in text:
        return text
    # Wrap first erp-table-wrap or erp-table-panel
    if 'class="erp-table-wrap"' in text and f'id="{panel_id}"' not in text:
        text = text.replace(
            '<div class="erp-table-wrap">',
            f'<div class="erp-table-wrap" id="{panel_id}" data-erp-table>',
            1,
        )
    elif 'class="erp-table-panel"' in text and f'id="{panel_id}"' not in text:
        text = re.sub(
            r'(<div class="erp-table-panel")',
            f'\\1 id="{panel_id}" data-erp-table',
            text,
            count=1,
        )
    elif "<table" in text and f'id="{panel_id}"' not in text:
        # wrap first table section
        text = re.sub(
            r'(<div class="erp-table-scroll">)',
            f'<div id="{panel_id}" data-erp-table><div class="erp-table-scroll">',
            text,
            count=1,
        )
        if f'id="{panel_id}"' in text:
            text = text.replace("</table>\n    </div>", "</table>\n    </div></div>", 1)
    return text


def patch_selectable_rows(text: str) -> str:
    if "erp-selectable-row" in text:
        return text

    def repl_row(m: re.Match) -> str:
        row = m.group(0)
        if "erp-selectable-row" in row:
            return row
        id_match = re.search(r"\{\{\s*row\.(\w+)\s*\}\}", row)
        if not id_match:
            id_match = re.search(r"data-record-id=", row)
            if id_match:
                return row
            return row
        field = id_match.group(1)
        if field not in ("id", "customer_id"):
            return row
        attrs = f'class="erp-selectable-row" tabindex="0" data-record-id="{{{{ row.{field} }}}}"'
        return re.sub(r"<tr(?:\s[^>]*)?>", f"<tr {attrs}>", row, count=1)

    return re.sub(
        r"<tr>\s*\n\s*<td>\{\{\s*row\.",
        repl_row,
        text,
    )


def process_file(rel: str, cfg: dict) -> bool:
    path = ROOT / rel.replace("/", "\\") if "\\" in str(ROOT) else ROOT / rel
    if not path.is_file():
        print(f"MISSING: {rel}")
        return False
    original = path.read_text(encoding="utf-8")
    if "extends 'base_maxek.html'" not in original and 'extends "base_maxek.html"' not in original:
        return False

    text = ensure_import(original)
    call = render_toolbar_call(cfg)
    text = insert_toolbar(text, call, cfg)

    if cfg.get("table_panel_id"):
        text = ensure_table_panel_id(text, cfg["table_panel_id"])

    if cfg.get("add_trigger_selector") == "#dms-upload-trigger" and 'id="dms-upload-trigger"' not in text:
        text = text.replace(
            "onclick=\"document.getElementById('dms-upload-panel')",
            'id="dms-upload-trigger" onclick="document.getElementById(\'dms-upload-panel\')',
            1,
        )

    text = patch_selectable_rows(text)

    if text != original:
        path.write_text(text, encoding="utf-8")
        print(f"UPDATED: {rel}")
        return True
    print(f"UNCHANGED: {rel}")
    return False


def main() -> int:
    updated = 0
    for rel, cfg in sorted(TOOLBAR.items()):
        if process_file(rel, cfg):
            updated += 1

    # Upgrade any remaining templates that already have toolbar but not standard
    for path in sorted(TEMPLATES.rglob("*.html")):
        rel = path.relative_to(ROOT).as_posix()
        if rel in TOOLBAR or rel in SKIP:
            continue
        if "deploy" in rel:
            continue
        text = path.read_text(encoding="utf-8")
        if "extends 'base_maxek.html'" not in text:
            continue
        if "erp_module_toolbar" not in text:
            continue
        if "mode='standard'" in text or 'mode="standard"' in text:
            continue
        # generic upgrade
        cfg = {
            "search_placeholder": "Search records...",
            "export_name": path.stem,
            "print_target": "#data-table",
            "table_panel_id": "data-table",
        }
        new_text = ensure_import(text)
        call = render_toolbar_call(cfg)
        new_text = upgrade_existing_toolbar(new_text, call)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            print(f"UPGRADED (generic): {rel}")
            updated += 1

    print(f"\nTotal updated: {updated}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
