-- Petty Cash FRS schema upgrade (safe on existing VPS data)
-- Run: sqlite3 database/maxek.db < deploy/fix_petty_cash_db.sql
-- Skip errors if a column already exists (run from bash with || true per line if needed)

-- New columns on legacy petty_cash_requests
ALTER TABLE petty_cash_requests ADD COLUMN request_number TEXT;
ALTER TABLE petty_cash_requests ADD COLUMN project_id INTEGER;
ALTER TABLE petty_cash_requests ADD COLUMN employee_code TEXT;
ALTER TABLE petty_cash_requests ADD COLUMN department TEXT;
ALTER TABLE petty_cash_requests ADD COLUMN purpose TEXT;
ALTER TABLE petty_cash_requests ADD COLUMN description TEXT;
ALTER TABLE petty_cash_requests ADD COLUMN required_amount REAL DEFAULT 0;
ALTER TABLE petty_cash_requests ADD COLUMN approval_status TEXT DEFAULT 'Draft';
ALTER TABLE petty_cash_requests ADD COLUMN transferred_amount REAL DEFAULT 0;
ALTER TABLE petty_cash_requests ADD COLUMN expenses_total REAL DEFAULT 0;
ALTER TABLE petty_cash_requests ADD COLUMN settlement_remarks TEXT;
ALTER TABLE petty_cash_requests ADD COLUMN settlement_submitted_at TEXT;
ALTER TABLE petty_cash_requests ADD COLUMN settlement_reviewed_at TEXT;
ALTER TABLE petty_cash_requests ADD COLUMN settlement_reviewed_by TEXT;
ALTER TABLE petty_cash_requests ADD COLUMN created_by TEXT;
ALTER TABLE petty_cash_requests ADD COLUMN modified_by TEXT;
ALTER TABLE petty_cash_requests ADD COLUMN modified_at TEXT;

-- Backfill from legacy columns
UPDATE petty_cash_requests SET purpose = reason WHERE (purpose IS NULL OR purpose = '') AND reason IS NOT NULL;
UPDATE petty_cash_requests SET required_amount = requested_amount WHERE (required_amount IS NULL OR required_amount = 0) AND requested_amount IS NOT NULL;
UPDATE petty_cash_requests SET transferred_amount = released_amount WHERE (transferred_amount IS NULL OR transferred_amount = 0) AND released_amount IS NOT NULL;
UPDATE petty_cash_requests SET request_number = document_no WHERE (request_number IS NULL OR request_number = '') AND document_no IS NOT NULL AND document_no != '';
UPDATE petty_cash_requests SET request_number = 'PCR-LEGACY-' || id WHERE request_number IS NULL OR request_number = '';
UPDATE petty_cash_requests SET created_by = prepared_by WHERE (created_by IS NULL OR created_by = '') AND prepared_by IS NOT NULL;
UPDATE petty_cash_requests SET modified_at = created_at WHERE modified_at IS NULL AND created_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS petty_cash_transfers(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    transfer_date TEXT,
    amount REAL DEFAULT 0,
    bank_name TEXT,
    account_number TEXT,
    utr_number TEXT,
    reference_number TEXT,
    payment_mode TEXT,
    remarks TEXT,
    created_by TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS petty_cash_expenses(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    expense_category TEXT,
    description TEXT,
    vendor TEXT,
    bill_number TEXT,
    amount REAL DEFAULT 0,
    staff_id INTEGER,
    staff_name TEXT,
    employee_code TEXT,
    created_by TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS petty_cash_attachments(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER,
    expense_id INTEGER,
    file_name TEXT,
    file_path TEXT,
    uploaded_by TEXT,
    uploaded_at TEXT
);
