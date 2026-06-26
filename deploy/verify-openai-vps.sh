#!/bin/bash
# MAXEK ERP — Verify OpenAI API key, billing, and connectivity (run on VPS)
# Usage: bash deploy/verify-openai-vps.sh [/var/www/maxek_erp]
set -euo pipefail

APP_DIR="${1:-/var/www/maxek_erp}"

if [ ! -d "$APP_DIR" ]; then
  echo "ERROR: Application directory not found: $APP_DIR"
  exit 1
fi

cd "$APP_DIR"

if [ ! -d venv ]; then
  echo "ERROR: venv not found. Run deploy/setup-openai-vps.sh first."
  exit 1
fi

# shellcheck disable=SC1091
source venv/bin/activate

python deploy/verify_openai_api.py "$APP_DIR"
