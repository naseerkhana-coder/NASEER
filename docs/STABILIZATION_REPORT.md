# MAXEK ERP Stabilization Report

**Date:** 2026-06-28  
**Scope:** Critical stabilization (no new features)  
**VPS:** erp.maxekindia.com → `/var/www/maxek-erp-flask`

## Summary checklist

| # | Section | Status | Notes |
|---|---------|--------|-------|
| 1 | Test Data Recovery | **DONE** | Reset script + `docs/MASTER_DATA_POST_RESET.md` |
| 2 | Dashboard Issues | **DONE** | Dept tile dedupe + prefs filter wired |
| 3 | Module Toolbar | **PARTIAL** | Standard toolbar macro exists; not all pro modules wired |
| 4 | Company Bank Fields | **DONE** | Schema + form + save in company master |
| 5 | Customer Creation | **DONE** | Required Customer Admin with email/mobile |
| 6 | Login Branding | **DONE** | Larger logo + tenant preview API |
| 7 | Customer Settings | **DONE** | Tenant branding block in Settings |
| 8 | Missing Module Functions | **NEEDS VPS TEST** | Dept portals defined; spot-check nav on VPS |
| 9 | Data Safety | **DONE** | Super Admin gates on delete/restore |
| 10 | Final QA | **PARTIAL** | Local pytest run; full UI needs VPS |

---

## 1. Test Data Recovery — DONE

- Script: `scripts/reset_operational_data.py`
- Master preservation documented in `docs/MASTER_DATA_POST_RESET.md`
- Re-seed: departments, designations, workflow_master, chart_of_accounts

## 2. Dashboard — DONE

- `get_command_centre_cards()` dedupes by canonical department slug
- Enabled departments normalized via alias map (fixes duplicate tiles)
- `filter_command_centre_dept_cards()` applied from user favourite modules
- Cards link with canonical slug → `/dept/<slug>`

## 3. Module Toolbar — PARTIAL

- `erp_module_toolbar` macro: New, Search, Export Excel, Print
- Full standard (Open, View, Edit, Delete, filters, PDF, Refresh, Run Report) varies by module
- **VPS test:** Projects, Store, Accounts pro-shell pages

## 4. Company Bank Fields — DONE

Added to `companies` table and Company Master form:

- Bank Name, Branch Name, Branch Address, Account Name, Account Number, IFSC
- SWIFT, MICR, UPI (optional)

## 5. Customer Creation — DONE

- New customers require Customer Administrator: username, password, email, mobile
- `create_customer_admin_user()` stores email/mobile on `users`
- Customer delete remains Super Admin only (`erp_admin_routes`)

## 6. Login Branding — DONE

- Left panel logo 56px; sign-in card shows tenant block (72px logo)
- `GET /login/branding?company_code=` for live preview
- `static/js/login.js` debounced company code lookup

## 7. Customer Settings — DONE

- `erp_customers`: logo_path, theme, address, financial_year, currency, timezone
- Settings → **Tenant Branding & Regional Settings** (Customer Admin)

## 8. Missing Module Functions — NEEDS VPS TEST

Department portals configured in `ui_shell_config.py` / `get_department_portals()`.

**Manual VPS checks:** Project, Planning, BOQ, DPR, Store, Purchase, MR, Accounts, HR, Fleet, Plant, Reports — open each `/dept/<slug>` and one tool link.

## 9. Data Safety — DONE

| Action | Guard |
|--------|-------|
| Delete customer | Super Admin + confirm (`erp_admin_customers`) |
| Delete company | Super Admin + audit log |
| Backup restore/delete | Super Admin only |
| Operational reset | CLI `--confirm RESET` only (not in UI) |

## 10. Final QA — PARTIAL

Run locally: `python -m pytest tests/ -q`

---

## VPS manual test priority

1. Login page — enter company code, confirm large tenant branding
2. Dashboard — no duplicate department tiles; each opens correct portal
3. Register customer — Customer Admin auto-created; login works
4. Company Master — save bank fields; reload record
5. Settings (Customer Admin) — tenant branding save
6. Treasury → Backup — restore/delete hidden unless Super Admin
7. Super Admin — delete customer with confirmation

---

## VPS deploy bundle (this stabilization)

Copy **same commit** together:

```bash
APP=/var/www/maxek-erp-flask
SRC=/tmp/maxek-pull   # git clone at stabilization commit

cp "$SRC/app.py" "$SRC/super_admin_service.py" "$SRC/company_master_service.py" \
   "$SRC/erp_admin_routes.py" "$SRC/treasury_routes.py" "$SRC/ui_shell_config.py" \
   "$SRC/dashboard_prefs_service.py" "$APP/"

cp "$SRC/templates/dashboard.html" "$SRC/templates/login.html" \
   "$SRC/templates/company_master.html" "$SRC/templates/settings.html" \
   "$SRC/templates/erp_admin/customers.html" \
   "$SRC/templates/treasury/backup_system.html" \
   "$APP/templates/" 2>/dev/null || true

mkdir -p "$APP/templates/erp_admin" "$APP/templates/treasury"
cp "$SRC/templates/erp_admin/customers.html" "$APP/templates/erp_admin/"
cp "$SRC/templates/treasury/backup_system.html" "$APP/templates/treasury/"

cp "$SRC/static/css/maxek-login.css" "$APP/static/css/"
cp "$SRC/static/js/login.js" "$APP/static/js/"
cp "$SRC/docs/MASTER_DATA_POST_RESET.md" "$SRC/docs/STABILIZATION_REPORT.md" "$APP/docs/" 2>/dev/null || mkdir -p "$APP/docs" && cp "$SRC/docs/"*.md "$APP/docs/"

sudo chown -R www-data:www-data "$APP"
sudo systemctl restart maxek-erp
journalctl -u maxek-erp -n 40 --no-pager
```

See also `deploy/VPS_DEPLOY_APP_PY_BUNDLE.md` for import dependencies when updating `app.py`.
