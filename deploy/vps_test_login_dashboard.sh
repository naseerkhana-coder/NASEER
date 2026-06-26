#!/usr/bin/env bash
# MAXEK ERP — smoke test login → dashboard on VPS (run on server as deploy user).
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8000}"
COMPANY_CODE="${MAXEK_COMPANY_CODE:-MAXEK}"
USERNAME="${MAXEK_USERNAME:-superadmin}"
PASSWORD="${MAXEK_PASSWORD:-superadmin123}"
COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR"' EXIT

echo "==> GET $BASE_URL/login"
LOGIN_CODE=$(curl -sS -o /dev/null -w "%{http_code}" -c "$COOKIE_JAR" "$BASE_URL/login")
echo "    HTTP $LOGIN_CODE"
if [[ "$LOGIN_CODE" != "200" ]]; then
  echo "FAIL: expected 200 on /login" >&2
  exit 1
fi

echo "==> POST $BASE_URL/login (company=$COMPANY_CODE user=$USERNAME)"
POST_CODE=$(curl -sS -o /dev/null -w "%{http_code}" -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
  -X POST "$BASE_URL/login" \
  -d "company_code=${COMPANY_CODE}" \
  -d "username=${USERNAME}" \
  -d "password=${PASSWORD}")
echo "    HTTP $POST_CODE (expect 302 redirect to dashboard)"
if [[ "$POST_CODE" != "302" && "$POST_CODE" != "303" ]]; then
  echo "FAIL: login did not redirect" >&2
  exit 1
fi

echo "==> GET $BASE_URL/dashboard (authenticated)"
DASH_BODY="$(mktemp)"
trap 'rm -f "$COOKIE_JAR" "$DASH_BODY"' EXIT
DASH_CODE=$(curl -sS -o "$DASH_BODY" -w "%{http_code}" -b "$COOKIE_JAR" "$BASE_URL/dashboard")
echo "    HTTP $DASH_CODE"
if [[ "$DASH_CODE" != "200" ]]; then
  echo "FAIL: dashboard returned $DASH_CODE" >&2
  head -c 2000 "$DASH_BODY" >&2 || true
  echo >&2
  exit 1
fi

if grep -qi "internal server error" "$DASH_BODY"; then
  echo "FAIL: dashboard body contains Internal Server Error" >&2
  exit 1
fi

if ! grep -qi "command centre" "$DASH_BODY"; then
  echo "WARN: dashboard body missing 'Command Centre' heading (check deploy version)" >&2
fi

echo "PASS: login → dashboard OK"
