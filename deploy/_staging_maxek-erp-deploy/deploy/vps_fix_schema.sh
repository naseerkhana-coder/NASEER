#!/bin/bash
# MAXEK ERP — one-shot production schema repair (safe to re-run)
# Usage: bash deploy/vps_fix_schema.sh [/var/www/maxek-erp-flask]
set -euo pipefail

APP_DIR="${1:-/var/www/maxek-erp-flask}"
cd "$APP_DIR"

echo "=============================================="
echo " MAXEK ERP — Schema repair"
echo " App dir: ${APP_DIR}"
echo "=============================================="

export MAXEK_SKIP_DEMO_SEED=1

if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
elif [ -d "venv" ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

python3 << 'PYEOF'
import os
import sqlite3

app_dir = os.getcwd()
db_path = os.path.join(app_dir, "database", "maxek.db")
if not os.path.isfile(db_path):
    raise SystemExit(f"Database not found: {db_path}")

conn = sqlite3.connect(db_path)


def ensure(table, column, coltype):
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
        print(f"ADDED  {table}.{column}")
    else:
        print(f"OK     {table}.{column}")


def ensure_table(name, create_sql):
    conn.execute(create_sql)
    print(f"OK     table {name}")


ensure_table(
    "subcontractor_manpower_rates",
  """
    CREATE TABLE IF NOT EXISTS subcontractor_manpower_rates(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subcontractor_id INTEGER NOT NULL,
        trade_name TEXT,
        rate_unit TEXT,
        working_hours REAL,
        rate_amount REAL,
        salary_amount REAL,
        FOREIGN KEY(subcontractor_id) REFERENCES subcontractors(id)
    )
  """,
)
ensure_table(
    "subcontractor_boq_rates",
  """
    CREATE TABLE IF NOT EXISTS subcontractor_boq_rates(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subcontractor_id INTEGER NOT NULL,
        project_id INTEGER,
        boq_item_id INTEGER,
        boq_number TEXT,
        item_description TEXT,
        unit TEXT,
        rate REAL,
        quantity REAL,
        total_amount REAL,
        line_no INTEGER,
        FOREIGN KEY(subcontractor_id) REFERENCES subcontractors(id),
        FOREIGN KEY(project_id) REFERENCES projects(id)
    )
  """,
)

SCHEMA_FIXES = [
    ("users", "designation_id", "INTEGER"),
    ("users", "workflow_role", "TEXT"),
    ("users", "reporting_manager", "TEXT"),
    ("users", "employee_name", "TEXT"),
    ("users", "department", "TEXT"),
    ("users", "status", "TEXT DEFAULT 'Active'"),
    ("users", "role", "TEXT"),
    ("users", "staff_id", "INTEGER"),
    ("attendance", "approval_status", "TEXT DEFAULT 'Pending Checker'"),
    ("attendance", "worker_source", "TEXT DEFAULT 'worker'"),
    ("workers", "worker_category", "TEXT DEFAULT 'Company Staff'"),
    ("workers", "subcontractor_id", "INTEGER"),
    ("notifications", "notification_type", "TEXT"),
    ("notifications", "module_id", "TEXT"),
    ("notifications", "record_id", "INTEGER"),
    ("notifications", "record_table", "TEXT"),
    ("approval_audit", "actor_username", "TEXT"),
    ("approval_requests", "checker_comment", "TEXT"),
    ("approval_requests", "approver_comment", "TEXT"),
    ("subcontractors", "subcontractor_code", "TEXT"),
    ("subcontractors", "date_of_birth", "TEXT"),
    ("subcontractors", "id_number", "TEXT"),
    ("subcontractors", "id_document", "TEXT"),
    ("subcontractors", "photo", "TEXT"),
    ("subcontractors", "pan_number", "TEXT"),
    ("subcontractors", "pan_document", "TEXT"),
    ("subcontractors", "bank_account", "TEXT"),
    ("subcontractors", "bank_name", "TEXT"),
    ("subcontractors", "ifsc_code", "TEXT"),
    ("subcontractors", "branch_name", "TEXT"),
    ("subcontractors", "rate_type", "TEXT"),
    ("subcontractor_manpower_rates", "subcontractor_id", "INTEGER"),
    ("subcontractor_manpower_rates", "trade_name", "TEXT"),
    ("subcontractor_manpower_rates", "rate_unit", "TEXT"),
    ("subcontractor_manpower_rates", "working_hours", "REAL"),
    ("subcontractor_manpower_rates", "rate_amount", "REAL"),
    ("subcontractor_manpower_rates", "salary_amount", "REAL"),
    ("subcontractor_boq_rates", "subcontractor_id", "INTEGER"),
    ("subcontractor_boq_rates", "project_id", "INTEGER"),
    ("subcontractor_boq_rates", "boq_item_id", "INTEGER"),
    ("subcontractor_boq_rates", "boq_number", "TEXT"),
    ("subcontractor_boq_rates", "item_description", "TEXT"),
    ("subcontractor_boq_rates", "unit", "TEXT"),
    ("subcontractor_boq_rates", "rate", "REAL"),
    ("subcontractor_boq_rates", "quantity", "REAL"),
    ("subcontractor_boq_rates", "total_amount", "REAL"),
    ("subcontractor_boq_rates", "line_no", "INTEGER"),
    ("boq_items", "boq_id", "INTEGER"),
    ("boq_items", "line_no", "INTEGER"),
    ("boq_items", "project_id", "INTEGER"),
]

for table, column, coltype in SCHEMA_FIXES:
    ensure(table, column, coltype)

conn.execute(
    "UPDATE users SET status='Active' WHERE status IS NULL OR TRIM(status)=''"
)
conn.execute(
    "UPDATE workers SET worker_category='Company Staff' "
    "WHERE worker_category IS NULL OR TRIM(worker_category)=''"
)
conn.commit()
conn.close()
print("Standalone schema repair complete.")
PYEOF

if python3 -c "import app" 2>/dev/null; then
  echo "Running app.init_db() for any remaining migrations..."
  python3 -c "from app import app, init_db; app.app_context().push(); init_db(); print('init_db OK')"
else
  echo "app.py import skipped (standalone repair only)."
fi

echo "Restarting maxek-erp..."
sudo systemctl restart maxek-erp
sleep 2
sudo systemctl status maxek-erp --no-pager || true

echo ""
echo "Verify:"
echo "  sqlite3 database/maxek.db \"PRAGMA table_info(subcontractor_boq_rates);\" | grep subcontractor_id"
echo "  sqlite3 database/maxek.db \"PRAGMA table_info(subcontractors);\" | grep rate_type"
echo "  journalctl -u maxek-erp -n 20 --no-pager"
