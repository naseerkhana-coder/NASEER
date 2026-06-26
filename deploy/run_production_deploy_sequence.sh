#!/usr/bin/env bash
# MAXEK ERP — Production deploy (master @ b897367+) — run ON VPS with sudo
# Usage: bash deploy/run_production_deploy_sequence.sh
set -euo pipefail

APP_DIR="/var/www/maxek-erp-flask"
TARGET_COMMIT_PREFIX="b897367"
DEPLOY_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REPORT_FILE="${APP_DIR}/backups/deploy_report_${DEPLOY_UTC//[:]/}.txt"

mkdir -p "${APP_DIR}/backups"
exec > >(tee -a "$REPORT_FILE") 2>&1

echo "=== MAXEK ERP production deploy started ${DEPLOY_UTC} UTC ==="
echo "App dir: ${APP_DIR}"

cd "$APP_DIR"

# --- 1. Full backup (keep until UAT approved) ---
echo ""
echo "[1/6] Full backup..."
BACKUP_DIR=""
if [[ -f deploy/vps_backup.sh ]]; then
  bash deploy/vps_backup.sh "$APP_DIR"
  BACKUP_DIR="$(ls -dt "${APP_DIR}/backups/backup_"* 2>/dev/null | head -1)"
elif [[ -f deploy/backup_vps.sh ]]; then
  APP_DIR="$APP_DIR" bash deploy/backup_vps.sh
  BACKUP_DIR="${APP_DIR}/backups"
else
  STAMP="$(date +%Y%m%d_%H%M%S)"
  BACKUP_DIR="${APP_DIR}/backups/manual_${STAMP}"
  mkdir -p "$BACKUP_DIR"
  tar -czf "${BACKUP_DIR}/app_pre_deploy.tar.gz" \
    --exclude='./venv' --exclude='./.venv' --exclude='./backups' \
    -C "$APP_DIR" .
  [[ -f database/maxek.db ]] && cp -a database/maxek.db "${BACKUP_DIR}/maxek.db"
  [[ -f .env ]] && cp -a .env "${BACKUP_DIR}/.env"
fi
[[ -f /etc/nginx/sites-enabled/maxek-erp ]] && sudo cp -a /etc/nginx/sites-enabled/maxek-erp "${BACKUP_DIR}/nginx-maxek-erp.conf" 2>/dev/null || true
[[ -f /etc/nginx/sites-available/maxek-erp ]] && sudo cp -a /etc/nginx/sites-available/maxek-erp "${BACKUP_DIR}/nginx-maxek-erp-sites-available.conf" 2>/dev/null || true
echo "Backup location(s): ${BACKUP_DIR}"
ls -la "${BACKUP_DIR}" || true

# --- 2. Update source ---
echo ""
echo "[2/6] Git update (master)..."
git fetch origin
git checkout master
git pull origin master
HEAD_SHA="$(git rev-parse HEAD)"
echo "HEAD: ${HEAD_SHA}"
if [[ "${HEAD_SHA}" != ${TARGET_COMMIT_PREFIX}* ]] && ! git merge-base --is-ancestor "${TARGET_COMMIT_PREFIX}" "${HEAD_SHA}" 2>/dev/null; then
  echo "WARN: HEAD may be older than ${TARGET_COMMIT_PREFIX}; verify manually."
fi

# --- 3. Sync application files ---
echo ""
echo "[3/6] Rsync MAXEK_ERP/ to app root..."
if [[ ! -d MAXEK_ERP ]]; then
  echo "ERROR: MAXEK_ERP/ subfolder missing after pull"
  exit 1
fi
rsync -a --delete \
  --exclude='database/*.db' \
  --exclude='venv/' --exclude='.venv/' \
  --exclude='.env' --exclude='backups/' \
  --exclude='__pycache__/' \
  MAXEK_ERP/ ./

# --- 4. Database migration ---
echo ""
echo "[4/6] migrate_production.py..."
if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
elif [[ -f venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
else
  echo "ERROR: no venv/.venv found"
  exit 1
fi
export MAXEK_SKIP_DEMO_SEED=1
python3 deploy/migrate_production.py

# --- 5. Service restart ---
echo ""
echo "[5/6] Restart services..."
sudo systemctl restart maxek-erp
sudo systemctl restart nginx
sudo systemctl status maxek-erp --no-pager || true
sudo chown -R www-data:www-data database static/uploads 2>/dev/null || true

# --- 6. Verification ---
echo ""
echo "[6/6] Verification..."
python3 -c "import app; print('import OK')"
sudo journalctl -u maxek-erp -n 50 --no-pager || true
BASE="http://127.0.0.1"
for path in / /login /dashboard /staff /boq-management /boq-multiple-entry /material-transfer /subcontract-payments /approvals /settings/workflow; do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "${BASE}${path}" || echo "000")
  echo "curl ${path} -> ${code}"
done
if [[ -f deploy/post_deploy_test.sh ]]; then
  bash deploy/post_deploy_test.sh || true
fi

echo ""
echo "=== Deploy finished ${DEPLOY_UTC} UTC ==="
echo "Commit: ${HEAD_SHA}"
echo "Report: ${REPORT_FILE}"
