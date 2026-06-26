# Deploy MAXEK ERP from ZIP (manual VPS upload)

Use this when you cannot `git pull` on the VPS. Build the zip on your PC with `python deploy/build_staging_deploy_zip.py` — see `deploy/PACKAGE_BUILD_INFO.txt` inside the zip for the exact git commit (includes Office Administration sidebar + fleet nav hardening via `safe_url_for` in `app.py` / `templates/base_maxek.html`).

**VPS:** `srv1704727` / `72.61.224.204`  
**App path:** `/var/www/maxek-erp-flask/`

Recommended zip for this release: `deploy/MAXEK_ERP_staging_deploy_20260620.zip` (upload to `/tmp/` on the VPS).

## Quick deploy (automated script)

After the zip is in `/tmp/`, run on the VPS as **root**:

```bash
# Copy script from your PC if the uploaded zip does not include it yet:
# scp deploy/vps_install_from_zip.sh root@72.61.224.204:/tmp/

chmod +x /tmp/vps_install_from_zip.sh   # if copied to /tmp

# Explicit zip path (e.g. build output deploy/tmp/maxek-erp-deploy-*.zip uploaded to /tmp/)
sudo bash /tmp/vps_install_from_zip.sh /tmp/maxek-erp-deploy-20260623.zip

# Or staging zip by name:
sudo bash /tmp/vps_install_from_zip.sh /tmp/MAXEK_ERP_staging_deploy_20260620.zip

# Auto-detect newest /tmp/MAXEK_ERP_staging_deploy_*.zip (no argument):
sudo bash /tmp/vps_install_from_zip.sh

# Or, after one successful sync:
sudo bash /var/www/maxek-erp-flask/deploy/vps_install_from_zip.sh
sudo bash /var/www/maxek-erp-flask/deploy/vps_install_from_zip.sh /tmp/maxek-erp-deploy-20260623.zip
```

From Windows, upload a local build zip then pass its VPS path:

```powershell
scp "C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\tmp\maxek-erp-deploy-20260623.zip" root@72.61.224.204:/tmp/
# On VPS:
sudo bash /var/www/maxek-erp-flask/deploy/vps_install_from_zip.sh /tmp/maxek-erp-deploy-20260623.zip
```

The script backs up `database/maxek.db` to `database/maxek.db.bak.TIMESTAMP`, syncs code into `/var/www/maxek-erp-flask` (never overwrites `.env`, `database/*.db`, or `venv/`), runs `deploy/migrate_production.py` with `MAXEK_SKIP_DEMO_SEED=1`, and restarts `maxek-erp`.
## 1. Transfer the ZIP from Windows

Recommended file: `deploy/MAXEK_ERP_staging_deploy_YYYYMMDD.zip`

### WinSCP (easiest on Windows)

1. Download [WinSCP](https://winscp.net/).
2. New session: **Host** `72.61.224.204`, **User** your SSH user (often `root`), **Password** or private key.
3. Upload the zip to `/tmp/` on the server (drag and drop).

### FileZilla (SFTP)

1. Protocol: **SFTP**, host `72.61.224.204`, port `22`.
2. Upload zip to `/tmp/`.

### scp (PowerShell / OpenSSH)

```powershell
scp "C:\Users\rajee\Documents\New project\MAXEK_ERP\deploy\MAXEK_ERP_staging_deploy_YYYYMMDD.zip" root@72.61.224.204:/tmp/
```

## 2. On the VPS — backup before changing code

```bash
cd /var/www/maxek-erp-flask
sudo mkdir -p /var/backups/maxek-erp
sudo cp -a database/maxek.db "/var/backups/maxek-erp/maxek.db.$(date +%Y%m%d_%H%M%S)"
# If you use a payroll DB file locally on VPS, back it up too:
[ -f database/maxek_payroll.db ] && sudo cp -a database/maxek_payroll.db "/var/backups/maxek-erp/maxek_payroll.db.$(date +%Y%m%d_%H%M%S)"
```

**Do not overwrite** production `database/maxek.db` or `.env` when unpacking.

## 3. Unpack into the app directory

```bash
cd /var/www/maxek-erp-flask
sudo unzip -o /tmp/MAXEK_ERP_staging_deploy_YYYYMMDD.zip -d /tmp/maxek-staging-unpack
# Sync code only; keep existing DB and .env
sudo rsync -av --delete \
  --exclude 'database/*.db' \
  --exclude 'database/*.db-*' \
  --exclude '.env' \
  --exclude '.env.*' \
  --exclude 'static/uploads/' \
  --exclude 'static/photos/' \
  /tmp/maxek-staging-unpack/ /var/www/maxek-erp-flask/
sudo chown -R www-data:www-data /var/www/maxek-erp-flask
```

If `rsync` is not installed: `sudo apt-get install -y rsync`

Alternative without rsync: unzip directly over the tree, then **restore** your backed-up `database/maxek.db` and `.env` if they were touched.

## 4. Python dependencies (if requirements changed)

```bash
cd /var/www/maxek-erp-flask
source venv/bin/activate   # or your venv path
pip install -r requirements.txt
```

## 5. Run production migration

```bash
cd /var/www/maxek-erp-flask
source venv/bin/activate
export MAXEK_SKIP_DEMO_SEED=1
python deploy/migrate_production.py
```

Review script output for errors before restarting the app.

## 6. Restart the application

```bash
sudo systemctl restart maxek-erp
sudo systemctl status maxek-erp --no-pager
```

If you use gunicorn directly instead of systemd, restart that service the same way you normally do on this host.

## 7. Quick smoke check

- Log in to the ERP in the browser.
- Confirm **Office Administration** and **Fleet & Vehicles** appear in the sidebar (Office Dashboard, Letter In/Out, Fleet Dashboard, etc.).
- Confirm other modules load: material transfer, subcontract payments ledger, BOQ bulk entry.
- Run: `cd /var/www/maxek-erp-flask && bash deploy/check-office-fleet-deploy.sh`
- Optional: `bash deploy/post_deploy_test.sh` if configured on the VPS.

## What this ZIP contains / omits

| Included | Excluded |
|----------|----------|
| Python app + `*_service.py`, `templates/`, `static/` (css/js) | `database/*.db` (SQLite data) |
| `deploy/` scripts and docs | `.env`, secrets |
| `requirements.txt`, `tests/` | `venv/`, `__pycache__/`, `.git/` |
| Empty placeholders for `database/`, `static/uploads/`, `static/photos/` | User uploads under `static/uploads/` and `static/photos/` |

## Rollback

```bash
sudo cp -a /var/backups/maxek-erp/maxek.db.TIMESTAMP database/maxek.db
sudo systemctl restart maxek-erp
```

Replace `TIMESTAMP` with your backup filename.
