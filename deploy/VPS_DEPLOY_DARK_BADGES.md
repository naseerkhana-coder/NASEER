# VPS deploy — dark badges + store teal + dashboard polish

**VPS app root:** `/var/www/maxek-erp-flask/`  
**After upload:** `sudo systemctl restart maxek-erp`

| # | Local path | VPS remote path |
|---|------------|-----------------|
| 1 | `app.py` | `/var/www/maxek-erp-flask/app.py` |
| 2 | `ui_shell_config.py` | `/var/www/maxek-erp-flask/ui_shell_config.py` |
| 3 | `templates/base_maxek.html` | `/var/www/maxek-erp-flask/templates/base_maxek.html` |
| 4 | `templates/dashboard.html` | `/var/www/maxek-erp-flask/templates/dashboard.html` |
| 5 | `templates/department_workspace.html` | `/var/www/maxek-erp-flask/templates/department_workspace.html` |
| 6 | `static/css/maxek-pro-dashboard.css` | `/var/www/maxek-erp-flask/static/css/maxek-pro-dashboard.css` |

**Verify:** Store department — Open/Run pills are dark (not cream/yellow); store accent is teal; main dashboard KPI row + department card grid.
