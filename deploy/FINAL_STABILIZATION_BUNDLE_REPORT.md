# MAXEK ERP — Final Stabilization Bundle Report
**Generated:** 2026-06-28 16:35:09 (local)  **Git HEAD:** `2e10ed5a72ec334de41553d609049a273edda2a8`  **Baseline:** `1edd62e` (last VPS bundle doc commit)  **Branch:** `main` (ahead of `origin/main` by 8 commits)  **Patch:** `deploy/dist/vps-patch-latest.zip` — Production files: 211 | Size bytes: 816458
Rebuild: `python deploy/build_vps_patch_latest.py`
---
## Commits included
- `2e10ed5` — feat: improve user permission assignment UI with department matrix
- `a4ca636` — feat: add per-tenant dashboard layout theme system
- `32788c9` — feat: roll out standard module toolbar, UAT checklist, branding split
- `114de03` — feat: refine Command Centre to department launcher with platform super-admin view
- `ad3b091` — fix: move financial widgets from Command Centre to Accounts dept dashboard
- `8318da9` — fix: dashboard greeting uses app timezone (IST)
- `cabbb87` — fix: prevent 500 on erp-admin pages when platform dashboard route missing
- `394bd8b` — fix: production stabilization phases 1-3 (toolbar, customer, deploy)

---
## Pre-pack verification

| Check | Result |
|-------|--------|
| import wsgi | OK |
| test_login_auth.py | 3 passed |
| test_customer_management_phase2.py | passed |
| test_user_permissions.py | passed |
| test_dashboard_themes.py | passed |
| Combined four suites | 16 passed |
| mode=standard count | 129 |
| Bulk import 410b68f5 | Not in repo — excluded |

---
## Files changed (grouped)

### Python (8)

- `app.py`
- `dashboard_prefs_service.py`
- `deploy/build_vps_patch_latest.py`
- `erp_admin_routes.py`
- `super_admin_service.py`
- `ui_shell_config.py`
- `user_context_service.py`
- `user_permission_service.py`

### Templates (139)

- `templates/accounts_book.html`
- `templates/accounts_book_v2.html`
- `templates/accounts_chart_of_accounts.html`
- `templates/accounts_expenses.html`
- `templates/accounts_gst_register.html`
- `templates/accounts_party_ledger.html`
- `templates/accounts_payment_voucher.html`
- `templates/accounts_pf_esi_register.html`
- `templates/accounts_receipt_voucher.html`
- `templates/accounts_reports.html`
- `templates/accounts_tally_export.html`
- `templates/accounts_tds_register.html`
- `templates/advances.html`
- `templates/approvals.html`
- `templates/attendance.html`
- `templates/base_maxek.html`
- `templates/bbs_register.html`
- `templates/boq.html`
- `templates/client_billing_register.html`
- `templates/client_billing_reports.html`
- `templates/clients.html`
- `templates/company_master.html`
- `templates/corporate_dms_register.html`
- `templates/corporate_template_master.html`
- `templates/cost_planning.html`
- `templates/cost_planning_reports.html`
- `templates/dashboard.html`
- `templates/dashboard_theme_compact.html`
- `templates/dashboard_theme_executive.html`
- `templates/dpr.html`
- `templates/employee_timesheets.html`
- `templates/erp_admin/audit_logs.html`
- `templates/erp_admin/change_requests.html`
- `templates/erp_admin/customer_settings.html`
- `templates/erp_admin/customers.html`
- `templates/erp_admin/licenses.html`
- `templates/erp_admin/limits.html`
- `templates/erp_admin/login_monitoring.html`
- `templates/erp_admin/platform_dashboard.html`
- `templates/erp_admin/settings.html`
- `templates/erp_admin/subscriptions.html`
- `templates/erp_admin/support_tickets.html`
- `templates/erp_admin/system_health.html`
- `templates/fleet_diesel_issue.html`
- `templates/fleet_diesel_purchase.html`
- `templates/fleet_diesel_stock.html`
- `templates/fleet_running_log.html`
- `templates/fleet_vehicle_documents.html`
- `templates/fleet_vehicles.html`
- `templates/head_office_expenses.html`
- `templates/macros/erp_ui.html`
- `templates/material_request.html`
- `templates/material_transfer.html`
- `templates/office_agreements.html`
- `templates/office_inward.html`
- `templates/office_legal.html`
- `templates/office_letters.html`
- `templates/office_outward.html`
- `templates/office_po_register.html`
- `templates/office_quotations.html`
- `templates/partials/dashboard_shell_header.html`
- `templates/partials/dashboard_shell_module_header.html`
- `templates/partials/dashboard_shell_sidebar.html`
- `templates/payroll.html`
- `templates/payroll_holidays.html`
- `templates/payroll_payments.html`
- `templates/payroll_revisions.html`
- `templates/petty_cash.html`
- `templates/plant_360.html`
- `templates/plant_asphalt_dispatch.html`
- `templates/plant_asphalt_production.html`
- `templates/plant_costing.html`
- `templates/plant_crusher_production.html`
- `templates/plant_maintenance.html`
- `templates/plant_master.html`
- `templates/plant_precast_dispatch.html`
- `templates/plant_precast_production.html`
- `templates/plant_qc.html`
- `templates/plant_rmc_dispatch.html`
- `templates/plant_rmc_production.html`
- `templates/plant_wetmix_production.html`
- `templates/precast_yard.html`
- `templates/precast_yard_yards.html`
- `templates/project_documents_register.html`
- `templates/project_photos_register.html`
- `templates/project_photos_reports.html`
- `templates/project_photos_timeline.html`
- `templates/projects.html`
- `templates/purchase_orders.html`
- `templates/purchase_request.html`
- `templates/purchase_vendors.html`
- `templates/qc_master.html`
- `templates/reports.html`
- `templates/salary.html`
- `templates/securities_guarantees.html`
- `templates/settings.html`
- `templates/staff.html`
- `templates/staff_bonus.html`
- `templates/store_grn.html`
- `templates/store_inventory.html`
- `templates/store_issue.html`
- `templates/store_materials.html`
- `templates/sub_billing_register.html`
- `templates/subcontract_payments.html`
- `templates/subcontractors.html`
- `templates/timesheet.html`
- `templates/treasury/alert_engine.html`
- `templates/treasury/alert_settings.html`
- `templates/treasury/backup_settings.html`
- `templates/treasury/backup_system.html`
- `templates/treasury/bank_accounts.html`
- `templates/treasury/bank_guarantees.html`
- `templates/treasury/budget_control.html`
- `templates/treasury/cheques.html`
- `templates/treasury/claims.html`
- `templates/treasury/contract_management.html`
- `templates/treasury/document_numbering.html`
- `templates/treasury/document_vault.html`
- `templates/treasury/equipment_costing.html`
- `templates/treasury/fixed_deposits.html`
- `templates/treasury/labour_productivity.html`
- `templates/treasury/letters_of_credit.html`
- `templates/treasury/overdrafts.html`
- `templates/treasury/payments.html`
- `templates/treasury/pdc_register.html`
- `templates/treasury/project_budget.html`
- `templates/treasury/project_contracts.html`
- `templates/treasury/project_labour_summary.html`
- `templates/treasury/project_profitability.html`
- `templates/treasury/receipts.html`
- `templates/treasury/reconciliation.html`
- `templates/treasury/reports.html`
- `templates/treasury/security_deposits.html`
- `templates/user_activity.html`
- `templates/user_management.html`
- `templates/users.html`
- `templates/workers.html`
- `templates/workflow_audit_report.html`
- `templates/workflow_settings.html`

