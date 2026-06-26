# MAXEK ERP — WinSCP path map (folder-by-folder upload)

Upload **individual files and folders** with WinSCP (drag-and-drop). **Do not zip** the project for this workflow.

| Setting | Value |
|--------|--------|
| **Local PC root** | `C:\Users\rajee\Documents\New project\MAXEK_ERP\` |
| **VPS remote root** | `/var/www/maxek-erp-flask/` |
| **Protocol** | SFTP |
| **Host** | `srv1704727` (or your Hostinger VPS IP) |
| **User** | `root` |

---

## WinSCP steps

1. Open **WinSCP** → **New Site** → Protocol **SFTP**, Host **srv1704727** (or IP), User **root**, password or SSH key → **Login**.
2. **Left panel (local):** browse to `C:\Users\rajee\Documents\New project\MAXEK_ERP`
3. **Right panel (remote):** browse to `/var/www/maxek-erp-flask`
4. For each section below, open the matching local folder on the left and the matching remote folder on the right, then **drag files** into the remote folder (overwrite when prompted).
5. **Do not upload:** `.venv\`, `venv\`, `__pycache__\`, `.git\`, `.env` (secrets), `database\maxek.db` unless you intend to replace production data, large `deploy\dist\*.zip` unless needed.

**After upload (SSH):**

```bash
cd /var/www/maxek-erp-flask
sudo chown -R www-data:www-data /var/www/maxek-erp-flask
source venv/bin/activate
export MAXEK_SKIP_DEMO_SEED=1
python deploy/migrate_production.py
sudo systemctl restart maxek-erp
sudo systemctl status maxek-erp --no-pager
```

---

## Quick list (minimum 14 files)

Use this for a small code/UI update when you know exactly what changed.

| # | Local path | Remote path | WinSCP action |
|---|------------|-------------|---------------|
| 1 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\app.py` | `/var/www/maxek-erp-flask/app.py` | Drag to **app root** |
| 2 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\workflow_service.py` | `/var/www/maxek-erp-flask/workflow_service.py` | Drag to **app root** |
| 2b | `C:\Users\rajee\Documents\New project\MAXEK_ERP\payroll_service.py` | `/var/www/maxek-erp-flask/payroll_service.py` | Drag to **app root** |
| 2c | `C:\Users\rajee\Documents\New project\MAXEK_ERP\attendance_service.py` | `/var/www/maxek-erp-flask/attendance_service.py` | Drag to **app root** |
| 2d | `C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\payroll.html` | `/var/www/maxek-erp-flask/templates/payroll.html` | Drag into **templates/** |
| 2e | `C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\payroll_run_print.html` | `/var/www/maxek-erp-flask/templates/payroll_run_print.html` | Drag into **templates/** |
| 2f | `C:\Users\rajee\Documents\New project\MAXEK_ERP\static\js\payroll-forms.js` | `/var/www/maxek-erp-flask/static/js/payroll-forms.js` | Drag into **static/js/** |
| 3 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\wsgi.py` | `/var/www/maxek-erp-flask/wsgi.py` | Drag to **app root** |
| 4 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\requirements.txt` | `/var/www/maxek-erp-flask/requirements.txt` | Drag to **app root** |
| 5 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\base_maxek.html` | `/var/www/maxek-erp-flask/templates/base_maxek.html` | Drag into **templates/** |
| 6 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\login.html` | `/var/www/maxek-erp-flask/templates/login.html` | Drag into **templates/** |
| 7 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\dashboard.html` | `/var/www/maxek-erp-flask/templates/dashboard.html` | Drag into **templates/** |
| 8 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\static\js\app.js` | `/var/www/maxek-erp-flask/static/js/app.js` | Drag into **static/js/** |
| 9 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\static\js\maxek-ui.js` | `/var/www/maxek-erp-flask/static/js/maxek-ui.js` | Drag into **static/js/** |
| 10 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\static\css\maxek-dashboard.css` | `/var/www/maxek-erp-flask/static/css/maxek-dashboard.css` | Drag into **static/css/** |
| 11 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\static\images\maxek-logo.png` | `/var/www/maxek-erp-flask/static/images/maxek-logo.png` | Drag into **static/images/** |
| 12 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\migrate_production.py` | `/var/www/maxek-erp-flask/deploy/migrate_production.py` | Drag into **deploy/** |
| 13 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\vps_update.sh` | `/var/www/maxek-erp-flask/deploy/vps_update.sh` | Drag into **deploy/** |
| 14 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\nginx-maxek-erp.conf` | `/var/www/maxek-erp-flask/deploy/nginx-maxek-erp.conf` | Drag into **deploy/** |

---

## 1. App root → `/var/www/maxek-erp-flask/`

Remote folder: open `/var/www/maxek-erp-flask` on the right. Drag these from the **local project root** (not from subfolders).

| File | Local path | Remote path | WinSCP action |
|------|------------|-------------|---------------|
| app.py | `C:\Users\rajee\Documents\New project\MAXEK_ERP\app.py` | `/var/www/maxek-erp-flask/app.py` | Upload to app root |
| workflow_service.py | `C:\Users\rajee\Documents\New project\MAXEK_ERP\workflow_service.py` | `/var/www/maxek-erp-flask/workflow_service.py` | Upload to app root |
| wsgi.py | `C:\Users\rajee\Documents\New project\MAXEK_ERP\wsgi.py` | `/var/www/maxek-erp-flask/wsgi.py` | Upload to app root |
| requirements.txt | `C:\Users\rajee\Documents\New project\MAXEK_ERP\requirements.txt` | `/var/www/maxek-erp-flask/requirements.txt` | Upload to app root |

---

## 2. `templates/` → `/var/www/maxek-erp-flask/templates/`

Local: `C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\`  
Remote: `/var/www/maxek-erp-flask/templates/`

Create remote subfolder `macros` if missing, then upload `templates\macros\erp_ui.html`.

| File | Local path | Remote path | WinSCP action |
|------|------------|-------------|---------------|
| accounts_book.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\accounts_book.html` | `/var/www/maxek-erp-flask/templates/accounts_book.html` | Drag into **templates/** |
| advances.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\advances.html` | `/var/www/maxek-erp-flask/templates/advances.html` | Drag into **templates/** |
| approvals.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\approvals.html` | `/var/www/maxek-erp-flask/templates/approvals.html` | Drag into **templates/** |
| attendance.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\attendance.html` | `/var/www/maxek-erp-flask/templates/attendance.html` | Drag into **templates/** |
| base.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\base.html` | `/var/www/maxek-erp-flask/templates/base.html` | Drag into **templates/** |
| base_maxek.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\base_maxek.html` | `/var/www/maxek-erp-flask/templates/base_maxek.html` | Drag into **templates/** |
| boq.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\boq.html` | `/var/www/maxek-erp-flask/templates/boq.html` | Drag into **templates/** |
| clients.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\clients.html` | `/var/www/maxek-erp-flask/templates/clients.html` | Drag into **templates/** |
| dashboard.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\dashboard.html` | `/var/www/maxek-erp-flask/templates/dashboard.html` | Drag into **templates/** |
| dashboard_choice_b.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\dashboard_choice_b.html` | `/var/www/maxek-erp-flask/templates/dashboard_choice_b.html` | Drag into **templates/** |
| department_hub.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\department_hub.html` | `/var/www/maxek-erp-flask/templates/department_hub.html` | Drag into **templates/** |
| dpr.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\dpr.html` | `/var/www/maxek-erp-flask/templates/dpr.html` | Drag into **templates/** |
| dpr_client_bill_print.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\dpr_client_bill_print.html` | `/var/www/maxek-erp-flask/templates/dpr_client_bill_print.html` | Drag into **templates/** |
| forgot_password.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\forgot_password.html` | `/var/www/maxek-erp-flask/templates/forgot_password.html` | Drag into **templates/** |
| login.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\login.html` | `/var/www/maxek-erp-flask/templates/login.html` | Drag into **templates/** |
| module_placeholder.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\module_placeholder.html` | `/var/www/maxek-erp-flask/templates/module_placeholder.html` | Drag into **templates/** |
| module_request.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\module_request.html` | `/var/www/maxek-erp-flask/templates/module_request.html` | Drag into **templates/** |
| notifications.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\notifications.html` | `/var/www/maxek-erp-flask/templates/notifications.html` | Drag into **templates/** |
| petty_cash.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\petty_cash.html` | `/var/www/maxek-erp-flask/templates/petty_cash.html` | Drag into **templates/** |
| projects.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\projects.html` | `/var/www/maxek-erp-flask/templates/projects.html` | Drag into **templates/** |
| reports.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\reports.html` | `/var/www/maxek-erp-flask/templates/reports.html` | Drag into **templates/** |
| salary.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\salary.html` | `/var/www/maxek-erp-flask/templates/salary.html` | Drag into **templates/** |
| settings.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\settings.html` | `/var/www/maxek-erp-flask/templates/settings.html` | Drag into **templates/** |
| staff.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\staff.html` | `/var/www/maxek-erp-flask/templates/staff.html` | Drag into **templates/** |
| staff_bonus.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\staff_bonus.html` | `/var/www/maxek-erp-flask/templates/staff_bonus.html` | Drag into **templates/** |
| subcontractors.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\subcontractors.html` | `/var/www/maxek-erp-flask/templates/subcontractors.html` | Drag into **templates/** |
| timesheet.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\timesheet.html` | `/var/www/maxek-erp-flask/templates/timesheet.html` | Drag into **templates/** |
| users.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\users.html` | `/var/www/maxek-erp-flask/templates/users.html` | Drag into **templates/** |
| workers.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\workers.html` | `/var/www/maxek-erp-flask/templates/workers.html` | Drag into **templates/** |
| workflow_audit_report.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\workflow_audit_report.html` | `/var/www/maxek-erp-flask/templates/workflow_audit_report.html` | Drag into **templates/** |
| workflow_settings.html | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\workflow_settings.html` | `/var/www/maxek-erp-flask/templates/workflow_settings.html` | Drag into **templates/** |
| macros/erp_ui.html | `C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\macros\erp_ui.html` | `/var/www/maxek-erp-flask/templates/macros/erp_ui.html` | Drag into **templates/macros/** |

*Shortcut:* select the whole local `templates` folder and drag to `/var/www/maxek-erp-flask/` so WinSCP merges into `templates/` (includes `macros`).

---

## 3. `static/js/` → `/var/www/maxek-erp-flask/static/js/`

Local: `C:\Users\rajee\Documents\New project\MAXEK_ERP\static\js\`  
Remote: `/var/www/maxek-erp-flask/static/js/`

| File | Local path | Remote path | WinSCP action |
|------|------------|-------------|---------------|
| app.js | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\static\js\app.js` | `/var/www/maxek-erp-flask/static/js/app.js` | Drag into **static/js/** |
| attendance-form.js | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\static\js\attendance-form.js` | `/var/www/maxek-erp-flask/static/js/attendance-form.js` | Drag into **static/js/** |
| employee-timesheet-form.js | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\static\js\employee-timesheet-form.js` | `/var/www/maxek-erp-flask/static/js/employee-timesheet-form.js` | Drag into **static/js/** |
| boq-forms.js | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\static\js\boq-forms.js` | `/var/www/maxek-erp-flask/static/js/boq-forms.js` | Drag into **static/js/** |
| dpr-forms.js | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\static\js\dpr-forms.js` | `/var/www/maxek-erp-flask/static/js/dpr-forms.js` | Drag into **static/js/** |
| master-forms.js | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\static\js\master-forms.js` | `/var/www/maxek-erp-flask/static/js/master-forms.js` | Drag into **static/js/** |
| maxek-ui.js | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\static\js\maxek-ui.js` | `/var/www/maxek-erp-flask/static/js/maxek-ui.js` | Drag into **static/js/** |
| staff-bonus.js | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\static\js\staff-bonus.js` | `/var/www/maxek-erp-flask/static/js/staff-bonus.js` | Drag into **static/js/** |
| staff-forms.js | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\static\js\staff-forms.js` | `/var/www/maxek-erp-flask/static/js/staff-forms.js` | Drag into **static/js/** |
| subcontractors.js | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\static\js\subcontractors.js` | `/var/www/maxek-erp-flask/static/js/subcontractors.js` | Drag into **static/js/** |
| workers-form.js | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\static\js\workers-form.js` | `/var/www/maxek-erp-flask/static/js/workers-form.js` | Drag into **static/js/** |
| workflow.js | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\static\js\workflow.js` | `/var/www/maxek-erp-flask/static/js/workflow.js` | Drag into **static/js/** |

---

## 4. `static/css/` → `/var/www/maxek-erp-flask/static/css/`

Local: `C:\Users\rajee\Documents\New project\MAXEK_ERP\static\css\`  
Remote: `/var/www/maxek-erp-flask/static/css/`

| File | Local path | Remote path | WinSCP action |
|------|------------|-------------|---------------|
| maxek-dashboard.css | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\static\css\maxek-dashboard.css` | `/var/www/maxek-erp-flask/static/css/maxek-dashboard.css` | Drag into **static/css/** |
| maxek-login.css | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\static\css\maxek-login.css` | `/var/www/maxek-erp-flask/static/css/maxek-login.css` | Drag into **static/css/** |
| style.css | `.C:\Users\rajee\Documents\New project\MAXEK_ERP\static\css\style.css` | `/var/www/maxek-erp-flask/static/css/style.css` | Drag into **static/css/** |

---

## 5. `static/images/` → `/var/www/maxek-erp-flask/static/images/`

Local: `C:\Users\rajee\Documents\New project\MAXEK_ERP\static\images\`  
Remote: `/var/www/maxek-erp-flask/static/images/`

| File | Local path | Remote path | WinSCP action |
|------|------------|-------------|---------------|
| maxek-logo.png | `C:\Users\rajee\Documents\New project\MAXEK_ERP\static\images\maxek-logo.png` | `/var/www/maxek-erp-flask/static/images/maxek-logo.png` | Drag into **static/images/** |

---

## 6. `deploy/` → `/var/www/maxek-erp-flask/deploy/`

Local: `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\`  
Remote: `/var/www/maxek-erp-flask/deploy/`

Upload **top-level** deploy files (scripts, SQL, docs, service/nginx). Skip `deploy\dist\`, `deploy\_staging_*`, nested `package_*`, and `*.zip` unless you are intentionally deploying a patch archive.

| File | Local path | Remote path | WinSCP action |
|------|------------|-------------|---------------|
| .env.example | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\.env.example` | `/var/www/maxek-erp-flask/deploy/.env.example` | Drag into **deploy/** |
| apply-worker-sub-crud.sh | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\apply-worker-sub-crud.sh` | `/var/www/maxek-erp-flask/deploy/apply-worker-sub-crud.sh` | Drag into **deploy/** |
| BACKUP_TO_GITHUB.md | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\BACKUP_TO_GITHUB.md` | `/var/www/maxek-erp-flask/deploy/BACKUP_TO_GITHUB.md` | Drag into **deploy/** |
| build_deploy_package.ps1 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\build_deploy_package.ps1` | `/var/www/maxek-erp-flask/deploy/build_deploy_package.ps1` | Drag into **deploy/** |
| build_deploy_package.py | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\build_deploy_package.py` | `/var/www/maxek-erp-flask/deploy/build_deploy_package.py` | Drag into **deploy/** |
| build_vps_patch.ps1 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\build_vps_patch.ps1` | `/var/www/maxek-erp-flask/deploy/build_vps_patch.ps1` | Drag into **deploy/** |
| build-worker-sub-crud-patch.ps1 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\build-worker-sub-crud-patch.ps1` | `/var/www/maxek-erp-flask/deploy/build-worker-sub-crud-patch.ps1` | Drag into **deploy/** |
| check_db_compatibility.py | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\check_db_compatibility.py` | `/var/www/maxek-erp-flask/deploy/check_db_compatibility.py` | Drag into **deploy/** |
| clean_project.bat | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\clean_project.bat` | `/var/www/maxek-erp-flask/deploy/clean_project.bat` | Drag into **deploy/** |
| clean_project.sh | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\clean_project.sh` | `/var/www/maxek-erp-flask/deploy/clean_project.sh` | Drag into **deploy/** |
| DATABASE_MIGRATION.md | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\DATABASE_MIGRATION.md` | `/var/www/maxek-erp-flask/deploy/DATABASE_MIGRATION.md` | Drag into **deploy/** |
| DEPLOY-FILES-CORRECTED.md | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\DEPLOY-FILES-CORRECTED.md` | `/var/www/maxek-erp-flask/deploy/DEPLOY-FILES-CORRECTED.md` | Drag into **deploy/** |
| DEPLOY-FILES-INDIVIDUAL.md | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\DEPLOY-FILES-INDIVIDUAL.md` | `/var/www/maxek-erp-flask/deploy/DEPLOY-FILES-INDIVIDUAL.md` | Drag into **deploy/** |
| DEPLOYMENT.md | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\DEPLOYMENT.md` | `/var/www/maxek-erp-flask/deploy/DEPLOYMENT.md` | Drag into **deploy/** |
| DEPLOY-WINSCP.md | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\DEPLOY-WINSCP.md` | `/var/www/maxek-erp-flask/deploy/DEPLOY-WINSCP.md` | Drag into **deploy/** |
| employee_master_edit_view_hotfix.zip | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\employee_master_edit_view_hotfix.zip` | `/var/www/maxek-erp-flask/deploy/employee_master_edit_view_hotfix.zip` | Drag into **deploy/** |
| EMPLOYEE_MASTER_HOTFIX.md | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\EMPLOYEE_MASTER_HOTFIX.md` | `/var/www/maxek-erp-flask/deploy/EMPLOYEE_MASTER_HOTFIX.md` | Drag into **deploy/** |
| employee_master_hotfix.zip | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\employee_master_hotfix.zip` | `/var/www/maxek-erp-flask/deploy/employee_master_hotfix.zip` | Drag into **deploy/** |
| fix_dpr_db.sql | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\fix_dpr_db.sql` | `/var/www/maxek-erp-flask/deploy/fix_dpr_db.sql` | Drag into **deploy/** |
| fix_workers_db.sql | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\fix_workers_db.sql` | `/var/www/maxek-erp-flask/deploy/fix_workers_db.sql` | Drag into **deploy/** |
| github_backup.env.example | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\github_backup.env.example` | `/var/www/maxek-erp-flask/deploy/github_backup.env.example` | Drag into **deploy/** |
| GITHUB_VPS_DEPLOY.md | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\GITHUB_VPS_DEPLOY.md` | `/var/www/maxek-erp-flask/deploy/GITHUB_VPS_DEPLOY.md` | Drag into **deploy/** |
| make_patch_zip.py | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\make_patch_zip.py` | `/var/www/maxek-erp-flask/deploy/make_patch_zip.py` | Drag into **deploy/** |
| maxek-erp.service | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\maxek-erp.service` | `/var/www/maxek-erp-flask/deploy/maxek-erp.service` | Drag into **deploy/** |
| maxek-erp-deploy.zip | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\maxek-erp-deploy.zip` | `/var/www/maxek-erp-flask/deploy/maxek-erp-deploy.zip` | Drag into **deploy/** |
| maxek-erp-deploy-MANIFEST.txt | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\maxek-erp-deploy-MANIFEST.txt` | `/var/www/maxek-erp-flask/deploy/maxek-erp-deploy-MANIFEST.txt` | Drag into **deploy/** |
| migrate_db.py | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\migrate_db.py` | `/var/www/maxek-erp-flask/deploy/migrate_db.py` | Drag into **deploy/** |
| migrate_production.py | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\migrate_production.py` | `/var/www/maxek-erp-flask/deploy/migrate_production.py` | Drag into **deploy/** |
| nginx-maxek-erp.conf | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\nginx-maxek-erp.conf` | `/var/www/maxek-erp-flask/deploy/nginx-maxek-erp.conf` | Drag into **deploy/** |
| PAYROLL_DB_MIGRATION.md | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\PAYROLL_DB_MIGRATION.md` | `/var/www/maxek-erp-flask/deploy/PAYROLL_DB_MIGRATION.md` | Drag into **deploy/** |
| post_deploy_test.sh | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\post_deploy_test.sh` | `/var/www/maxek-erp-flask/deploy/post_deploy_test.sh` | Drag into **deploy/** |
| STREAMLIT_TO_FLASK_MIGRATION.md | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\STREAMLIT_TO_FLASK_MIGRATION.md` | `/var/www/maxek-erp-flask/deploy/STREAMLIT_TO_FLASK_MIGRATION.md` | Drag into **deploy/** |
| test_login_compatibility.py | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\test_login_compatibility.py` | `/var/www/maxek-erp-flask/deploy/test_login_compatibility.py` | Drag into **deploy/** |
| UPDATE_FILES.txt | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\UPDATE_FILES.txt` | `/var/www/maxek-erp-flask/deploy/UPDATE_FILES.txt` | Drag into **deploy/** |
| upload-from-windows.ps1 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\upload-from-windows.ps1` | `/var/www/maxek-erp-flask/deploy/upload-from-windows.ps1` | Drag into **deploy/** |
| verify_staff_update.py | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\verify_staff_update.py` | `/var/www/maxek-erp-flask/deploy/verify_staff_update.py` | Drag into **deploy/** |
| verify_ui_on_vps.sh | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\verify_ui_on_vps.sh` | `/var/www/maxek-erp-flask/deploy/verify_ui_on_vps.sh` | Drag into **deploy/** |
| vps_backup.sh | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\vps_backup.sh` | `/var/www/maxek-erp-flask/deploy/vps_backup.sh` | Drag into **deploy/** |
| vps_backup_to_github.sh | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\vps_backup_to_github.sh` | `/var/www/maxek-erp-flask/deploy/vps_backup_to_github.sh` | Drag into **deploy/** |
| vps_fix_schema.sh | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\vps_fix_schema.sh` | `/var/www/maxek-erp-flask/deploy/vps_fix_schema.sh` | Drag into **deploy/** |
| VPS_PATCH_maxek-erp-flask.txt | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\VPS_PATCH_maxek-erp-flask.txt` | `/var/www/maxek-erp-flask/deploy/VPS_PATCH_maxek-erp-flask.txt` | Drag into **deploy/** |
| vps_pull_from_github.sh | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\vps_pull_from_github.sh` | `/var/www/maxek-erp-flask/deploy/vps_pull_from_github.sh` | Drag into **deploy/** |
| vps_setup.sh | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\vps_setup.sh` | `/var/www/maxek-erp-flask/deploy/vps_setup.sh` | Drag into **deploy/** |
| vps_update.sh | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\vps_update.sh` | `/var/www/maxek-erp-flask/deploy/vps_update.sh` | Drag into **deploy/** |
| VPS_UPDATE_RUNBOOK.md | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\VPS_UPDATE_RUNBOOK.md` | `/var/www/maxek-erp-flask/deploy/VPS_UPDATE_RUNBOOK.md` | Drag into **deploy/** |
| WINSCP_EXCLUDE.txt | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\WINSCP_EXCLUDE.txt` | `/var/www/maxek-erp-flask/deploy/WINSCP_EXCLUDE.txt` | Drag into **deploy/** |
| WINSCP_maxek-erp-flask.txt | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\WINSCP_maxek-erp-flask.txt` | `/var/www/maxek-erp-flask/deploy/WINSCP_maxek-erp-flask.txt` | Drag into **deploy/** |
| WINSCP_UPLOAD_MANIFEST.txt | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\WINSCP_UPLOAD_MANIFEST.txt` | `/var/www/maxek-erp-flask/deploy/WINSCP_UPLOAD_MANIFEST.txt` | Drag into **deploy/** |
| WINSCP-PATH-MAP.md | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\WINSCP-PATH-MAP.md` | `/var/www/maxek-erp-flask/deploy/WINSCP-PATH-MAP.md` | Drag into **deploy/** |
| worker-sub-crud-patch.zip | `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\worker-sub-crud-patch.zip` | `/var/www/maxek-erp-flask/deploy/worker-sub-crud-patch.zip` | Drag into **deploy/** |

**Optional (only when applying a documented hotfix):** upload matching files from `deploy\employee_master_edit_view_hotfix\`, `deploy\hotfix_employee_master\`, etc., to the same paths under `/var/www/maxek-erp-flask/` (not only under `deploy/`).

**Optional archives (usually upload to `deploy/` then unzip on VPS):** `maxek-erp-deploy.zip`, `worker-sub-crud-patch.zip`, `employee_master_*.zip` — prefer full folder sync above instead of zip for routine updates.

---

## Full deploy checklist (counts)

| Area | File count |
|------|------------|
| App root | 4 |
| templates/ (incl. macros) | 32 |
| static/js/ | 11 |
| static/css/ | 3 |
| static/images/ | 1 |
| deploy/ (top-level scripts & docs) | 47 |
| **Typical full sync total** | **98** |

---

## Path prefix reference

- Windows full prefix: `C:\Users\rajee\Documents\New project\MAXEK_ERP\`
- Linux full prefix: `/var/www/maxek-erp-flask/`

Related: `deploy\DEPLOY-WINSCP.md`, `deploy\WINSCP_UPLOAD_MANIFEST.txt`, `deploy\WINSCP_EXCLUDE.txt`
