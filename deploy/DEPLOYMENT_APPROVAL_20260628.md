# MAXEK ERP — Deployment Approval & Execution Runbook

**Date:** 2026-06-28  
**Release roadmap:** [docs/MAXEK_ERP_RELEASE_PLAN.md](../docs/MAXEK_ERP_RELEASE_PLAN.md)

**Approved by:** User (manual deployment)  
**Repository:** `C:\Users\rajee\Documents\New project\MAXEK_ERP`  
**Git HEAD:** `2e10ed5a72ec334de41553d609049a273edda2a8` — feat: improve user permission assignment UI with department matrix  
**Patch artifact:** `deploy/dist/vps-patch-latest.zip`  
**Manifest:** `deploy/dist/VPS-PATCH-LATEST-MANIFEST.txt` — **211** production files, **816,458** bytes  
**Bundle commits:** `32788c9`, `a4ca636`, `2e10ed5` (Final Stabilization: toolbar + themes + permissions)

> **Agent note:** No automated VPS deploy. Operator runs commands below on Windows (upload) and Linux (VPS).

---

## Scope exclusion — bulk import

**Bulk import commit `410b68f5` is ABORTED and NOT in this repository.** It is **excluded** from `vps-patch-latest.zip` and must **not** be deployed or enabled on production until a separate approved bundle exists.

---

## Pre-deployment backup (VPS — run first)

Create backup directory and full application + database snapshot before touching live code.

```bash
sudo mkdir -p /var/backups/maxek-erp
STAMP=$(date +%Y%m%d_%H%M%S)
sudo tar -czf "/var/backups/maxek-erp/maxek-erp-flask_pre_${STAMP}.tar.gz" \
  -C /var/www maxek-erp-flask \
  --exclude='maxek-erp-flask/venv' \
  --exclude='maxek-erp-flask/__pycache__' \
  --exclude='maxek-erp-flask/**/__pycache__'
if [ -f /var/www/maxek-erp-flask/database/maxek.db ]; then
  sudo cp -a /var/www/maxek-erp-flask/database/maxek.db \
    "/var/backups/maxek-erp/maxek.db_pre_${STAMP}.bak"
fi
ls -lh /var/backups/maxek-erp/*${STAMP}*
```

Record backup filenames in the **Post-deployment log** below.

---

## Step 1 — Upload patch (Windows)

From PowerShell on the operator machine (adjust `USER` and `VPS_HOST`):

```powershell
cd "C:\Users\rajee\Documents\New project\MAXEK_ERP"
scp deploy\dist\vps-patch-latest.zip USER@VPS_HOST:/tmp/vps-patch-latest.zip
scp deploy\dist\VPS-PATCH-LATEST-MANIFEST.txt USER@VPS_HOST:/tmp/VPS-PATCH-LATEST-MANIFEST.txt
```

Optional integrity check on Windows before upload:

```powershell
(Get-FileHash "deploy\dist\vps-patch-latest.zip" -Algorithm SHA256).Hash
(Get-Item "deploy\dist\vps-patch-latest.zip").Length
# Expect length: 816458
```

---

## Step 2 — Deploy on VPS

Confirm service name (expected **`maxek-erp`**):

```bash
systemctl list-units 'maxek*' --all
```

Deploy sequence:

```bash
sudo systemctl stop maxek-erp
cd /var/www/maxek-erp-flask
sudo unzip -o /tmp/vps-patch-latest.zip -d /var/www/maxek-erp-flask
source venv/bin/activate
export MAXEK_SKIP_DEMO_SEED=1
python deploy/migrate_production.py
sudo chown -R www-data:www-data app.py templates static *.py
sudo systemctl start maxek-erp
sudo systemctl status maxek-erp --no-pager
```

Post-unzip smoke (still on VPS):

```bash
cd /var/www/maxek-erp-flask
source venv/bin/activate
python -c "import wsgi; print('wsgi OK')"
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5000/login || curl -s -o /dev/null -w "%{http_code}\n" https://erp.maxekindia.com/login
```

Adjust local curl URL/port to match your gunicorn/nginx setup.

---

## Production verification checklist

Complete immediately after service restart (smoke). Full browser UAT: `docs/PRODUCTION_UAT_CHECKLIST.md` (also inside patch at `docs/PRODUCTION_UAT_CHECKLIST.md` on VPS).

