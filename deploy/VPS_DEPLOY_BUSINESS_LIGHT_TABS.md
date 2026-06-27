# VPS deploy — Business Light theme tab contrast & softer canvas

**VPS app root:** `/var/www/maxek-erp-flask/`  
**After upload:** `sudo systemctl restart maxek-erp`

| # | Local path | VPS remote path |
|---|------------|-----------------|
| 1 | `templates/base_maxek.html` | `/var/www/maxek-erp-flask/templates/base_maxek.html` |
| 2 | `static/css/maxek-pro-dashboard.css` | `/var/www/maxek-erp-flask/static/css/maxek-pro-dashboard.css` |
| 3 | `static/css/maxek-field-standards.css` | `/var/www/maxek-erp-flask/static/css/maxek-field-standards.css` |

**Verify:** Hard-refresh `/dashboard` with **Business** theme active.

- Main dashboard background is soft gray (`#f1f5f9`), KPI/tile cards stay white with subtle border.
- Module **erp-tab** bars: dark text `#1e293b`, active tab teal border (no red).
- Department **sub-nav** links: readable on light pill, teal active state.
- Secondary **erp-sub-toolbar** links: teal accent, no MAXEK red bleed.

**Cache buster:** `?v=20260628-business-tabs` on pro-dashboard + field-standards CSS in `base_maxek.html`.
