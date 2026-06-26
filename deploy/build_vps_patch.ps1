# Build VPS patch ZIP for WinSCP upload to /var/www/maxek-erp-flask/

# Usage: powershell -ExecutionPolicy Bypass -File deploy/build_vps_patch.ps1

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Set-Location $Root



python deploy/build_vps_patch_latest.py

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }



$Stamp = Get-Date -Format "yyyyMMdd_HHmm"

$StampedZip = Join-Path $Root "deploy\dist\vps-patch-maxek-erp-flask-$Stamp.zip"

$LatestZip = Join-Path $Root "deploy\dist\vps-patch-latest.zip"

Copy-Item $LatestZip $StampedZip -Force



Write-Host ""

Write-Host "VPS patch ZIP ready:"

Write-Host "  $LatestZip"

Write-Host "  $StampedZip"

Write-Host ""

Write-Host "WinSCP: extract into /var/www/maxek-erp-flask/ (merge folders)"

Write-Host "Then run SSH steps in deploy/VPS_PATCH_maxek-erp-flask.txt"

