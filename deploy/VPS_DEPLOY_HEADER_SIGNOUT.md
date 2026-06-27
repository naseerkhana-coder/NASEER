# VPS deploy — Header Sign out button

**VPS app root:** `/var/www/maxek-erp-flask/`  
**After upload:** `sudo systemctl restart maxek-erp`

| # | Local path | VPS remote path |
|---|------------|-----------------|
| 1 | `templates/partials/dashboard_shell_header.html` | `/var/www/maxek-erp-flask/templates/partials/dashboard_shell_header.html` |
| 2 | `templates/partials/dashboard_shell_module_header.html` | `/var/www/maxek-erp-flask/templates/partials/dashboard_shell_module_header.html` |
| 3 | `static/css/maxek-pro-dashboard.css` | `/var/www/maxek-erp-flask/static/css/maxek-pro-dashboard.css` |

**Verify:** Hard-refresh `/dashboard` and any module page (e.g. `/employees`). Top-right header shows **Sign out** next to the user profile on both main dashboard and module pages. Works on Business (light), Midnight, and ERP Classic themes. Sidebar has no sign-out link.
