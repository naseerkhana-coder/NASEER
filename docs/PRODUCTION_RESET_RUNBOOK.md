# Production reset runbook — master data only

**Target VPS:** `/var/www/maxek-erp-flask` · **URL:** https://erp.maxekindia.com  
**Database:** `database/maxek.db` (SQLite)

> **Do not run on production without explicit approval and a verified backup.**

---

## Table classification

### KEEP (master / lookup / platform config)

| Table(s) | Purpose |
|----------|---------|
| `designations` | Job titles; workflow routing |
| `departments` | Department dropdown defaults |
| `trades` | Trade master |
| `chart_of_accounts` | Head of accounts / COA defaults |
| `workflow_master` | Per-module approval configuration |
| `steel_shapes` | DPR steel reference |
| `qc_tests` | QC test master (if present) |
| `app_settings`, `erp_settings` | Application configuration |
| `erp_customers`, `erp_licenses`, `erp_subscriptions` | Multi-tenant platform |
| `erp_user_limits`, `erp_branch_limits`, `erp_storage_limits` | License limits |
| `number_sequences`, `document_number_sequences` | Counters (reset to 1, not dropped) |
| `help_topics`, `corporate_report_templates` | Help / report templates |
| `company_country_field_config` | Company form metadata |
| `users` | **Only** rows where `username` ∈ (`superadmin`, `admin`) |

### DELETE (operational / transactional)

All project, HR, store, accounts, treasury, plant, fleet, office, billing, and approval **transaction** tables — see full list in `scripts/reset_operational_data.py` → `CLEAR_TABLES`.

Includes: `projects`, `clients`, `staff`, `workers`, `attendance`, `purchase_orders`, `material_requests`, `account_expenses`, `payroll_*`, `dpr_*`, `boq_*`, `companies` / `company_branches` (operational company records), `erp_attachments`, `approval_requests`, etc.

### RESET (not deleted)

- Document number counters → `next_value=1` / `last_number=0`
- Optional re-seed: designations, departments (if empty), chart of accounts (idempotent), workflow_master

### Manual follow-up (not automated)

- Uploaded files under `static/uploads/`, `uploads/` — delete separately if required
- Reverse proxy / `.env` — unchanged
- Sample ERP customers (`TRD001`, `DEMO001`, …) — kept in `erp_customers` unless you manually prune

---

## VPS procedure (after backup)

```bash
# 1. SSH to VPS
ssh user@your-vps

# 2. Backup (mandatory)
cd /var/www/maxek-erp-flask
bash deploy/vps_backup.sh /var/www/maxek-erp-flask

# 3. Preview (no writes)
bash deploy/vps_reset_to_master_data.sh --dry-run

# 4. Execute reset + new admin password
bash deploy/vps_reset_to_master_data.sh \
  --confirm RESET \
  --new-admin-password 'YourNewSecurePassword!'

# 5. Verify
sudo systemctl status maxek-erp
curl -sI https://erp.maxekindia.com/login | head -5
python deploy/test_login_compatibility.py database/maxek.db admin 'YourNewSecurePassword!'
```

---

## Admin password reset (without full reset)

Passwords use **bcrypt** (`app.py` → `hash_password`), not Werkzeug `generate_password_hash`.

```bash
cd /var/www/maxek-erp-flask
source venv/bin/activate
python - <<'PY'
import sqlite3, bcrypt
db = sqlite3.connect("database/maxek.db")
plain = "YourNewSecurePassword!"  # change me
hashed = bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()
db.execute("UPDATE users SET password=?, status='Active' WHERE username='admin'", (hashed,))
db.commit()
print("admin password updated (bcrypt)")
PY
sudo systemctl restart maxek-erp
```

Test login:

```bash
python deploy/test_login_compatibility.py database/maxek.db admin 'YourNewSecurePassword!'
```

**Super Admin** (`superadmin`): same pattern with `WHERE username='superadmin'`. Default seed password is documented in `super_admin_service.py` (`SUPERADMIN_DEFAULT_PASSWORD`) — change in production.

---

## Multi-company & demo company

### What exists today

| Layer | Status |
|-------|--------|
| **ERP customers (tenants)** | `erp_customers` — Super Admin manages TRD001, MAX001, **DEMO001**, etc. |
| **Users scoped by tenant** | `users.customer_id` — composite username per customer |
| **Company master** | `companies`, `company_branches` — legal entities **within** a customer |
| **User work context** | `user_work_context` — selected company, branch, project |
| **Row-level isolation** | **Partial** — `tenant_isolation.py` adds columns to core tables; many modules still in `DEFERRED_TENANT_TABLES` |

### Recommended approach

**One SQLite database** on VPS (current architecture). Do **not** split demo into a separate DB unless you run a second deployment.

| Need | Approach |
|------|----------|
| Many production companies | Customer Admin → **Company Master** → add `company_code`, branches; users pick context in header |
| Many ERP customers (SaaS) | Super Admin → **Customer Master** → new `customer_code`, license, admin user |
| **Demo company** | Keep `erp_customers.customer_code = 'DEMO001'` (plan = Demo); login as `demo` / seed password; **reset demo** by running reset script scoped to demo customer (Phase 2 — see below) |
| Isolate demo from production data | **Phase 2:** enforce `customer_id` / `company_id` filters on all queries; until then, use **separate VPS** or reset demo DB before each demo |

### Implementation phases (if full isolation needed)

1. **Phase A (done):** Company master, user context, customer_id on users/companies.
2. **Phase B:** Migrate `DEFERRED_TENANT_TABLES` (DPR, BOQ, timesheets, expenses, notifications).
3. **Phase C:** Reset script `--customer-code DEMO001` to wipe one tenant only.
4. **Phase D (optional):** Read-only demo mode flag on `erp_customers.plan = 'Demo'`.

---

## Related files

| File | Purpose |
|------|---------|
| `scripts/reset_operational_data.py` | Core reset logic |
| `deploy/vps_reset_to_master_data.sh` | VPS wrapper (stop service, run, restart) |
| `deploy/vps_backup.sh` | Pre-reset backup |
| `docs/ERP_USER_GUIDE.md` | End-user module guide |
| `seed_super_admin.py` | Bootstrap platform superadmin |
| `super_admin_service.py` | Tenant / license model |
