# MAXEK ERP — Corrected deploy file list (WinSCP, no zip)

**Generated from:** `git status` on branch `codex/employee-master-edit-view` (local working tree)  
**VPS app root:** `/var/www/maxek-erp-flask/`  
**Local project root:** `C:\Users\rajee\Documents\New project\MAXEK_ERP\`  
**Service after upload:** `sudo systemctl restart maxek-erp`

Upload files **individually** in WinSCP (drag one file → confirm overwrite). Do **not** upload folders that contain secrets or junk (see [Exclude](#exclude-do-not-upload)).

---

## Feature areas covered

| Area | Key paths |
|------|-----------|
| HR Employee Master | `app.py`, `templates/staff.html`, `static/js/staff-forms.js`, `static/js/master-forms.js` |
| Staff Bonus | `templates/staff_bonus.html`, `static/js/staff-bonus.js` |
| Timezone | `app.py`, `templates/settings.html`, `static/js/app.js` |
| Dashboard UI / sub-tabs / hub | `templates/dashboard.html`, `templates/department_hub.html`, `static/css/maxek-dashboard.css`, `static/js/maxek-ui.js`, `templates/macros/erp_ui.html` |
| Branding / logo | `static/images/maxek-logo.png`, `static/css/maxek-login.css`, `templates/login.html`, `templates/forgot_password.html`, `templates/base_maxek.html`, `templates/dashboard_choice_b.html` |
| DPR (measurements, upload, view, FRS) | `app.py`, `templates/dpr.html`, `templates/dpr_client_bill_print.html`, `static/js/dpr-forms.js`, `deploy/fix_dpr_db.sql` |
| Subbar / shell fixes | `templates/base_maxek.html`, `static/js/maxek-ui.js`, `static/css/maxek-dashboard.css` |
| Workers / subcontractors | `templates/workers.html`, `templates/subcontractors.html`, `static/js/workers-form.js`, `static/js/subcontractors.js` |
| Attendance | `templates/attendance.html`, `static/js/attendance-form.js` |

---

## Minimum set vs full set

| Set | Count | When to use |
|-----|-------|-------------|
| **Minimum** | 12 files | Hotfix or narrow change; backend + one page per feature |
| **Recommended** | 39 files | Normal release for HR + DPR + dashboard + branding (this list) |
| **Full** | 39 app + 4 deploy SQL/migrate + 1 optional doc | Same as recommended + run DB scripts on VPS |

### Minimum set (12) — upload these first

| # | Local Windows path | VPS remote path |
|---|-------------------|-----------------|
| 1 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\app.py` | `/var/www/maxek-erp-flask/app.py` |
| 2 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\base_maxek.html` | `/var/www/maxek-erp-flask/templates/base_maxek.html` |
| 3 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\dashboard.html` | `/var/www/maxek-erp-flask/templates/dashboard.html` |
| 4 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\settings.html` | `/var/www/maxek-erp-flask/templates/settings.html` |
| 5 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\staff.html` | `/var/www/maxek-erp-flask/templates/staff.html` |
| 6 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\staff_bonus.html` | `/var/www/maxek-erp-flask/templates/staff_bonus.html` |
| 7 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\templates\dpr.html` | `/var/www/maxek-erp-flask/templates/dpr.html` |
| 8 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\static\css\maxek-dashboard.css` | `/var/www/maxek-erp-flask/static/css/maxek-dashboard.css` |
| 9 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\static\js\app.js` | `/var/www/maxek-erp-flask/static/js/app.js` |
| 10 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\static\js\maxek-ui.js` | `/var/www/maxek-erp-flask/static/js/maxek-ui.js` |
| 11 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\static\js\staff-forms.js` | `/var/www/maxek-erp-flask/static/js/staff-forms.js` |
| 12 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\static\js\dpr-forms.js` | `/var/www/maxek-erp-flask/static/js/dpr-forms.js` |

Add `workflow_service.py`, `wsgi.py` if you changed workflow or WSGI (both are modified in git).

---

## Full recommended set — by folder

**Legend:** Required = **Y** (upload for this release), **N** (optional reference only)

### App root → `/var/www/maxek-erp-flask/`

| # | Local Windows path | VPS remote path | Feature area | Req |
|---|-------------------|-----------------|--------------|-----|
| 1 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\app.py` | `/var/www/maxek-erp-flask/app.py` | Core API — HR, bonus, DPR, timezone | Y |
| 2 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\workflow_service.py` | `/var/www/maxek-erp-flask/workflow_service.py` | Workflow engine | Y |
| 3 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\wsgi.py` | `/var/www/maxek-erp-flask/wsgi.py` | Gunicorn entry | Y |
| 4 | `C:\Users\rajee\Documents\New project\MAXEK_ERP\requirements.txt` | `/var/www/maxek-erp-flask/requirements.txt` | Python deps (only if you added packages) | N |

### templates/ → `/var/www/maxek-erp-flask/templates/`

