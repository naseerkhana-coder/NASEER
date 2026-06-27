# VPS deploy — Header Sign out overflow fix

**VPS app root:** `/var/www/maxek-erp-flask/`  
**After upload:** `sudo systemctl restart maxek-erp`

| # | Local path | VPS remote path |
|---|------------|-----------------|
| 1 | `static/css/maxek-pro-dashboard.css` | `/var/www/maxek-erp-flask/static/css/maxek-pro-dashboard.css` |
| 2 | `templates/base_maxek.html` | `/var/www/maxek-erp-flask/templates/base_maxek.html` |

**Verify:** Hard-refresh `/dashboard`, `/employees`, and Super Admin **Platform Command Centre**. **Sign out** stays visible top-right (icon-only below 900px width). Module pages no longer squeeze actions into the search column.

**Cache buster:** `?v=20260628-header-signout` on pro-dashboard CSS.
