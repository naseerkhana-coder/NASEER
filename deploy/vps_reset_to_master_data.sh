#!/bin/bash
# MAXEK ERP — Reset production DB to master/lookup data (keeps superadmin + admin).
#
# ⚠️  DESTRUCTIVE. Always backup first.
#
# Usage on VPS:
#   cd /var/www/maxek-erp-flask
#   bash deploy/vps_backup.sh /var/www/maxek-erp-flask
#   bash deploy/vps_reset_to_master_data.sh --dry-run
#   bash deploy/vps_reset_to_master_data.sh --confirm RESET --new-admin-password 'YourPass!'
#
set -euo pipefail

APP_DIR="${MAXEK_APP_DIR:-/var/www/maxek-erp-flask}"
DB_PATH="${MAXEK_DB_PATH:-${APP_DIR}/database/maxek.db}"
SERVICE_NAME="${MAXEK_SERVICE:-maxek-erp}"
VENV_PYTHON="${APP_DIR}/venv/bin/python"

if [[ ! -d "$APP_DIR" ]]; then
  echo "ERROR: App directory not found: $APP_DIR"
  exit 1
fi

if [[ ! -f "$DB_PATH" ]]; then
  echo "ERROR: Database not found: $DB_PATH"
  exit 1
fi

if [[ ! -x "$VENV_PYTHON" ]]; then
  VENV_PYTHON="python3"
fi

cd "$APP_DIR"

echo "=============================================="
echo " MAXEK ERP — Reset to master data"
echo " App:  $APP_DIR"
echo " DB:   $DB_PATH"
echo "=============================================="
echo ""
echo "⚠️  Ensure you have a recent backup:"
echo "    bash deploy/vps_backup.sh $APP_DIR"
echo ""

DRY=0
CONFIRM=""
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY=1
      EXTRA_ARGS+=("--dry-run")
      shift
      ;;
    --confirm)
      CONFIRM="${2:-}"
      EXTRA_ARGS+=("--confirm" "$CONFIRM")
      shift 2
      ;;
    --new-admin-password)
      EXTRA_ARGS+=("--new-admin-password" "${2:-}")
      shift 2
      ;;
    --no-reseed)
      EXTRA_ARGS+=("--no-reseed")
      shift
      ;;
    *)
      echo "Unknown argument: $1"
      exit 1
      ;;
  esac
done

if [[ "$DRY" -eq 0 && "$CONFIRM" != "RESET" ]]; then
  echo "Preview only (dry run). To execute:"
  echo "  bash deploy/vps_reset_to_master_data.sh --confirm RESET --new-admin-password '...'"
  echo ""
  EXTRA_ARGS=("--dry-run")
fi

STOPPED=0
if [[ "$DRY" -eq 0 && "$CONFIRM" == "RESET" ]]; then
  if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    echo "Stopping $SERVICE_NAME for consistent reset..."
    sudo systemctl stop "$SERVICE_NAME"
    STOPPED=1
  fi
fi

"$VENV_PYTHON" scripts/reset_operational_data.py --db "$DB_PATH" "${EXTRA_ARGS[@]}"
STATUS=$?

if [[ "$STOPPED" -eq 1 ]]; then
  echo "Restarting $SERVICE_NAME..."
  sudo systemctl start "$SERVICE_NAME"
fi

if [[ "$STATUS" -eq 0 && "$DRY" -eq 0 && "$CONFIRM" == "RESET" ]]; then
  echo ""
  echo "Optional: remove uploaded attachments (not done automatically):"
  echo "  ls -la ${APP_DIR}/static/uploads ${APP_DIR}/uploads 2>/dev/null || true"
fi

exit "$STATUS"