| # | Local Windows path | VPS remote path | Feature area | Req |
|---|-------------------|-----------------|--------------|-----|
| 5 | `...\templates\base_maxek.html` | `templates/base_maxek.html` | Shell, nav, subbar | Y |
| 6 | `...\templates\macros\erp_ui.html` | `templates/macros/erp_ui.html` | UI macros / sub-tabs | Y |
| 7 | `...\templates\department_hub.html` | `templates/department_hub.html` | Department hub landing | Y |
| 8 | `...\templates\dashboard.html` | `templates/dashboard.html` | Main dashboard | Y |
| 9 | `...\templates\dashboard_choice_b.html` | `templates/dashboard_choice_b.html` | Dashboard variant / branding | Y |
| 10 | `...\templates\login.html` | `templates/login.html` | Login branding | Y |
| 11 | `...\templates\forgot_password.html` | `templates/forgot_password.html` | Login branding | Y |
| 12 | `...\templates\settings.html` | `templates/settings.html` | Timezone & settings UI | Y |
| 13 | `...\templates\staff.html` | `templates/staff.html` | HR employee master | Y |
| 14 | `...\templates\staff_bonus.html` | `templates/staff_bonus.html` | Staff bonus | Y |
| 15 | `...\templates\attendance.html` | `templates/attendance.html` | HR attendance | Y |
| 16 | `...\templates\timesheet.html` | `templates/timesheet.html` | HR timesheet | Y |
| 17 | `...\templates\workers.html` | `templates/workers.html` | Workers master | Y |
| 18 | `...\templates\subcontractors.html` | `templates/subcontractors.html` | Subcontractors | Y |
| 19 | `...\templates\projects.html` | `templates/projects.html` | Projects (DPR link) | Y |
| 20 | `...\templates\clients.html` | `templates/clients.html` | Clients (DPR billing) | Y |
| 21 | `...\templates\users.html` | `templates/users.html` | Admin users | Y |
| 22 | `...\templates\notifications.html` | `templates/notifications.html` | Notifications | Y |
| 23 | `...\templates\boq.html` | `templates/boq.html` | BOQ module | Y |
| 24 | `...\templates\dpr.html` | `templates/dpr.html` | DPR main UI | Y |
| 25 | `...\templates\dpr_client_bill_print.html` | `templates/dpr_client_bill_print.html` | DPR print / client bill | Y |

*Prefix `...` = `C:\Users\rajee\Documents\New project\MAXEK_ERP`*

### static/js/ → `/var/www/maxek-erp-flask/static/js/`

| # | Local Windows path | VPS remote path | Feature area | Req |
|---|-------------------|-----------------|--------------|-----|
| 26 | `...\static\js\app.js` | `static/js/app.js` | Core client / timezone | Y |
| 27 | `...\static\js\maxek-ui.js` | `static/js/maxek-ui.js` | Dashboard UI / subbar | Y |
| 28 | `...\static\js\workflow.js` | `static/js/workflow.js` | Workflow client | Y |
| 29 | `...\static\js\master-forms.js` | `static/js/master-forms.js` | Shared master forms | Y |
| 30 | `...\static\js\attendance-form.js` | `static/js/attendance-form.js` | Attendance UX | Y |
| 31 | `...\static\js\staff-forms.js` | `static/js/staff-forms.js` | HR employee CRUD | Y |
| 32 | `...\static\js\staff-bonus.js` | `static/js/staff-bonus.js` | Staff bonus | Y |
| 33 | `...\static\js\dpr-forms.js` | `static/js/dpr-forms.js` | DPR measurements / upload / view | Y |
| 34 | `...\static\js\workers-form.js` | `static/js/workers-form.js` | Workers forms | Y |
| 35 | `...\static\js\subcontractors.js` | `static/js/subcontractors.js` | Subcontractors | Y |
| 36 | `...\static\js\boq-forms.js` | `static/js/boq-forms.js` | BOQ forms | Y |

### static/css/ → `/var/www/maxek-erp-flask/static/css/`

| # | Local Windows path | VPS remote path | Feature area | Req |
|---|-------------------|-----------------|--------------|-----|
| 37 | `...\static\css\maxek-dashboard.css` | `static/css/maxek-dashboard.css` | Dashboard / sub-tabs styling | Y |
| 38 | `...\static\css\maxek-login.css` | `static/css/maxek-login.css` | Login branding | Y |

### static/images/ → `/var/www/maxek-erp-flask/static/images/`

| # | Local Windows path | VPS remote path | Feature area | Req |
|---|-------------------|-----------------|--------------|-----|
| 39 | `...\static\images\maxek-logo.png` | `static/images/maxek-logo.png` | Logo branding | Y |

### docs/ → `/var/www/maxek-erp-flask/docs/` (optional on server)

| # | Local Windows path | VPS remote path | Feature area | Req |
|---|-------------------|-----------------|--------------|-----|
| 40 | `...\docs\DPR-FRS-GAP-ANALYSIS.md` | `docs/DPR-FRS-GAP-ANALYSIS.md` | DPR FRS reference | N |

### deploy/ → `/var/www/maxek-erp-flask/deploy/` (run on SSH, not served)

