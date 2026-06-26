# MAXEK ERP — Full WinSCP Deploy (corrected)

| Setting | Value |
|--------|--------|
| **PC folder** | `C:\Users\rajee\Documents\New project\MAXEK_ERP\` |
| **VPS folder** | `/var/www/maxek-erp-flask/` |
| **Service** | `maxek-erp` |

---

## Option A — WinSCP (recommended)

1. Run `deploy\clean_project.bat` on PC.
2. WinSCP → SFTP → `/var/www/maxek-erp-flask/`
3. Upload everything in **`deploy/WINSCP-FULL-FILE-LIST.txt`** (keep same subfolders).
4. **Fast drag:** upload root `app.py`, `workflow_service.py`, `cost_planning_service.py`, `payroll_service.py`, `wsgi.py`, `requirements.txt`, then whole folders `templates\`, `static\css\`, `static\js\`, `static\images\`.

### Never overwrite on VPS

| Path | Reason |
|------|--------|
| `database/maxek.db` | Production data |
| `.env` | Secrets |
| `.venv/` or `venv/` | Server Python |
| `static/uploads/**` | User files |
| `static/photos/**` | Server media |
| `backups/` | Server backups |

---

## Option B — Zip then upload

On PC (PowerShell):

```powershell
cd "C:\Users\rajee\Documents\New project\MAXEK_ERP"
python deploy\build_deploy_package.py
```

Zip appears in `deploy\dist\maxek-erp-deploy-<hash>.zip`. Upload zip to VPS, unzip into `/var/www/maxek-erp-flask/` (do not overwrite `database/maxek.db` or `.env`).

---

## Post-deploy (SSH / PuTTY)

```bash
cd /var/www/maxek-erp-flask
source .venv/bin/activate
export MAXEK_SKIP_DEMO_SEED=1
python -c "from app import app, init_db; app.app_context().push(); init_db(); print('OK')"

sudo mkdir -p static/uploads/petty_cash static/uploads/securities static/uploads/dpr static/uploads/staff
sudo chown -R www-data:www-data /var/www/maxek-erp-flask
sudo chmod -R u+rwX /var/www/maxek-erp-flask/database

sudo systemctl restart maxek-erp
sudo systemctl status maxek-erp --no-pager
```

Browser: **Ctrl+F5** hard refresh.

---

## Verify

| Module | Menu path |
|--------|-----------|
| Petty Cash | Accounts → Petty Cash |
| Securities | Accounts → Securities & Guarantees |
| Cost Planning | Projects → Cost Planning |
| BOQ | Projects → BOQ |
| Dashboard layout | Home dashboard |

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/login
sudo journalctl -u maxek-erp -n 20 --no-pager | grep -E "Error|Traceback"
```

---

## Critical files (do not miss)

| File | Why |
|------|-----|
| `cost_planning_service.py` | Cost Planning import fails without it |
| `wsgi.py` | Gunicorn + `init_db()` on startup |
| `static/js/maxek-ui.js` | Sub-bar / toolbar fixes |
| `static/js/petty-cash-form.js` | Petty Cash FRS UI |
| `static/js/cost-planning.js` | Cost Planning UI |
| `static/js/securities-guarantees.js` | Securities UI |

Full path list: **`deploy/WINSCP-FULL-FILE-LIST.txt`**
