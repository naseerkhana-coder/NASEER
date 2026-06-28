# MAXEK ERP Dashboard Themes

Per-tenant dashboard **layout** themes (distinct from UI colour themes `command-dark`, `pro-light`, `ultra-color`).

## Theme options

| ID | Name | Status | Template |
|----|------|--------|----------|
| `executive` | Theme A — Executive Dashboard | Active | `dashboard_theme_executive.html` |
| `command-centre` | Theme B — Construction Command Centre | **Default** | `dashboard.html` |
| `compact` | Theme C — Compact Dashboard | Active | `dashboard_theme_compact.html` |
| `kpi` | Theme D — KPI Dashboard | Placeholder → falls back to B | — |
| `custom` | Theme E — Custom Dashboard | Placeholder → falls back to B | — |

Placeholder themes show an info notice and render Theme B until implemented.

## Resolution order

1. **User override** — `user_dashboard_preferences.dashboard_layout_theme` (Settings → My Dashboard Preferences). Empty = use company default.
2. **Company default** — `erp_customers.dashboard_theme` (ERP Admin → Customer Settings, or tenant branding in Settings).
3. **System default** — `command-centre`.

Implemented in `dashboard_prefs_service.resolve_dashboard_theme()`. `render_choice_b_dashboard()` in `app.py` selects the template from `DASHBOARD_THEME_TEMPLATES`.

## Data reuse

All themes share `_build_dashboard_shared_context()` — same queries as Command Centre (`get_dashboard_stats`, `get_command_centre_cards`, `get_approval_summary`, `accounts_hub_stats`, etc.). Only Jinja layout differs.

## CSS

Layout-specific rules use `[data-dashboard-theme="…"]` on the dashboard content wrapper. Colour tokens remain on `<html data-theme="…">`.

## Theme E — Custom Dashboard (future)

Planned widget toggles per user/tenant (not yet wired):

- Company summary block
- Pending approvals panel
- Project summary panel
- Financial summary (high-level)
- Department tile grid
- Quick actions row
- KPI strip (Theme D overlap)

Store toggles in `user_dashboard_preferences` JSON or a dedicated `dashboard_widgets` column when Theme E ships.

## Deploy / migration

On first request after deploy, `ensure_super_admin_schema()` adds `erp_customers.dashboard_theme` (default `command-centre`). `ensure_user_context_schema()` adds `user_dashboard_preferences.dashboard_layout_theme`. No manual migration script required for SQLite.
