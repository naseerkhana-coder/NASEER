# MAXEK ERP — Individual file upload (WinSCP)

Upload **one file at a time** (no zip). Overwrite existing files on the VPS.

| Setting | Value |
|---------|--------|
| **VPS** | `root@srv1704727` |
| **Remote app root** | `/var/www/maxek-erp-flask/` |
| **Local project root** | `C:\Users\rajee\Documents\New project\MAXEK_ERP\` |

**Do not upload:** `database/maxek.db`, `.env`, `venv/`, `.venv/`, `__pycache__/`, `deploy/package_*`, `deploy/_staging_*`, `.tmp-browser-artifacts/`

---

## Checklist (tick when uploaded)

### App root
- [ ] `app.py`
- [ ] `workflow_service.py`
- [ ] `wsgi.py`

### templates/
- [ ] `base_maxek.html`
- [ ] `department_hub.html`
- [ ] `dashboard.html`
- [ ] `settings.html`
- [ ] `staff.html`
- [ ] `staff_bonus.html`
- [ ] `attendance.html`
- [ ] `timesheet.html`
- [ ] `workers.html`
- [ ] `subcontractors.html`
- [ ] `projects.html`
- [ ] `clients.html`
- [ ] `users.html`
- [ ] `notifications.html`
- [ ] `boq.html`
- [ ] `dpr.html`
- [ ] `dpr_client_bill_print.html`
- [ ] `macros/erp_ui.html`

### static/js/
- [ ] `app.js`
- [ ] `workflow.js`
- [ ] `master-forms.js`
- [ ] `attendance-form.js`
- [ ] `staff-forms.js`
- [ ] `staff-bonus.js`
- [ ] `dpr-forms.js`
- [ ] `workers-form.js`
- [ ] `subcontractors.js`
- [ ] `boq-forms.js`

### static/css/
- [ ] `maxek-dashboard.css`

### deploy/ (upload then run on SSH)
- [ ] `deploy/vps_fix_schema.sh`
- [ ] `deploy/migrate_production.py`
- [ ] `deploy/fix_dpr_db.sql`
- [ ] `deploy/fix_workers_db.sql`

---

## App root → `/var/www/maxek-erp-flask/`

| Local path (Windows) | Remote path | Feature |
|----------------------|-------------|---------|
| `C:\Users\rajee\Documents\New project\MAXEK_ERP\app.py` | `/var/www/maxek-erp-flask/app.py` | Core — HR, bonus, DPR, timezone |
| `C:\Users\rajee\Documents\New project\MAXEK_ERP\workflow_service.py` | `/var/www/maxek-erp-flask/workflow_service.py` | Workflow |
| `C:\Users\rajee\Documents\New project\MAXEK_ERP\wsgi.py` | `/var/www/maxek-erp-flask/wsgi.py` | Gunicorn entry |

## templates/ → `/var/www/maxek-erp-flask/templates/`

| Local path | Remote path | Feature |
|------------|-------------|---------|
| `...\templates\base_maxek.html` | `templates/base_maxek.html` | Nav / shell |
| `...\templates\department_hub.html` | `templates/department_hub.html` | HR hub |
| `...\templates\dashboard.html` | `templates/dashboard.html` | Dashboard |
| `...\templates\settings.html` | `templates/settings.html` | Timezone UI |
| `...\templates\staff.html` | `templates/staff.html` | HR staff |
| `...\templates\staff_bonus.html` | `templates/staff_bonus.html` | Bonus |
| `...\templates\attendance.html` | `templates/attendance.html` | HR attendance |
| `...\templates\timesheet.html` | `templates/timesheet.html` | HR timesheet |
| `...\templates\workers.html` | `templates/workers.html` | Workers |
| `...\templates\subcontractors.html` | `templates/subcontractors.html` | Subcontractors |
| `...\templates\projects.html` | `templates/projects.html` | Projects (DPR) |
| `...\templates\clients.html` | `templates/clients.html` | Clients (DPR bill) |
| `...\templates\users.html` | `templates/users.html` | Admin users |
| `...\templates\notifications.html` | `templates/notifications.html` | Notifications |
| `...\templates\boq.html` | `templates/boq.html` | BOQ |
| `...\templates\dpr.html` | `templates/dpr.html` | DPR |
| `...\templates\dpr_client_bill_print.html` | `templates/dpr_client_bill_print.html` | DPR print |
| `...\templates\macros\erp_ui.html` | `templates/macros/erp_ui.html` | UI macros |

Use full prefix: `C:\Users\rajee\Documents\New project\MAXEK_ERP` instead of `...`.

## static/js/ → `/var/www/maxek-erp-flask/static/js/`

| Local path | Remote path | Feature |
|------------|-------------|---------|
| `...\static\js\app.js` | `static/js/app.js` | Core / timezone client |
| `...\static\js\workflow.js` | `static/js/workflow.js` | Workflow |
| `...\static\js\master-forms.js` | `static/js/master-forms.js` | Shared forms |
| `...\static\js\attendance-form.js` | `static/js/attendance-form.js` | HR attendance |
| `...\static\js\staff-forms.js` | `static/js/staff-forms.js` | HR staff CRUD |
| `...\static\js\staff-bonus.js` | `static/js/staff-bonus.js` | Bonus |
| `...\static\js\dpr-forms.js` | `static/js/dpr-forms.js` | DPR |
| `...\static\js\workers-form.js` | `static/js/workers-form.js` | Workers |
| `...\static\js\subcontractors.js` | `static/js/subcontractors.js` | Subcontractors |
| `...\static\js\boq-forms.js` | `static/js/boq-forms.js` | BOQ |

## static/css/ → `/var/www/maxek-erp-flask/static/css/`

| Local path | Remote path | Feature |
|------------|-------------|---------|
| `...\static\css\maxek-dashboard.css` | `static/css/maxek-dashboard.css` | Dashboard styling |

## deploy/ → `/var/www/maxek-erp-flask/deploy/`

| Local path | Remote path | Feature |
|------------|-------------|---------|
| `...\deploy\vps_fix_schema.sh` | `deploy/vps_fix_schema.sh` | DB schema repair |
| `...\deploy\migrate_production.py` | `deploy/migrate_production.py` | DB migration |
| `...\deploy\fix_dpr_db.sql` | `deploy/fix_dpr_db.sql` | DPR SQL patches |
| `...\deploy\fix_workers_db.sql` | `deploy/fix_workers_db.sql` | Workers SQL patches |

---

## After upload — SSH

```bash
ssh root@srv1704727
cd /var/www/maxek-erp-flask

