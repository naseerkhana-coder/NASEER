# Deploy MAXEK ERP to VPS (WinSCP / ZIP)

**Local project:** `C:\Users\rajee\Documents\New project\MAXEK_ERP`  
**Deployment package:** `deploy\maxek-erp-deploy.zip`  
**VPS host:** `root@srv1704727` (Hostinger)  
**Remote app root:** `/var/www/maxek-erp-flask`  
**Service:** `sudo systemctl restart maxek-erp`

Do **not** upload or overwrite: `database/maxek.db`, `.env`, `venv/`, `backups/`, `static/uploads/*`.

---

## Option A — WinSCP (upload files directly)

1. Install [WinSCP](https://winscp.net/) if needed.
2. **New site:** Protocol SFTP, host `srv1704727` (or IP from Hostinger), user `root`, your SSH password or key.
3. **Local pane:** `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\_staging_maxek-erp-deploy`  
   *(Or extract `maxek-erp-deploy.zip` locally first.)*
4. **Remote pane:** `/var/www/maxek-erp-flask`
5. Drag and drop so paths match:
   - `app.py` → `/var/www/maxek-erp-flask/app.py`
   - `templates\` → `/var/www/maxek-erp-flask/templates/`
   - `static\` → `/var/www/maxek-erp-flask/static/`
   - `workflow_service.py`, `wsgi.py`, `requirements.txt` → app root
   - `deploy\` scripts → `/var/www/maxek-erp-flask/deploy/`
6. When WinSCP asks to overwrite, choose **Yes** (or **Yes to all**).
7. SSH (WinSCP → Commands → Open in PuTTY, or separate terminal):

```bash
cd /var/www/maxek-erp-flask
bash deploy/vps_backup.sh /var/www/maxek-erp-flask
source venv/bin/activate
export MAXEK_SKIP_DEMO_SEED=1
python deploy/migrate_production.py
sudo chown -R www-data:www-data database static/uploads
sudo systemctl restart maxek-erp
sudo systemctl status maxek-erp --no-pager
```

---

## Option B — Upload ZIP, unzip on server

1. WinSCP: upload  
   **Local:** `C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\maxek-erp-deploy.zip`  
   **Remote:** `/var/www/maxek-erp-flask/deploy/maxek-erp-deploy.zip`
2. SSH:

```bash
cd /var/www/maxek-erp-flask
unzip -o deploy/maxek-erp-deploy.zip -d /var/www/maxek-erp-flask
bash deploy/vps_backup.sh /var/www/maxek-erp-flask
source venv/bin/activate
export MAXEK_SKIP_DEMO_SEED=1
python deploy/migrate_production.py
sudo systemctl restart maxek-erp
```

---

## Verification (SSH)

```bash
cd /var/www/maxek-erp-flask
grep -n "staff_bonus\|staff-forms\|Staff Bonus" app.py templates/staff.html templates/staff_bonus.html 2>/dev/null | head
test -f static/js/staff-forms.js && test -f static/js/staff-bonus.js && echo "HR JS OK"
test -f templates/staff_bonus.html && echo "staff_bonus template OK"
sudo systemctl is-active maxek-erp
curl -sI http://127.0.0.1:5000/login | head -3
```

Full file list for this package: `deploy\maxek-erp-deploy-MANIFEST.txt`

---

## This package includes (HR / recent work)

- `app.py`, `workflow_service.py`, `wsgi.py`
- Templates: `staff.html`, `staff_bonus.html`, `settings.html`, `dashboard.html`, `notifications.html`, plus attendance, workers, DPR, BOQ, hub, etc.
- Static: `maxek-dashboard.css`, `staff-forms.js`, `staff-bonus.js`, `dpr-forms.js`, and related JS
- Deploy helpers: migrations, backup, WinSCP notes
