MAXEK ERP — UI/UX PATCH DEPLOY
Generated: 2026-06-23T14:30:24
Package: MAXEK_ERP_UI_UX_patch_20260623.zip
Files: 112

WORK STREAMS INCLUDED
------------------------------------------------------------
1. Employee age & data entry (dob-age.js, data-entry.js, staff/workers/purchase_vendors/base_maxek)
2. Final UI/UX standards (field/table CSS, shell partials, maxek-ui.js, ui_shell_config.py, petty_cash, alert_engine, macros)
3. Client billing print/form fixes

VPS TARGET ROOT
------------------------------------------------------------
/var/www/maxek-erp-flask

FILE LIST (local relative path -> VPS path)
------------------------------------------------------------
    1. accounts_service.py  ->  /var/www/maxek-erp-flask/accounts_service.py
    2. ai_routes.py  ->  /var/www/maxek-erp-flask/ai_routes.py
    3. ai_service.py  ->  /var/www/maxek-erp-flask/ai_service.py
    4. alert_engine_service.py  ->  /var/www/maxek-erp-flask/alert_engine_service.py
    5. api_routes.py  ->  /var/www/maxek-erp-flask/api_routes.py
    6. app.py  ->  /var/www/maxek-erp-flask/app.py
    7. attachment_service.py  ->  /var/www/maxek-erp-flask/attachment_service.py
    8. attendance_service.py  ->  /var/www/maxek-erp-flask/attendance_service.py
    9. audit_trail_service.py  ->  /var/www/maxek-erp-flask/audit_trail_service.py
   10. auth_jwt.py  ->  /var/www/maxek-erp-flask/auth_jwt.py
   11. backup_service.py  ->  /var/www/maxek-erp-flask/backup_service.py
   12. badge_counts_service.py  ->  /var/www/maxek-erp-flask/badge_counts_service.py
   13. bbs_service.py  ->  /var/www/maxek-erp-flask/bbs_service.py
   14. budget_service.py  ->  /var/www/maxek-erp-flask/budget_service.py
   15. claims_service.py  ->  /var/www/maxek-erp-flask/claims_service.py
   16. client_billing_service.py  ->  /var/www/maxek-erp-flask/client_billing_service.py
   17. command_center_service.py  ->  /var/www/maxek-erp-flask/command_center_service.py
   18. company_master_service.py  ->  /var/www/maxek-erp-flask/company_master_service.py
   19. contract_service.py  ->  /var/www/maxek-erp-flask/contract_service.py
   20. corporate_dms_service.py  ->  /var/www/maxek-erp-flask/corporate_dms_service.py
   21. corporate_report_data_service.py  ->  /var/www/maxek-erp-flask/corporate_report_data_service.py
   22. corporate_template_service.py  ->  /var/www/maxek-erp-flask/corporate_template_service.py
   23. cost_planning_service.py  ->  /var/www/maxek-erp-flask/cost_planning_service.py
   24. dashboard_prefs_service.py  ->  /var/www/maxek-erp-flask/dashboard_prefs_service.py
   25. deploy/fix_petty_cash_db.sql  ->  /var/www/maxek-erp-flask/deploy/fix_petty_cash_db.sql
   26. deploy/migrate_production.py  ->  /var/www/maxek-erp-flask/deploy/migrate_production.py
   27. document_numbering_service.py  ->  /var/www/maxek-erp-flask/document_numbering_service.py
   28. employee_timesheet_service.py  ->  /var/www/maxek-erp-flask/employee_timesheet_service.py
   29. equipment_costing_service.py  ->  /var/www/maxek-erp-flask/equipment_costing_service.py
   30. erp_admin_routes.py  ->  /var/www/maxek-erp-flask/erp_admin_routes.py
   31. erp_platform_routes.py  ->  /var/www/maxek-erp-flask/erp_platform_routes.py
   32. global_search_service.py  ->  /var/www/maxek-erp-flask/global_search_service.py
   33. helpdesk_service.py  ->  /var/www/maxek-erp-flask/helpdesk_service.py
   34. labour_productivity_service.py  ->  /var/www/maxek-erp-flask/labour_productivity_service.py
   35. office_fleet_service.py  ->  /var/www/maxek-erp-flask/office_fleet_service.py
   36. payroll_service.py  ->  /var/www/maxek-erp-flask/payroll_service.py
   37. plant_service.py  ->  /var/www/maxek-erp-flask/plant_service.py
   38. precast_service.py  ->  /var/www/maxek-erp-flask/precast_service.py
   39. profitability_service.py  ->  /var/www/maxek-erp-flask/profitability_service.py
   40. project_photos_service.py  ->  /var/www/maxek-erp-flask/project_photos_service.py
   41. qc_service.py  ->  /var/www/maxek-erp-flask/qc_service.py
   42. report_registry.py  ->  /var/www/maxek-erp-flask/report_registry.py
   43. requirements.txt  ->  /var/www/maxek-erp-flask/requirements.txt
   44. seed_super_admin.py  ->  /var/www/maxek-erp-flask/seed_super_admin.py
   45. static/css/maxek-dashboard.css  ->  /var/www/maxek-erp-flask/static/css/maxek-dashboard.css
   46. static/css/maxek-field-standards.css  ->  /var/www/maxek-erp-flask/static/css/maxek-field-standards.css
   47. static/css/maxek-login.css  ->  /var/www/maxek-erp-flask/static/css/maxek-login.css
   48. static/css/maxek-table-standards.css  ->  /var/www/maxek-erp-flask/static/css/maxek-table-standards.css
   49. static/images/maxek-logo.png  ->  /var/www/maxek-erp-flask/static/images/maxek-logo.png
   50. static/js/ai-assistant.js  ->  /var/www/maxek-erp-flask/static/js/ai-assistant.js
   51. static/js/boq-forms.js  ->  /var/www/maxek-erp-flask/static/js/boq-forms.js
   52. static/js/data-entry.js  ->  /var/www/maxek-erp-flask/static/js/data-entry.js
   53. static/js/dob-age.js  ->  /var/www/maxek-erp-flask/static/js/dob-age.js
   54. static/js/login.js  ->  /var/www/maxek-erp-flask/static/js/login.js
   55. static/js/maxek-ui.js  ->  /var/www/maxek-erp-flask/static/js/maxek-ui.js
   56. static/js/staff-forms.js  ->  /var/www/maxek-erp-flask/static/js/staff-forms.js
   57. store_service.py  ->  /var/www/maxek-erp-flask/store_service.py
   58. subcontract_payment_service.py  ->  /var/www/maxek-erp-flask/subcontract_payment_service.py
   59. subcontractor_billing_service.py  ->  /var/www/maxek-erp-flask/subcontractor_billing_service.py
   60. super_admin_service.py  ->  /var/www/maxek-erp-flask/super_admin_service.py
   61. templates/accounts_payment_voucher.html  ->  /var/www/maxek-erp-flask/templates/accounts_payment_voucher.html
   62. templates/attendance.html  ->  /var/www/maxek-erp-flask/templates/attendance.html
   63. templates/base_maxek.html  ->  /var/www/maxek-erp-flask/templates/base_maxek.html
   64. templates/bbs_print.html  ->  /var/www/maxek-erp-flask/templates/bbs_print.html
   65. templates/boq.html  ->  /var/www/maxek-erp-flask/templates/boq.html
   66. templates/client_billing_form.html  ->  /var/www/maxek-erp-flask/templates/client_billing_form.html
   67. templates/client_billing_gst_print.html  ->  /var/www/maxek-erp-flask/templates/client_billing_gst_print.html
   68. templates/client_billing_print.html  ->  /var/www/maxek-erp-flask/templates/client_billing_print.html
   69. templates/clients.html  ->  /var/www/maxek-erp-flask/templates/clients.html
   70. templates/cost_planning.html  ->  /var/www/maxek-erp-flask/templates/cost_planning.html
   71. templates/dashboard.html  ->  /var/www/maxek-erp-flask/templates/dashboard.html
   72. templates/dpr.html  ->  /var/www/maxek-erp-flask/templates/dpr.html
   73. templates/dpr_client_bill_print.html  ->  /var/www/maxek-erp-flask/templates/dpr_client_bill_print.html
   74. templates/employee_timesheet_print.html  ->  /var/www/maxek-erp-flask/templates/employee_timesheet_print.html
   75. templates/login.html  ->  /var/www/maxek-erp-flask/templates/login.html
   76. templates/macros/erp_ui.html  ->  /var/www/maxek-erp-flask/templates/macros/erp_ui.html
   77. templates/material_request.html  ->  /var/www/maxek-erp-flask/templates/material_request.html
   78. templates/partials/ai_assistant_panel.html  ->  /var/www/maxek-erp-flask/templates/partials/ai_assistant_panel.html
   79. templates/partials/shell_action_panel.html  ->  /var/www/maxek-erp-flask/templates/partials/shell_action_panel.html
   80. templates/partials/shell_global_search.html  ->  /var/www/maxek-erp-flask/templates/partials/shell_global_search.html
   81. templates/partials/shell_help_center.html  ->  /var/www/maxek-erp-flask/templates/partials/shell_help_center.html
   82. templates/partials/shell_quick_panel.html  ->  /var/www/maxek-erp-flask/templates/partials/shell_quick_panel.html
   83. templates/partials/shell_status_strip.html  ->  /var/www/maxek-erp-flask/templates/partials/shell_status_strip.html
   84. templates/partials/universal_view_panel.html  ->  /var/www/maxek-erp-flask/templates/partials/universal_view_panel.html
   85. templates/payroll.html  ->  /var/www/maxek-erp-flask/templates/payroll.html
   86. templates/payroll_print_slip.html  ->  /var/www/maxek-erp-flask/templates/payroll_print_slip.html
   87. templates/payroll_run_print.html  ->  /var/www/maxek-erp-flask/templates/payroll_run_print.html
   88. templates/petty_cash.html  ->  /var/www/maxek-erp-flask/templates/petty_cash.html
   89. templates/plant_asphalt_dispatch_print.html  ->  /var/www/maxek-erp-flask/templates/plant_asphalt_dispatch_print.html
   90. templates/plant_rmc_dispatch_print.html  ->  /var/www/maxek-erp-flask/templates/plant_rmc_dispatch_print.html
   91. templates/projects.html  ->  /var/www/maxek-erp-flask/templates/projects.html
   92. templates/purchase_order_print.html  ->  /var/www/maxek-erp-flask/templates/purchase_order_print.html
   93. templates/purchase_orders.html  ->  /var/www/maxek-erp-flask/templates/purchase_orders.html
   94. templates/purchase_vendors.html  ->  /var/www/maxek-erp-flask/templates/purchase_vendors.html
   95. templates/settings.html  ->  /var/www/maxek-erp-flask/templates/settings.html
   96. templates/staff.html  ->  /var/www/maxek-erp-flask/templates/staff.html
   97. templates/store_grn.html  ->  /var/www/maxek-erp-flask/templates/store_grn.html
   98. templates/store_materials.html  ->  /var/www/maxek-erp-flask/templates/store_materials.html
   99. templates/sub_billing_print.html  ->  /var/www/maxek-erp-flask/templates/sub_billing_print.html
  100. templates/treasury/alert_engine.html  ->  /var/www/maxek-erp-flask/templates/treasury/alert_engine.html
  101. templates/treasury/alert_settings.html  ->  /var/www/maxek-erp-flask/templates/treasury/alert_settings.html
  102. templates/treasury/hub.html  ->  /var/www/maxek-erp-flask/templates/treasury/hub.html
  103. templates/vehicle_print.html  ->  /var/www/maxek-erp-flask/templates/vehicle_print.html
  104. templates/workers.html  ->  /var/www/maxek-erp-flask/templates/workers.html
  105. tenant_isolation.py  ->  /var/www/maxek-erp-flask/tenant_isolation.py
  106. treasury_routes.py  ->  /var/www/maxek-erp-flask/treasury_routes.py
  107. treasury_service.py  ->  /var/www/maxek-erp-flask/treasury_service.py
  108. ui_shell_config.py  ->  /var/www/maxek-erp-flask/ui_shell_config.py
  109. user_activity_service.py  ->  /var/www/maxek-erp-flask/user_activity_service.py
  110. user_context_service.py  ->  /var/www/maxek-erp-flask/user_context_service.py
  111. workflow_service.py  ->  /var/www/maxek-erp-flask/workflow_service.py
  112. wsgi.py  ->  /var/www/maxek-erp-flask/wsgi.py

