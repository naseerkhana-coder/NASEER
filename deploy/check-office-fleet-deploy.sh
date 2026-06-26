#!/usr/bin/env bash
# MAXEK ERP — Office & Fleet deploy sanity check (run on VPS from app root)
# Usage: cd /var/www/maxek-erp-flask && bash deploy/check-office-fleet-deploy.sh

set -euo pipefail
APP_ROOT="${APP_ROOT:-$(pwd)}"
cd "$APP_ROOT"

echo "=== MAXEK Office & Fleet deploy check ==="
echo "App root: $APP_ROOT"
echo

# --- 1. Required templates (from app.py render_template + base layout) ---
TEMPLATES=(
  templates/base_maxek.html
  templates/department_hub.html
  templates/office_dashboard.html
  templates/office_inward.html
  templates/office_outward.html
  templates/office_letters.html
  templates/office_quotations.html
  templates/office_po_register.html
  templates/office_agreements.html
  templates/office_legal.html
  templates/fleet_dashboard.html
  templates/fleet_vehicles.html
  templates/fleet_vehicle_documents.html
  templates/fleet_running_log.html
  templates/fleet_diesel_purchase.html
  templates/fleet_diesel_stock.html
  templates/fleet_diesel_issue.html
  templates/letter_print.html
  templates/quotation_print.html
  templates/vehicle_print.html
)

echo "--- Missing templates ---"
missing=0
for t in "${TEMPLATES[@]}"; do
  if [[ ! -f "$t" ]]; then
    echo "MISSING: $t"
    missing=$((missing + 1))
  fi
done
if [[ $missing -eq 0 ]]; then
  echo "OK: all ${#TEMPLATES[@]} office/fleet templates present"
fi
echo

# --- 2. Core Python modules ---
echo "--- Python modules ---"
for f in app.py office_fleet_service.py; do
  if [[ -f "$f" ]]; then
    echo "OK: $f ($(wc -l < "$f" | tr -d ' ') lines)"
  else
    echo "MISSING: $f"
  fi
done
echo

# --- 3. NAV_GROUPS office-fleet endpoints vs @app.route function names ---
echo "--- Office-fleet route endpoints (grep app.py) ---"
ENDPOINTS=(
  office_admin office_inward office_outward office_letters office_letter_print
  office_quotations office_quotation_print office_po_register office_agreements office_legal
  fleet_dashboard fleet_vehicles fleet_vehicle_print fleet_vehicle_documents
  fleet_running_log fleet_diesel_purchase fleet_diesel_stock fleet_diesel_issue
  office_document_download fleet_document_download department_hub
)
for ep in "${ENDPOINTS[@]}"; do
  if grep -qE "def ${ep}\(" app.py 2>/dev/null; then
    echo "OK: $ep"
  else
    echo "MISSING ROUTE: $ep"
  fi
done
echo

# --- 4. render_template calls in office/fleet section ---
echo "--- render_template targets (office/fleet block in app.py) ---"
grep -n 'render_template("' app.py | awk -F'"' '/office_|fleet_|letter_print|quotation_print|vehicle_print|department_hub/ {print $2}' | sort -u | while read -r tpl; do
  path="templates/${tpl}"
  if [[ -f "$path" ]]; then
    echo "OK: $tpl"
  else
    echo "MISSING (referenced in app.py): $tpl"
  fi
done
echo

# --- 5. base_maxek toolbar uses safe_url_for (post-hardening) ---
echo "--- base_maxek toolbar hardening ---"
if grep -q 'safe_url_for(item.endpoint' templates/base_maxek.html 2>/dev/null; then
  echo "OK: base_maxek.html uses safe_url_for for toolbar"
else
  echo "WARN: base_maxek.html still uses raw url_for in toolbar (BuildError risk on partial deploy)"
fi
if grep -q 'def safe_url_for' app.py 2>/dev/null; then
  echo "OK: app.py defines safe_url_for"
else
  echo "WARN: app.py missing safe_url_for"
fi
if grep -qE 'jinja_env\.globals\[.safe_url_for.\]' app.py 2>/dev/null; then
  echo "OK: safe_url_for registered on jinja_env.globals"
else
  echo "WARN: safe_url_for not on jinja_env.globals (UndefinedError risk on /fleet)"
fi
if [[ -f templates/fleet_dashboard.html ]]; then
  echo "OK: templates/fleet_dashboard.html present"
else
  echo "MISSING: templates/fleet_dashboard.html"
fi
if grep -q 'safe_url_for(mod.endpoint' templates/fleet_dashboard.html 2>/dev/null; then
  echo "OK: fleet_dashboard.html uses safe_url_for for module links"
else
  echo "WARN: fleet_dashboard.html missing safe_url_for on module links"
fi
echo

# --- 6. Quick Flask import smoke (optional, needs venv) ---
if [[ -x venv/bin/python ]]; then
  echo "--- Flask import smoke ---"
  if venv/bin/python -c "import app; print('OK: app imports')" 2>/dev/null; then
    :
  else
    echo "FAIL: app.py import error (run: venv/bin/python -c 'import app')"
  fi
  echo
fi

echo "=== journalctl one-liner (last office/fleet errors) ==="
echo "sudo journalctl -u maxek-erp -n 100 --no-pager | grep -iE 'office|fleet|TemplateNotFound|BuildError|UndefinedError|safe_url_for|500'"

echo
echo "=== grep app log (if file-based) ==="
echo "grep -iE 'office|fleet|TemplateNotFound|BuildError' /var/log/maxek-erp/*.log 2>/dev/null | tail -30"
