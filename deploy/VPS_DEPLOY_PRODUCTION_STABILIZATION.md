# VPS deploy — Production stabilization (Phases 1–3)

**App path:** `/var/www/maxek-erp-flask/`

## What this patch includes

- Standard CRUD toolbar (`mode='standard'`) across ERP modules
- Customer/company management fixes (cascade delete, settings, bank labels)
- Generic `maxek-ui.js` toolbar wiring (New/View/Edit/Delete super-admin only/Export/Print/Refresh)
- Rebuilt `deploy/dist/vps-patch-latest.zip`

## Option A — Upload zip (recommended)

From your dev PC:

```powershell
cd "C:\Users\rajee\Documents\New project\MAXEK_ERP"
python deploy/build_vps_patch_latest.py
scp deploy/dist/vps-patch-latest.zip root@72.61.224.204:/tmp/
```

On VPS:

```bash
cd /var/www/maxek-erp-flask
sudo systemctl stop maxek-erp-flask
unzip -o /tmp/vps-patch-latest.zip -d /var/www/maxek-erp-flask
sudo systemctl start maxek-erp-flask
sudo systemctl status maxek-erp-flask --no-pager
```

## Option B — Quick sync (selected files)

```bash
scp super_admin_service.py erp_admin_routes.py app.py root@72.61.224.204:/var/www/maxek-erp-flask/
scp templates/macros/erp_ui.html root@72.61.224.204:/var/www/maxek-erp-flask/templates/macros/
scp templates/erp_admin/*.html root@72.61.224.204:/var/www/maxek-erp-flask/templates/erp_admin/
scp templates/*.html root@72.61.224.204:/var/www/maxek-erp-flask/templates/
scp static/js/maxek-ui.js root@72.61.224.204:/var/www/maxek-erp-flask/static/js/
scp static/css/maxek-dashboard.css root@72.61.224.204:/var/www/maxek-erp-flask/static/css/
ssh root@72.61.224.204 "systemctl restart maxek-erp-flask"
```

## Verify no 500/502 after restart

On VPS:

```bash
# Service must be active
systemctl is-active maxek-erp-flask

# App import smoke test
cd /var/www/maxek-erp-flask
./venv/bin/python -c "import wsgi; print('wsgi OK')"

# HTTP smoke (replace host if needed)
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5000/login
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5000/erp-admin/customers
```

Expected: service `active`, wsgi prints `wsgi OK`, curl returns `200` (or `302` redirect to login when unauthenticated — not `500`/`502`).

If 502 persists:

```bash
journalctl -u maxek-erp-flask -n 80 --no-pager
tail -n 50 /var/log/nginx/error.log
```

## Browser smoke (Super Admin)

See Phase 4 checklist in stabilization report / agent output.
