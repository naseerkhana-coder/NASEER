# VPS deploy — Dashboard CSS refresh (UI only)

**Branch:** `release/v1.1`  
**Scope:** Visual refresh of the ERP home dashboard only. No backend, database, JavaScript, or spreadsheet grid changes.

## Files in this patch

| File | Purpose |
|------|---------|
| `static/css/maxek-dashboard-home-refresh.css` | Dashboard-only styles (scoped to `.dashboard-mode`) |
| `templates/base_maxek.html` | Loads refresh CSS when pro shell is active |

## 1. Backup (VPS)

```bash
cd /var/www/maxek-erp-flask
sudo mkdir -p /var/backups/maxek-erp
sudo cp -a static/css/maxek-dashboard-home-refresh.css "/var/backups/maxek-erp/" 2>/dev/null || true
sudo cp -a templates/base_maxek.html "/var/backups/maxek-erp/base_maxek.html.$(date +%Y%m%d_%H%M%S)"
```

Do **not** overwrite `.env` or `database/*.db`.

## 2. Build zip (Windows dev machine)

```powershell
cd "C:\Users\rajee\Documents\New project\MAXEK_ERP"
python deploy/build_vps_patch_dashboard_css_refresh.py
```

## 3. Upload and apply

```powershell
scp "deploy/vps-patch-dashboard-css-refresh.zip" root@72.61.224.204:/tmp/
```

On VPS:

```bash
cd /var/www/maxek-erp-flask
sudo unzip -o /tmp/vps-patch-dashboard-css-refresh.zip -d /tmp/dashboard-css-patch
sudo rsync -av /tmp/dashboard-css-patch/static/css/maxek-dashboard-home-refresh.css static/css/
sudo rsync -av /tmp/dashboard-css-patch/templates/base_maxek.html templates/
sudo chown -R www-data:www-data static/css/maxek-dashboard-home-refresh.css templates/base_maxek.html
sudo systemctl restart maxek-erp
sudo systemctl status maxek-erp --no-pager
```

## 4. Verify

- [ ] Open `/dashboard` — greeting, date chip, and department tiles look updated.
- [ ] Hard refresh (Ctrl+Shift+R) to bypass browser cache.
- [ ] Open any module (e.g. BOQ) — layout unchanged; no new grid behaviour.
- [ ] Browser console — no JavaScript errors.

## 5. Rollback

```bash
cd /var/www/maxek-erp-flask
sudo cp -a /var/backups/maxek-erp/base_maxek.html.* templates/base_maxek.html
sudo rm -f static/css/maxek-dashboard-home-refresh.css
sudo systemctl restart maxek-erp
```

## Spreadsheet grid (not in this patch)

Spreadsheet grid work lives on branch `feature/spreadsheet-grid`. Complete `deploy/SPREADSHEET_GRID_UAT_CHECKLIST.md` before merging that branch to production.