cp database/maxek.db database/maxek.db.bak-manual

source .venv/bin/activate 2>/dev/null || source venv/bin/activate
export MAXEK_SKIP_DEMO_SEED=1
bash deploy/vps_fix_schema.sh /var/www/maxek-erp-flask
python3 deploy/migrate_production.py

sqlite3 database/maxek.db < deploy/fix_dpr_db.sql
sqlite3 database/maxek.db < deploy/fix_workers_db.sql

sudo systemctl restart maxek-erp
sudo systemctl status maxek-erp --no-pager

grep -n staff_bonus app.py | head -5
grep -n dpr app.py | head -5
grep -n timezone app.py | head -5
test -f templates/staff_bonus.html && test -f templates/dpr.html && test -f static/js/dpr-forms.js && echo "Key HR/DPR assets OK"
```

---

## Partial upload — top 3

1. `app.py` — all backend routes and timezone logic
2. `templates/dpr.html` — DPR page
3. `static/js/dpr-forms.js` — DPR UI logic

For bonus add `templates/staff_bonus.html` and `static/js/staff-bonus.js`. For timezone add `templates/settings.html` and `static/js/app.js`.

---

## Summary

| | |
|--|--|
| Application files | 32 |
| Deploy helpers | 4 |
| **Total** | **36** |
| This guide | `deploy/DEPLOY-FILES-INDIVIDUAL.md` |

`requirements.txt` unchanged in git — skip unless you added Python packages.
