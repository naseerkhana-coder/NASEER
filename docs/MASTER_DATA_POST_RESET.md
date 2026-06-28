# Master Data After Operational Reset

Use with `scripts/reset_operational_data.py` (default: `--reseed` on live reset).

## Preserved tables (KEEP_TABLES)

| Table | Purpose |
|-------|---------|
| `designations` | HR designation lookup |
| `departments` | Org department master |
| `trades` | Worker trade lookup |
| `chart_of_accounts` | Accounts COA (idempotent re-seed) |
| `workflow_master` | Approval workflow definitions |
| `steel_shapes`, `qc_tests` | DPR/QC reference |
| `app_settings`, `erp_settings` | Platform configuration |
| `erp_customers`, `erp_licenses`, `erp_subscriptions` | Tenants & licensing |
| `erp_*_limits` | User/branch/storage limits |
| `number_sequences`, `document_number_sequences` | Doc numbering (counters reset separately) |
| `help_topics`, `corporate_report_templates` | Help & report templates |
| `company_country_field_config` | Company master field metadata |

## Re-seeded on reset (when `--reseed`, default)

1. **departments** — default rows via `_ensure_department_defaults`
2. **designations** + **workflow_master** — `workflow_service.seed_designations`, `seed_workflow_master`
3. **chart_of_accounts** — `accounts_service.seed_chart_of_accounts` (idempotent)

## Users after reset

- Keeps platform **superadmin** and tenant **admin** accounts (see `_prune_users` in reset script)
- Optional: `--new-admin-password '…'` to reset `admin` password
- Demo tenant `DEMO001` customer row is preserved if present in `erp_customers`

## Verify on VPS

```bash
cd /var/www/maxek-erp-flask && source venv/bin/activate
python - <<'PY'
import sqlite3
db = sqlite3.connect("database/maxek.db")
for t in ("designations", "departments", "chart_of_accounts", "workflow_master", "erp_customers"):
    n = db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"{t}: {n} rows")
PY
```

Expected: non-zero counts for masters; at least one `erp_customers` row (platform + tenants).