| # | Check | Pass | Notes |
|---|--------|:----:|-------|
| 1 | `systemctl is-active maxek-erp` → active | ☐ | |
| 2 | `python -c "import wsgi"` in venv → no error | ☐ | |
| 3 | `/login` returns HTTP 200 (public URL) | ☐ | https://erp.maxekindia.com |
| 4 | Valid login → dashboard loads | ☐ | |
| 5 | Customer Settings: dashboard theme selector works | ☐ | |
| 6 | My Dashboard Preferences override works | ☐ | |
| 7 | Settings → Users: permission matrix save persists | ☐ | |
| 8 | Sample modules show standard toolbar (e.g. Projects, Clients) | ☐ | |
| 9 | ERP Admin pages load without HTTP 500 | ☐ | |
| 10 | No unexpected demo seed / test data after migrate | ☐ | `MAXEK_SKIP_DEMO_SEED=1` was set |

**Stabilization-specific (this bundle):**

| # | Check | Pass | Notes |
|---|--------|:----:|-------|
| 11 | Command Centre / department launcher navigation | ☐ | |
| 12 | Per-tenant dashboard layout theme applies | ☐ | |
| 13 | Financial widgets on Accounts dept dashboard (not wrong hub) | ☐ | |
| 14 | Greeting uses app timezone (IST) | ☐ | |

**Explicitly out of scope for this deploy:**

- Bulk import features (`410b68f5`) — **not deployed**

---

## Rollback

If deploy fails or smoke checks fail, **stop service** and restore from `/var/backups/maxek-erp/` (full tar and/or DB `.bak` from pre-deploy step).

Detailed bundle context, file groups, and rollback summary: **`deploy/FINAL_STABILIZATION_BUNDLE_REPORT.md`**.

Quick rollback:

```bash
sudo systemctl stop maxek-erp
# Replace TIMESTAMP with your backup stamp
sudo tar -xzf /var/backups/maxek-erp/maxek-erp-flask_pre_TIMESTAMP.tar.gz -C /var/www
# If DB was corrupted: sudo cp /var/backups/maxek-erp/maxek.db_pre_TIMESTAMP.bak /var/www/maxek-erp-flask/database/maxek.db
sudo chown -R www-data:www-data /var/www/maxek-erp-flask
sudo systemctl start maxek-erp
```

---

## Post-deployment log template

Copy this section into your change record / ticket after execution.

### Deployment log

| Field | Value |
|-------|--------|
| Deploy date/time (IST) | |
| Operator | |
| VPS host | |
| Git HEAD deployed | `2e10ed5a72ec334de41553d609049a273edda2a8` |
| Zip file | `vps-patch-latest.zip` (211 files, 816458 bytes) |
| Pre-deploy backup path(s) | |
| Upload method | scp to `/tmp/` |

### Migration result

```
(paste full stdout/stderr from: MAXEK_SKIP_DEMO_SEED=1 python deploy/migrate_production.py)
```

| Item | Result |
|------|--------|
| Exit code | |
| Schema changes applied | |
| Errors / warnings | |

### Service status

```
(paste: systemctl status maxek-erp --no-pager)
```

| Check | Result |
|-------|--------|
| Active state | |
| Recent journal errors | `journalctl -u maxek-erp -n 50 --no-pager` |

### UAT results

| Area | Result | Tester | Date |
|------|--------|--------|------|
| Smoke checklist (above) | Pass / Fail | | |
| Full PRODUCTION_UAT_CHECKLIST | Pass / Fail / Partial | | |

Issues:

| ID | Module | Severity | Description | Status |
|----|--------|----------|-------------|--------|
| | | | | |

### Remaining issues

- Known backlog (toolbar): see **Modules without standard toolbar** in `FINAL_STABILIZATION_BUNDLE_REPORT.md`
- Bulk import: deferred (not in bundle)

### Production baseline sign-off

| Role | Name | Date | Approve deploy baseline |
|------|------|------|-------------------------|
| Technical lead | | | ☐ |
| Business / UAT lead | | | ☐ |

**Baseline tag:** HEAD `2e10ed5` — Final Stabilization patch `vps-patch-latest` — bulk import excluded.

---

## Rebuild patch locally (optional)

```powershell
cd "C:\Users\rajee\Documents\New project\MAXEK_ERP"
python deploy/build_vps_patch_latest.py
```

---

## Approval record

- [x] User approved deployment execution materials — 2026-06-28
- [ ] VPS backup completed
- [ ] Patch uploaded and applied
- [ ] Migration succeeded
- [ ] Service verified
- [ ] UAT smoke passed
- [ ] Production baseline signed off

