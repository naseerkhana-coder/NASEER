# VPS deploy — department portals (Plant, Asphalt, Concrete, Precast, Admin)

Upload these files to `/var/www/maxek-erp-flask/` then restart the app service.

| # | Local file | VPS path |
|---|------------|----------|
| 1 | `ui_shell_config.py` | `/var/www/maxek-erp-flask/ui_shell_config.py` |
| 2 | `app.py` | `/var/www/maxek-erp-flask/app.py` |
| 3 | `user_permission_service.py` | `/var/www/maxek-erp-flask/user_permission_service.py` |

No template or static changes required — dashboard tiles use existing `templates/dashboard.html`.

After upload:

```bash
sudo systemctl restart maxek-erp-flask
# or your gunicorn/uwsgi service name
```

Verify at `/dashboard` — department tile grid should include Plant, Asphalt Plant, Concrete Plant, Precast Yard, and Office Administration. Each opens `/dept/<slug>` with links to existing plant routes.
