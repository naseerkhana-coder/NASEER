# Build zip for VPS: worker + subcontractor edit/delete
$ErrorActionPreference = "Stop"
$src = Split-Path $PSScriptRoot -Parent
$staging = Join-Path $PSScriptRoot "worker-sub-crud-staging"
$out = Join-Path $PSScriptRoot "worker-sub-crud-patch.zip"
$files = @(
    "app.py",
    "templates\workers.html",
    "templates\subcontractors.html",
    "static\js\workers-form.js",
    "static\js\subcontractors.js"
)

if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
if (Test-Path $out) { Remove-Item $out -Force }
New-Item -ItemType Directory -Path $staging | Out-Null

foreach ($rel in $files) {
    $full = Join-Path $src $rel
    if (-not (Test-Path $full)) { throw "Missing file: $full" }
    $dest = Join-Path $staging $rel
    $destDir = Split-Path $dest -Parent
    if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
    Copy-Item $full $dest -Force
    Write-Host "Staged $rel"
}

Compress-Archive -Path (Join-Path $staging "*") -DestinationPath $out -Force
Remove-Item $staging -Recurse -Force

$item = Get-Item $out
Write-Host ""
Write-Host "Created: $($item.FullName)"
Write-Host "Size: $([math]::Round($item.Length/1KB, 1)) KB"
