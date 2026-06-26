# Deploy checklist — pending modules (Phase B–D)

Upload via WinSCP to `/var/www/maxek-erp-flask/` using paths in `WINSCP-FULL-FILE-LIST.txt`.

**Never upload:** `database/maxek.db`, `.env`, `.venv/`, `static/uploads/**`, `static/photos/**`

## Files in this release

| Module | Service | Templates |
|--------|---------|-----------|
| Company Master | `company_master_service.py` | `company_master.html` |
| Client Billing | `client_billing_service.py` | `client_billing_*.html` |
| Project Photos | `project_photos_service.py` | `project_photos_*.html` (4) |
| Employee Timesheet | `employee_timesheet_service.py` | `employee_timesheet*.html` |
| BBS | `bbs_service.py` | `bbs_*.html` |
| Subcontractor Billing | `subcontractor_billing_service.py` | `sub_billing_*.html` |
| Corporate DMS (Phase D) | `corporate_dms_service.py` | `corporate_dms_register.html` |

Also upload: `app.py`, `deploy/migrate_production.py`, `deploy/nginx-maxek-erp.conf`

## VPS commands (SSH)

```bash
cd /var/www/maxek-erp-flask

# Create upload directory for Corporate DMS (if missing)
mkdir -p static/uploads/corporate_dms
chown -R www-data:www-data static/uploads/corporate_dms

# Run migration (no demo seed)
export MAXEK_SKIP_DEMO_SEED=1
python deploy/migrate_production.py

# Update nginx static path if still on old folder name
sudo cp deploy/nginx-maxek-erp.conf /etc/nginx/sites-available/maxek-erp
sudo nginx -t && sudo systemctl reload nginx

# Restart Gunicorn
sudo systemctl restart maxek-erp   # or your service name
```

## Verify

- Settings → Corporate DMS (`/settings/corporate-dms`)
- Settings → Company Master (expiry notifications)
- Projects → Client Billing, Project Photos
- Workforce → Employee Timesheets (if linked in nav)
- Subcontract → Sub-contractor Billing

## Nginx note

`deploy/nginx-maxek-erp.conf` uses:
- `client_max_body_size 32M`
- Static alias: `/var/www/maxek-erp-flask/static/`
