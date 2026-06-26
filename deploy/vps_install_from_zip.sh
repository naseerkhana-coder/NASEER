#!/usr/bin/env bash
# MAXEK ERP — Install/update from staging ZIP on VPS (run as root)
# Usage: sudo bash deploy/vps_install_from_zip.sh [ZIP_PATH]
#    ZIP_PATH: optional path to deploy zip (e.g. /tmp/maxek-erp-deploy-20260623.zip)
#    If omitted, uses newest /tmp/MAXEK_ERP_staging_deploy_*.zip
#    or: sudo bash /tmp/vps_install_from_zip.sh [ZIP_PATH]
set -euo pipefail

APP_DIR="/var/www/maxek-erp-flask"
EXTRACT_DIR="/tmp/maxek-deploy-extract"
SERVICE_NAME="maxek-erp"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run as root: sudo bash $0"
  exit 1
fi

if [[ ! -d "$APP_DIR" ]]; then
  echo "ERROR: App directory missing: $APP_DIR"
  exit 1
fi

pick_zip() {
  local arg="${1:-}"
  if [[ -n "$arg" && -f "$arg" ]]; then
    echo "$arg"
    return
  fi
  local latest
  latest="$(ls -1t /tmp/MAXEK_ERP_staging_deploy_*.zip 2>/dev/null | head -1 || true)"
  if [[ -n "$latest" && -f "$latest" ]]; then
    echo "$latest"
    return
  fi
  echo ""
}

ZIP_PATH="$(pick_zip "${1:-}")"
if [[ -z "$ZIP_PATH" ]]; then
  echo "ERROR: No deploy zip found."
  echo "  Option 1: pass zip path as first argument"
  echo "    sudo bash $0 /path/to/deploy.zip"
  echo "  Option 2: upload to /tmp/ and use newest matching:"
  echo "    /tmp/MAXEK_ERP_staging_deploy_*.zip"
  exit 1
fi

echo "=== MAXEK ERP zip deploy ==="
echo "App dir:  $APP_DIR"
echo "Zip:      $ZIP_PATH"
echo "Extract:  $EXTRACT_DIR"
echo ""

STAMP="$(date +%Y%m%d_%H%M%S)"
cd "$APP_DIR"

if [[ -f database/maxek.db ]]; then
  echo "[1/6] Backup database/maxek.db -> database/maxek.db.bak.${STAMP}"
  cp -a database/maxek.db "database/maxek.db.bak.${STAMP}"
else
  echo "[1/6] No database/maxek.db yet (skip in-app backup)"
fi

if [[ -f database/maxek_payroll.db ]]; then
  cp -a database/maxek_payroll.db "database/maxek_payroll.db.bak.${STAMP}" || true
fi

echo "[2/6] Unpack zip to $EXTRACT_DIR"
rm -rf "$EXTRACT_DIR"
mkdir -p "$EXTRACT_DIR"
unzip -q -o "$ZIP_PATH" -d "$EXTRACT_DIR"

SRC="$EXTRACT_DIR"
if [[ -d "$EXTRACT_DIR/MAXEK_ERP" ]]; then
  SRC="$EXTRACT_DIR/MAXEK_ERP"
elif [[ -d "$EXTRACT_DIR/maxek-erp-flask" ]]; then
  SRC="$EXTRACT_DIR/maxek-erp-flask"
fi

if [[ ! -f "$SRC/app.py" ]]; then
  echo "ERROR: app.py not found under $SRC — check zip layout"
  exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
  apt-get update -qq && apt-get install -y rsync
fi

echo "[3/6] Sync code into $APP_DIR (keep .env, *.db, venv/)"
rsync -a --delete \
  --exclude '.env' \
  --exclude '.env.*' \
  --exclude 'database/*.db' \
  --exclude 'database/*.db-*' \
  --exclude 'venv/' \
  --exclude '.venv/' \
  --exclude 'static/uploads/' \
  --exclude 'static/photos/' \
  --exclude 'backups/' \
  --exclude '__pycache__/' \
  "$SRC/" "$APP_DIR/"

chown -R www-data:www-data "$APP_DIR" || true

echo "[4/6] Python venv + migrate_production.py"
cd "$APP_DIR"
if [[ -f venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
elif [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
else
  echo "ERROR: No venv/ or .venv/ in $APP_DIR"
  exit 1
fi

pip install -q -r requirements.txt

export MAXEK_SKIP_DEMO_SEED=1
python3 deploy/migrate_production.py

echo "[5/6] Restart $SERVICE_NAME"
if systemctl list-unit-files | grep -q "^${SERVICE_NAME}.service"; then
  systemctl restart "$SERVICE_NAME"
  systemctl status "$SERVICE_NAME" --no-pager || true
else
  echo "WARN: ${SERVICE_NAME}.service not found — restart gunicorn manually"
fi

echo "[6/6] Verification (HTTP status codes; 200 or 302 expected for protected routes)"
PUBLIC_BASE="${MAXEK_PUBLIC_URL:-http://127.0.0.1}"
echo ""
echo "Local checks:"
for path in /login /material-transfer /subcontract-payments /boq-multiple-entry /dashboard; do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "${PUBLIC_BASE}${path}" || echo 000)"
  echo "  curl -s -o /dev/null -w '%{http_code}' ${PUBLIC_BASE}${path}  # -> ${code}"
done

if [[ -f deploy/post_deploy_test.sh ]]; then
  echo ""
  echo "Optional: bash deploy/post_deploy_test.sh"
fi

echo ""
echo "=== Done. .env and database/*.db were NOT overwritten. ==="
echo "Backup DB (if any): database/maxek.db.bak.${STAMP}"