| # | Local Windows path | VPS remote path | Feature area | Req |
|---|-------------------|-----------------|--------------|-----|
| 41 | `...\deploy\vps_fix_schema.sh` | `deploy/vps_fix_schema.sh` | Schema repair script | Y |
| 42 | `...\deploy\migrate_production.py` | `deploy/migrate_production.py` | Production migration | Y |
| 43 | `...\deploy\fix_dpr_db.sql` | `deploy/fix_dpr_db.sql` | DPR DB patches | Y |
| 44 | `...\deploy\fix_workers_db.sql` | `deploy/fix_workers_db.sql` | Workers DB patches | Y |
| 45 | `...\deploy\DEPLOY-FILES-CORRECTED.md` | `deploy/DEPLOY-FILES-CORRECTED.md` | This checklist | N |

**Totals:** 39 required application files + 4 deploy helpers (43 upload targets); 2 optional (requirements.txt if changed, FRS doc).

---

## Git working tree reference (modified / new)

These match `git status` as of this document:

**Modified:** `app.py`, `workflow_service.py`, `wsgi.py`, `static/css/maxek-dashboard.css`, `static/css/maxek-login.css`, `static/js/app.js`, `static/js/maxek-ui.js`, `static/js/workflow.js`, `templates/*` (attendance, base_maxek, clients, dashboard, dashboard_choice_b, forgot_password, login, macros/erp_ui, notifications, projects, settings, staff, subcontractors, timesheet, users, workers), `deploy/UPDATE_FILES.txt`, `deploy/WINSCP_UPLOAD_MANIFEST.txt`

**New (untracked, include in upload):** `static/js/attendance-form.js`, `static/js/boq-forms.js`, `static/js/dpr-forms.js`, `static/js/master-forms.js`, `static/js/staff-bonus.js`, `static/js/staff-forms.js`, `static/js/subcontractors.js`, `static/js/workers-form.js`, `static/images/maxek-logo.png`, `templates/boq.html`, `templates/department_hub.html`, `templates/dpr.html`, `templates/dpr_client_bill_print.html`, `templates/staff_bonus.html`, `docs/DPR-FRS-GAP-ANALYSIS.md`, deploy SQL/fix scripts listed above

---

## Exclude (do not upload)

| Path | Reason |
|------|--------|
| `patches/` | Local patch build artifacts |
| `node_modules/` | Not used on VPS Flask app |
| `.env`, `deploy/github_backup.env` (real secrets) | Production secrets stay on server |
| `database/maxek.db`, `database/*.db` | Production data — backup on VPS only |
| `venv/`, `.venv/`, `__pycache__/`, `*.pyc` | Rebuild on server |
| `deploy/package_*`, `deploy/_staging_*`, `deploy/dist/` | Staging/zips |
| `.tmp-browser-artifacts/`, `_browser_probe_out/` | Debug |
| `live-dashboard.html` (repo root) | Local probe artifact |
| `../_github_push/` | Outside app tree |

---

## Post-upload SSH commands

```bash
ssh root@srv1704727
cd /var/www/maxek-erp-flask

# Backup DB before schema work
cp database/maxek.db database/maxek.db.bak-$(date +%Y%m%d-%H%M) 2>/dev/null || true

source .venv/bin/activate 2>/dev/null || source venv/bin/activate
export MAXEK_SKIP_DEMO_SEED=1

bash deploy/vps_fix_schema.sh /var/www/maxek-erp-flask
python3 deploy/migrate_production.py

sqlite3 database/maxek.db < deploy/fix_dpr_db.sql
sqlite3 database/maxek.db < deploy/fix_workers_db.sql

# Upload directories (preserve existing files)
sudo mkdir -p static/uploads/dpr static/uploads/staff static/uploads/workers static/uploads/subcontractors
sudo chown -R www-data:www-data database static/uploads
sudo chmod -R u+rwX,g+rwX static/uploads

sudo systemctl restart maxek-erp
sudo systemctl status maxek-erp --no-pager
journalctl -u maxek-erp -n 50 --no-pager

# Quick sanity checks
grep -n staff_bonus app.py | head -3
grep -n dpr app.py | head -3
grep -n timezone app.py | head -3
test -f templates/staff_bonus.html && test -f templates/dpr.html && test -f static/js/dpr-forms.js && test -f static/images/maxek-logo.png && echo "Key assets OK"
```

---

## WinSCP tips

1. Remote pane: open `/var/www/maxek-erp-flask/`.
2. Local pane: `C:\Users\rajee\Documents\New project\MAXEK_ERP\`.
3. Upload **one file**; confirm **Overwrite** when prompted.
4. Create remote folders once if missing: `static/images/`, `static/uploads/dpr/`, `docs/`.
5. After all **Y** files: run SSH block above, then hard-refresh browser (Ctrl+F5).

---

## Related docs

- `deploy/DEPLOY-FILES-INDIVIDUAL.md` — shorter checklist
- `deploy/UPDATE_FILES.txt` — legacy list (superseded by this file for VPS path `maxek-erp-flask`)
