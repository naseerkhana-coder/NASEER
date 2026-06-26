#!/bin/bash
# MAXEK ERP — Test /api/ai/* Flask routes (run on VPS after OpenAI is configured)
# Usage: bash deploy/test-ai-endpoints.sh [/var/www/maxek_erp] [base_url] [username] [password]
set -euo pipefail

APP_DIR="${1:-/var/www/maxek_erp}"
BASE_URL="${2:-http://127.0.0.1:8000}"
LOGIN_USER="${3:-admin}"
LOGIN_PASS="${4:-admin}"

COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR"' EXIT

pass=0
fail=0

note() { echo "$*"; }
pass_check() { echo "  PASS  $1"; pass=$((pass + 1)); }
fail_check() { echo "  FAIL  $1"; fail=$((fail + 1)); }

json_post() {
  local path="$1"
  local body="$2"
  curl -s -b "$COOKIE_JAR" -X POST \
    -H "Content-Type: application/json" \
    -d "$body" \
    "${BASE_URL}${path}"
}

echo "=== AI route tests ==="
echo "Base URL: ${BASE_URL}"
echo "Login as: ${LOGIN_USER}"
echo ""

echo "--- Login (session required for /api/ai/*) ---"
LOGIN_CODE="$(curl -s -c "$COOKIE_JAR" -b "$COOKIE_JAR" -o /dev/null -w '%{http_code}' \
  -X POST -d "username=${LOGIN_USER}&password=${LOGIN_PASS}" "${BASE_URL}/login")"
if [ "$LOGIN_CODE" = "200" ] || [ "$LOGIN_CODE" = "302" ]; then
  pass_check "login (${LOGIN_CODE})"
else
  fail_check "login (${LOGIN_CODE})"
  echo "Cannot continue without session."
  exit 1
fi

echo ""
echo "--- POST /api/ai/project-assistant ---"
RESP="$(json_post "/api/ai/project-assistant" '{"message":"List three MAXEK ERP modules in one sentence."}')"
if echo "$RESP" | grep -q '"reply"'; then
  pass_check "project-assistant returned reply"
  echo "       $(echo "$RESP" | head -c 200)..."
elif echo "$RESP" | grep -q 'openai_not_configured'; then
  fail_check "project-assistant — OPENAI_API_KEY not loaded (503 openai_not_configured)"
  echo "       $RESP"
elif echo "$RESP" | grep -q 'openai_error'; then
  fail_check "project-assistant — OpenAI error (503)"
  echo "       $RESP"
else
  fail_check "project-assistant unexpected response"
  echo "       $RESP"
fi

echo ""
echo "--- POST /api/ai/dpr-writer ---"
RESP="$(json_post "/api/ai/dpr-writer" '{"notes":"Foundation work progressed; 12 cum concrete poured."}')"
if echo "$RESP" | grep -q '"narrative"'; then
  pass_check "dpr-writer returned narrative"
elif echo "$RESP" | grep -q 'openai_not_configured'; then
  fail_check "dpr-writer — OPENAI_API_KEY not loaded"
else
  fail_check "dpr-writer unexpected response"
  echo "       $(echo "$RESP" | head -c 200)"
fi

echo ""
echo "--- POST /api/ai/boq-search ---"
RESP="$(json_post "/api/ai/boq-search" '{"query":"concrete"}')"
if echo "$RESP" | grep -q '"items"'; then
  pass_check "boq-search returned items array"
elif echo "$RESP" | grep -q 'openai_not_configured'; then
  fail_check "boq-search — OPENAI_API_KEY not loaded"
else
  fail_check "boq-search unexpected response"
  echo "       $(echo "$RESP" | head -c 200)"
fi

echo ""
echo "--- POST /api/ai/document-reader (inline text) ---"
RESP="$(json_post "/api/ai/document-reader" '{"text":"Site meeting held. Safety briefing completed. Target: finish slab by Friday."}')"
if echo "$RESP" | grep -q '"summary"'; then
  pass_check "document-reader returned summary"
elif echo "$RESP" | grep -q 'openai_not_configured'; then
  fail_check "document-reader — OPENAI_API_KEY not loaded"
else
  fail_check "document-reader unexpected response"
  echo "       $(echo "$RESP" | head -c 200)"
fi

echo ""
echo "--- Unauthenticated request (expect 401) ---"
UNAUTH="$(curl -s -o /dev/null -w '%{http_code}' -X POST \
  -H "Content-Type: application/json" \
  -d '{"message":"test"}' \
  "${BASE_URL}/api/ai/project-assistant")"
if [ "$UNAUTH" = "401" ]; then
  pass_check "unauthenticated blocked (401)"
else
  fail_check "expected 401 without session, got ${UNAUTH}"
fi

if [ -d "$APP_DIR/venv" ]; then
  echo ""
  echo "--- ai_service.py (direct module test) ---"
  cd "$APP_DIR"
  # shellcheck disable=SC1091
  source venv/bin/activate
  if python deploy/test_ai_service.py "$APP_DIR"; then
    pass_check "ai_service direct tests"
  else
    fail_check "ai_service direct tests"
  fi
fi

echo ""
echo "=== Results: ${pass} passed, ${fail} failed ==="
exit "$fail"
