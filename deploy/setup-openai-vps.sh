#!/bin/bash
# MAXEK ERP — Install OpenAI SDK in production venv (run on VPS via SSH)
# Usage: bash deploy/setup-openai-vps.sh [/var/www/maxek_erp]
set -euo pipefail

APP_DIR="${1:-/var/www/maxek_erp}"

echo "=============================================="
echo " MAXEK ERP — OpenAI package setup"
echo " App dir: ${APP_DIR}"
echo "=============================================="

if [ ! -d "$APP_DIR" ]; then
  echo "ERROR: Application directory not found: $APP_DIR"
  exit 1
fi

cd "$APP_DIR"

if [ ! -d venv ]; then
  echo "ERROR: venv not found. Run deploy/vps_setup.sh first."
  exit 1
fi

# shellcheck disable=SC1091
source venv/bin/activate

echo "[1/3] Upgrading pip..."
pip install --upgrade pip -q

echo "[2/3] Installing openai>=1.0.0 (also in requirements.txt)..."
pip install 'openai>=1.0.0' -q

echo "[3/3] Verifying import..."
python - <<'PY'
import openai
from ai_service import OPENAI_MODEL, get_openai_client, OpenAIConfigurationError

print(f"  openai package version: {openai.__version__}")
print(f"  default model (OPENAI_MODEL): {OPENAI_MODEL}")
try:
    get_openai_client()
    print("  OPENAI_API_KEY: set (client can be constructed)")
except OpenAIConfigurationError as exc:
    print(f"  OPENAI_API_KEY: not set — {exc}")
    print("  Add OPENAI_API_KEY to .env, then restart maxek-erp.")
PY

if [ ! -f .env ]; then
  echo ""
  echo "WARN: .env missing. Copy deploy/.env.example to .env and set OPENAI_API_KEY."
elif ! grep -q '^OPENAI_API_KEY=' .env 2>/dev/null; then
  echo ""
  echo "Next: add OpenAI settings to .env (see deploy/OPENAI_VPS_SETUP.md):"
  echo "  OPENAI_API_KEY=sk-..."
  echo "  OPENAI_MODEL=gpt-4o-mini"
fi

echo ""
echo "Setup complete. Configure the API key, then run:"
echo "  bash deploy/verify-openai-vps.sh ${APP_DIR}"
