# MAXEK ERP — OpenAI VPS Setup

Step-by-step checklist to enable AI features (`ai_service.py`, `ai_routes.py`) on the Linux VPS.

**Prerequisites:** MAXEK ERP already deployed (`deploy/vps_setup.sh` or equivalent), Gunicorn running via `maxek-erp` systemd unit.

**Billing:** OpenAI usage is metered. Before go-live, confirm a valid payment method and usage limits at [OpenAI Billing](https://platform.openai.com/settings/organization/billing).

---

## What gets configured

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `OPENAI_API_KEY` | Yes (for AI features) | — | Secret key from [OpenAI API keys](https://platform.openai.com/api-keys) |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | Chat model for DPR writer, project assistant, BOQ search, document reader |

The app reads these from the process environment. Production uses **`.env`** loaded by systemd (`EnvironmentFile` in `deploy/maxek-erp.service`).

---

## Checklist

### 1. Upload latest code

Ensure the VPS has:

- `ai_service.py`, `ai_routes.py`, `app.py` (with `register_ai_routes`)
- `requirements.txt` (includes `openai>=1.0.0`)
- `deploy/setup-openai-vps.sh`, `deploy/verify-openai-vps.sh`, `deploy/test-ai-endpoints.sh`

See `deploy/DEPLOYMENT.md` or `deploy/VPS_UPDATE_RUNBOOK.md` for WinSCP upload workflow.

### 2. Install OpenAI package in venv

SSH into the VPS:

```bash
cd /var/www/maxek_erp
chmod +x deploy/setup-openai-vps.sh deploy/verify-openai-vps.sh deploy/test-ai-endpoints.sh
bash deploy/setup-openai-vps.sh /var/www/maxek_erp
```

This activates `venv`, installs `openai>=1.0.0`, and verifies `import openai` and `ai_service` load correctly.

**Alternative (full dependency sync):**

```bash
cd /var/www/maxek_erp
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure `OPENAI_API_KEY` on the VPS

**Recommended: app `.env` file** (matches existing MAXEK pattern)

```bash
cd /var/www/maxek_erp
nano .env
```

Add or update:

```env
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4o-mini
```

Secure the file (only `www-data` should read secrets):

```bash
sudo chown www-data:www-data .env
sudo chmod 600 .env
```

**Never commit `.env` or API keys to git or WinSCP upload packages.**

Restart so Gunicorn workers pick up the new variables:

```bash
sudo systemctl restart maxek-erp
sudo systemctl status maxek-erp
```

**How systemd loads env:** `deploy/maxek-erp.service` contains:

```ini
EnvironmentFile=-/var/www/maxek_erp/.env
```

(`vps_setup.sh` rewrites the path if your app directory differs.)

**Optional: separate secrets file**

```bash
sudo nano /etc/maxek-erp/openai.env
# OPENAI_API_KEY=sk-...
# OPENAI_MODEL=gpt-4o-mini
sudo chmod 600 /etc/maxek-erp/openai.env
sudo chown root:www-data /etc/maxek-erp/openai.env
```

Add to the systemd unit under `[Service]`:

```ini
EnvironmentFile=-/etc/maxek-erp/openai.env
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl restart maxek-erp
```

### 4. Verify API connectivity and billing

```bash
bash deploy/verify-openai-vps.sh /var/www/maxek_erp
```

This runs `deploy/verify_openai_api.py`, which:

1. Imports the `openai` package
2. Calls `ai_service.get_openai_client()`
3. Calls `models.list` (auth / account access)
4. Runs a minimal `chat.completions.create` (model + billing)

**Common errors and fixes**

| Error / symptom | Likely cause | Action |
|-----------------|--------------|--------|
| `OPENAI_API_KEY is not configured` | Key missing from `.env` or service not restarted | Add key to `.env`, `systemctl restart maxek-erp` |
| `401` / `invalid_api_key` | Wrong or revoked key | Create new key in OpenAI dashboard |
| `insufficient_quota` / quota exceeded | No credits or hard limit hit | Add billing / raise limits in OpenAI dashboard |
| `model_not_found` | Model not enabled for org | Set `OPENAI_MODEL=gpt-4o-mini` or choose an available model |
| `503 openai_not_configured` in browser | Workers started before key was set | Restart `maxek-erp` after editing `.env` |

For full Python tracebacks during diagnosis:

```bash
OPENAI_VERIFY_TRACE=1 bash deploy/verify-openai-vps.sh /var/www/maxek_erp
```

### 5. Test `ai_service.py` directly

```bash
cd /var/www/maxek_erp
source venv/bin/activate
python deploy/test_ai_service.py /var/www/maxek_erp
```

Exercises `get_openai_client`, `chat_completion`, and `chat_completion_json` without HTTP.

### 6. Test Flask AI routes

With the app running and a valid login (default demo: `admin` / `admin` — change in production):

```bash
bash deploy/test-ai-endpoints.sh /var/www/maxek_erp http://127.0.0.1:8000 admin admin
```

Tests:

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/ai/project-assistant` | POST | Copilot Q&A |
| `/api/ai/dpr-writer` | POST | DPR narrative |
| `/api/ai/boq-search` | POST | Natural-language BOQ search |
| `/api/ai/document-reader` | POST | Document summary (inline text) |

**Manual curl example (project assistant):**

```bash
COOKIE_JAR=$(mktemp)
curl -s -c "$COOKIE_JAR" -b "$COOKIE_JAR" -X POST \
  -d "username=admin&password=admin" \
  "http://127.0.0.1:8000/login" -o /dev/null

curl -s -b "$COOKIE_JAR" -X POST \
  -H "Content-Type: application/json" \
  -d '{"message":"What is a DPR in construction?"}' \
  "http://127.0.0.1:8000/api/ai/project-assistant" | python3 -m json.tool
```

Expected success shape: `{"reply":"...", "project_id": null}`.

### 7. Browser verification

1. Log in to MAXEK ERP
2. Open a screen that uses AI (DPR writer, project assistant, BOQ AI search, document reader)
3. Confirm you get a response — not `AI service is temporarily unavailable` or `OPENAI_API_KEY is not configured`

Check logs if something fails:

```bash
journalctl -u maxek-erp -n 100 --no-pager
```

---

## Production checklist

- [ ] `openai` installed in VPS `venv` (`setup-openai-vps.sh` or `pip install -r requirements.txt`)
- [ ] `OPENAI_API_KEY` set in `.env` (or systemd `EnvironmentFile`), **not** in repo
- [ ] `.env` permissions: `chmod 600`, owned by `www-data`
- [ ] `OPENAI_MODEL` set if not using default `gpt-4o-mini`
- [ ] OpenAI billing confirmed active ([billing dashboard](https://platform.openai.com/settings/organization/billing))
- [ ] `verify-openai-vps.sh` passes all four checks
- [ ] `test-ai-endpoints.sh` passes
- [ ] `maxek-erp` restarted after env changes
- [ ] AI features verified in browser

---

## After code updates

When deploying AI-related changes via WinSCP:

```bash
bash deploy/vps_backup.sh /var/www/maxek_erp
# upload files
bash deploy/vps_update.sh /var/www/maxek_erp   # reinstalls requirements.txt including openai
bash deploy/verify-openai-vps.sh /var/www/maxek_erp
bash deploy/test-ai-endpoints.sh /var/www/maxek_erp
```

If only the API key or model changed, restart is enough:

```bash
sudo systemctl restart maxek-erp
bash deploy/verify-openai-vps.sh /var/www/maxek_erp
```

---

## Related files

| File | Role |
|------|------|
| `deploy/setup-openai-vps.sh` | Install `openai` in venv |
| `deploy/verify-openai-vps.sh` | Shell wrapper for API verification |
| `deploy/verify_openai_api.py` | `models.list` + minimal completion tests |
| `deploy/test_ai_service.py` | Direct `ai_service.py` tests |
| `deploy/test-ai-endpoints.sh` | HTTP tests for `/api/ai/*` |
| `deploy/.env.example` | Template including OpenAI variables |
| `deploy/maxek-erp.service` | systemd unit loading `.env` |
