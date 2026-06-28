# VPS deploy — partial `app.py` bundle (avoid 502 import errors)

**Symptom:** gunicorn crash / 502 — `cannot import name 'get_customer_enabled_departments' from 'super_admin_service'`

**Cause:** Deploying `app.py` (or `company_master_service.py`) without the Python modules that `app.py` imports at startup. Partial file copies from a newer commit leave older `*_service.py` files on the VPS.

**App path:** `/var/www/maxek-erp-flask/`  
**Service:** `maxek-erp` (or `maxek-erp-flask` on some hosts)

---

## Restore site NOW (minimal)

Copy **at least** `super_admin_service.py` — this defines `get_customer_enabled_departments` (added in commit `a16b452`).

Also copy `erp_admin_routes.py` if customer package / department toggles in ERP Admin were never deployed (same commit).

```bash
APP=/var/www/maxek-erp-flask
SRC=/tmp/maxek-pull   # or path after re-clone below

# If /tmp/maxek-pull is missing, re-clone first (see below), then:

cp "$SRC/super_admin_service.py" "$APP/"
cp "$SRC/erp_admin_routes.py" "$APP/"   # recommended with super_admin

sudo chown www-data:www-data "$APP/super_admin_service.py" "$APP/erp_admin_routes.py"
sudo systemctl restart maxek-erp
sudo systemctl status maxek-erp --no-pager
journalctl -u maxek-erp -n 30 --no-pager   # confirm no ImportError
```

### Re-clone one-liner (if `/tmp/maxek-pull` is gone)

```bash
rm -rf /tmp/maxek-pull && git clone --depth 1 https://github.com/YOUR_ORG/MAXEK_ERP.git /tmp/maxek-pull
# Or from a specific commit:
# git clone https://github.com/YOUR_ORG/MAXEK_ERP.git /tmp/maxek-pull && cd /tmp/maxek-pull && git checkout ed26b98
```

Replace the repo URL with your actual remote. From Windows you can also `scp` individual files:

```powershell
scp super_admin_service.py erp_admin_routes.py root@72.61.224.204:/var/www/maxek-erp-flask/
```

---

## Full bundle when deploying current `app.py`

Whenever you upload a new `app.py`, copy these **together** (same git commit):

| Priority | File | Why |
|----------|------|-----|
| **Required** | `super_admin_service.py` | `get_customer_enabled_departments`, limits, tenant auth |
| **Required** | `erp_admin_routes.py` | Imports `get_customer_enabled_departments`; customer package UI |
| **Required** | `ui_shell_config.py` | Shell nav, department portals, dashboard tiles (`app.py` imports ~20 symbols) |
| **Required** | `user_permission_service.py` | Department tab permissions (`filter_portal_menu_for_user`, etc.) |
| **Required** | `dashboard_prefs_service.py` | Command centre KPI/card filtering |
| Often | `company_master_service.py` | Bank fields, branch limits, `super_admin_service` |
| Often | `treasury_routes.py` | Backup restore/delete Super Admin guard |
| Template | `templates/erp_admin/customers.html` | Customer Admin onboarding (required fields) |
| Template | `templates/company_master.html` | Bank account fields |
| Template | `templates/login.html`, `static/css/maxek-login.css`, `static/js/login.js` | Login tenant branding |
| Template | `templates/settings.html` | Tenant branding settings |
| Template | `templates/treasury/backup_system.html` | Super Admin restore/delete UI |
| Docs | `docs/STABILIZATION_REPORT.md`, `docs/MASTER_DATA_POST_RESET.md` | Stabilization checklist |

### `app.py` local import map (startup)

These modules are imported when gunicorn loads `app.py` (must exist and export every symbol listed in `app.py`):

```
ui_shell_config          → shell / nav / department portals
super_admin_service      → tenant admin, limits, get_customer_enabled_departments
erp_admin_routes         → register_erp_admin_routes
api_routes               → register_api_routes
ai_routes                → register_ai_routes
erp_platform_routes      → erp_platform_bp
auth_jwt                 → ensure_jwt_schema
tenant_isolation         → ensure_tenant_isolation_schema
user_context_service     → context switcher
user_permission_service  → tab permissions
badge_counts_service     → live badges
attachment_service       → attachments schema
audit_trail_service      → audit log
dashboard_prefs_service  → dashboard preferences
company_master_service   → companies / branches / GST / directors
+ cost_planning, payroll, attendance, accounts, treasury, store, workflow, … (domain services)
```

**Rule:** If you change `app.py` imports or any symbol used at module level, deploy the matching module from the **same commit**. Prefer full zip deploy (`deploy/VPS_DEPLOY_FROM_ZIP.md`) over cherry-picking files.

---

## Verify after restart

```bash
curl -sI http://127.0.0.1:5000/login | head -1    # adjust port if needed
sudo journalctl -u maxek-erp -n 50 --no-pager | grep -i import
```

Log in → `/dashboard` → ERP Admin → Customers (department checkboxes should load if `erp_admin_routes` + template were updated).

---

## Related docs

- `deploy/VPS_DEPLOY_DEPARTMENT_PORTALS.md` — `ui_shell_config.py` + `user_permission_service.py` + `app.py`
- `deploy/VPS_DEPLOY_FROM_ZIP.md` — full safe deploy from zip
