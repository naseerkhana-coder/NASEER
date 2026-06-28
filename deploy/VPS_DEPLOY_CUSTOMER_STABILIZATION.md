# VPS deploy — Customer Management stabilization

**App path:** `/var/www/maxek-erp-flask/`

## Summary

Standard CRUD toolbar on Customer Master, cascade delete for super admin, per-customer settings route, ERP admin subbar deduplication, and company bank label fix.

## Files to upload

| File | Purpose |
|------|---------|
| `super_admin_service.py` | Cascade delete; `email_settings` column; tenant settings save |
| `erp_admin_routes.py` | Customer settings route; cascade delete POST; view mode |
| `app.py` | Import `ERP_ADMIN_ACTIVE_ENDPOINTS`; inject into templates; timezone for settings |
| `templates/macros/erp_ui.html` | `erp_module_toolbar` `mode='standard'` |
| `templates/erp_admin/customers.html` | Standard toolbar; row selection; Settings link |
| `templates/erp_admin/customer_settings.html` | **New** — tenant branding/settings form |
| `templates/base_maxek.html` | Hide department subbar on ERP admin endpoints |
| `templates/company_master.html` | Account Holder label |
| `static/js/maxek-ui.js` | Standard toolbar wiring (New/Open/View/Edit/Delete/sort/filter) |
| `static/css/maxek-dashboard.css` | Toolbar flex-wrap and filter controls |

## Quick sync (from dev PC)

```bash
scp super_admin_service.py erp_admin_routes.py app.py root@72.61.224.204:/var/www/maxek-erp-flask/
scp templates/macros/erp_ui.html root@72.61.224.204:/var/www/maxek-erp-flask/templates/macros/
scp templates/erp_admin/customers.html templates/erp_admin/customer_settings.html root@72.61.224.204:/var/www/maxek-erp-flask/templates/erp_admin/
scp templates/base_maxek.html templates/company_master.html root@72.61.224.204:/var/www/maxek-erp-flask/templates/
scp static/js/maxek-ui.js root@72.61.224.204:/var/www/maxek-erp-flask/static/js/
scp static/css/maxek-dashboard.css root@72.61.224.204:/var/www/maxek-erp-flask/static/css/
```

## Restart

```bash
ssh root@72.61.224.204 "systemctl restart maxek-erp-flask"
```

## Smoke test (super admin)

1. `/erp-admin/customers` — single toolbar row (New … Refresh); no duplicate department subbar.
2. Select a row → Open/View/Edit/Delete enable.
3. **New** customer with admin user → redirect to list; admin can log in with customer code + username + password.
4. **Delete** customer with users → confirm mentions user removal → succeeds (cascade).
5. **Settings** on a row → `/erp-admin/customers/<id>/settings` saves logo/branding fields.
6. Company Master → bank field label reads **Account Holder**.
