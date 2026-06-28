# VPS deploy — Super Admin dashboard navigation fix

**VPS app root:** `/var/www/maxek-erp-flask/`  
**After upload:** `sudo systemctl restart maxek-erp`

| # | Local path | VPS remote path |
|---|------------|-----------------|
| 1 | `app.py` | `/var/www/maxek-erp-flask/app.py` |
| 2 | `templates/partials/dashboard_shell_sidebar.html` | `/var/www/maxek-erp-flask/templates/partials/dashboard_shell_sidebar.html` |
| 3 | `templates/partials/dashboard_shell_module_header.html` | `/var/www/maxek-erp-flask/templates/partials/dashboard_shell_module_header.html` |
| 4 | `templates/erp_admin/platform_dashboard.html` | `/var/www/maxek-erp-flask/templates/erp_admin/platform_dashboard.html` |
| 5 | `static/css/maxek-dashboard.css` | `/var/www/maxek-erp-flask/static/css/maxek-dashboard.css` |

**Verify (super admin account):**

1. Log in — lands on `/super-admin/dashboard` (Platform Command Centre) as before.
2. Sidebar **Dashboard** → opens `/dashboard` (main ERP command centre), not redirected back to platform.
3. Logo / brand click → `/dashboard`.
4. Platform page **Main Dashboard** button and module **Back** → `/dashboard`.
5. Sidebar **Platform → Platform Command Centre** → `/super-admin/dashboard` still works.

**Cache buster:** hard-refresh or append `?v=20260628-superadmin-dash-nav` on CSS if styles look stale.
