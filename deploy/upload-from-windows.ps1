# Run this on YOUR WINDOWS PC (not on the VPS).
# Uploads worker/subcontractor edit-delete files directly to srv1704727.

$ErrorActionPreference = "Stop"
$src = Split-Path $PSScriptRoot -Parent
$remote = "root@srv1704727"
$app = "/var/www/maxek-erp-flask"

Write-Host "Uploading from: $src"
Write-Host "To: $remote ($app)"
Write-Host ""

scp "$src\app.py" "${remote}:${app}/"
scp "$src\templates\workers.html" "${remote}:${app}/templates/"
scp "$src\templates\subcontractors.html" "${remote}:${app}/templates/"
scp "$src\static\js\workers-form.js" "${remote}:${app}/static/js/"
scp "$src\static\js\subcontractors.js" "${remote}:${app}/static/js/"

Write-Host ""
Write-Host "Done. Now on VPS run:"
Write-Host "  chown www-data:www-data $app/app.py $app/templates/workers.html $app/templates/subcontractors.html $app/static/js/workers-form.js $app/static/js/subcontractors.js"
Write-Host "  systemctl restart maxek-erp"
Write-Host "  grep -n editing_worker $app/app.py | head -1"