### Static (4)

- `static/css/maxek-dashboard.css`
- `static/css/maxek-pro-dashboard.css`
- `static/js/master-forms.js`
- `static/js/maxek-ui.js`

---
## DB auto-schema

- `erp_customers.dashboard_theme` — super_admin_service
- `user_tab_permissions.action_flags` — user_permission_service
- Dashboard prefs — dashboard_prefs_service
- Run on VPS: `python deploy/migrate_production.py` after unzip

---
## Modules without standard toolbar (NEED backlog)

- `[NEED] templates/accounts_hub.html`
- `[NEED] templates/bbs_form.html`
- `[NEED] templates/boq_multiple_entry.html`
- `[NEED] templates/client_billing_form.html`
- `[NEED] templates/client_billing_gst_form.html`
- `[NEED] templates/corporate_reports_hub.html`
- `[NEED] templates/dashboard_theme_compact.html`
- `[NEED] templates/dashboard_theme_executive.html`
- `[NEED] templates/employee_timesheet_form.html`
- `[NEED] templates/erp_admin/customer_settings.html`
- `[NEED] templates/sub_billing_form.html`
- `[NEED] templates/treasury/account_360.html`
- `[NEED] templates/treasury/budget_form.html`
- `[NEED] templates/treasury/cash_flow_forecast.html`
- `[NEED] templates/treasury/cheque_form.html`
- `[NEED] templates/treasury/cheque_view.html`
- `[NEED] templates/treasury/claim_form.html`
- `[NEED] templates/treasury/claim_view.html`
- `[NEED] templates/treasury/contract_form.html`
- `[NEED] templates/treasury/contract_view.html`
- `[NEED] templates/treasury/cost_entry_form.html`
- `[NEED] templates/treasury/document_upload.html`
- `[NEED] templates/treasury/document_view.html`
- `[NEED] templates/treasury/equipment_detail.html`
- `[NEED] templates/treasury/equipment_form.html`
- `[NEED] templates/treasury/fd_form.html`
- `[NEED] templates/treasury/fd_view.html`
- `[NEED] templates/treasury/hub.html`
- `[NEED] templates/treasury/labour_productivity_detail.html`
- `[NEED] templates/treasury/labour_productivity_form.html`
- `[NEED] templates/treasury/numbering_config_form.html`
- `[NEED] templates/treasury/pdc_form.html`
- `[NEED] templates/treasury/pdc_view.html`
- `[NEED] templates/treasury/project_profitability_detail.html`

---
## VPS deploy

Path: `/var/www/maxek-erp-flask/` — Service: **`maxek-erp`** (confirm with `systemctl list-units 'maxek*'`)

```bash
sudo systemctl stop maxek-erp
cd /var/www/maxek-erp-flask
sudo unzip -o /tmp/vps-patch-latest.zip -d /var/www/maxek-erp-flask
source venv/bin/activate
export MAXEK_SKIP_DEMO_SEED=1
python deploy/migrate_production.py
sudo chown -R www-data:www-data app.py templates static *.py
sudo systemctl start maxek-erp
```

## Rollback

Stop service → restore `/var/backups/maxek-erp/` full tar or previous zip → start service.

## Post-deploy checklist

- [ ] Service active
- [ ] wsgi import OK
- [ ] /login HTTP 200
- [ ] Customer Settings dashboard theme
- [ ] My Dashboard Preferences override
- [ ] Settings → Users permission matrix save
- [ ] Sample modules show standard toolbar
- [ ] No 500 on ERP Admin

## Approval

- [ ] Deploy HEAD `2e10ed5a72ec334de41553d609049a273edda2a8` single patch
