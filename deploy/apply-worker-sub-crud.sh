#!/bin/bash
# Apply worker + subcontractor edit/delete patch on VPS.
# Usage (on server):
#   cd /var/www/maxek-erp-flask
#   unzip -o /tmp/worker-sub-crud-patch.zip -d /tmp/worker-sub-crud-patch
#   bash deploy/apply-worker-sub-crud.sh /tmp/worker-sub-crud-patch

set -euo pipefail

APP_ROOT="${1:-/tmp/worker-sub-crud-patch}"
TARGET="/var/www/maxek-erp-flask"

if [[ ! -f "$APP_ROOT/app.py" ]]; then
  echo "ERROR: $APP_ROOT/app.py not found. Unzip the patch first."
  exit 1
fi

for f in app.py \
  templates/workers.html \
  templates/subcontractors.html \
  static/js/workers-form.js \
  static/js/subcontractors.js; do
  if [[ ! -f "$APP_ROOT/$f" ]]; then
    echo "ERROR: missing $APP_ROOT/$f"
    exit 1
  fi
  install -D -m 0644 "$APP_ROOT/$f" "$TARGET/$f"
  echo "OK: $f"
done

chown -R www-data:www-data "$TARGET/app.py" \
  "$TARGET/templates/workers.html" \
  "$TARGET/templates/subcontractors.html" \
  "$TARGET/static/js/workers-form.js" \
  "$TARGET/static/js/subcontractors.js"

if [[ -x "$TARGET/.venv/bin/python" ]]; then
  (cd "$TARGET" && "$TARGET/.venv/bin/python" deploy/migrate_db.py) || true
fi

systemctl restart maxek-erp
sleep 2
systemctl is-active maxek-erp

echo "--- verify ---"
grep -n "editing_worker" "$TARGET/app.py" | head -1 || echo "WARN: editing_worker not in app.py"
grep -n "Edit" "$TARGET/templates/workers.html" | head -1 || echo "WARN: Edit not in workers.html"
curl -s -o /dev/null -w "workers HTTP %{http_code}\n" http://127.0.0.1:8000/workers || true

echo "Done. Hard-refresh browser (Ctrl+Shift+R) on Worker Creation page."