UPLOAD (from Windows PowerShell)
------------------------------------------------------------
scp deploy/MAXEK_ERP_UI_UX_patch_20260623.zip root@srv1704727:/tmp/

APPLY ON VPS (SSH)
------------------------------------------------------------
cd /var/www/maxek-erp-flask
sudo cp -a database/maxek.db database/maxek.db.bak-$(date +%Y%m%d%H%M)  # optional backup
sudo unzip -o /tmp/MAXEK_ERP_UI_UX_patch_20260623.zip -d /var/www/maxek-erp-flask
source venv/bin/activate
export MAXEK_SKIP_DEMO_SEED=1
python deploy/migrate_production.py
sudo chown -R www-data:www-data /var/www/maxek-erp-flask/app.py /var/www/maxek-erp-flask/templates /var/www/maxek-erp-flask/static /var/www/maxek-erp-flask/*.py
sudo systemctl restart maxek-erp
sudo systemctl status maxek-erp --no-pager

ONE-LINE DEPLOY (after scp to /tmp/)
------------------------------------------------------------
cd /var/www/maxek-erp-flask && sudo unzip -o /tmp/MAXEK_ERP_UI_UX_patch_20260623.zip -d /var/www/maxek-erp-flask && source venv/bin/activate && export MAXEK_SKIP_DEMO_SEED=1 && python deploy/migrate_production.py && sudo chown -R www-data:www-data app.py templates static *.py && sudo systemctl restart maxek-erp

BROWSER — HARD REFRESH CSS/JS CACHE
------------------------------------------------------------
After deploy, hard-refresh each browser session: Ctrl+Shift+R (Windows) or Cmd+Shift+R (Mac).
base_maxek.html cache-bust query params: ?v=20260623-fieldwidth / ?v=20260623-ux / ?v=20260623-shell

VERIFY
------------------------------------------------------------
1. App loads (no 502) — confirms app.py + service imports match
2. Staff/Workers: DOB shows computed age; data-entry tab order works
3. Global search (Ctrl+K) opens from header
4. Petty cash + Treasury > Alert engine pages render with new table/field standards
5. Client billing form + print layouts
