-- Run on VPS if worker save still fails after app.py update:
-- sqlite3 /var/www/maxek-erp-flask/database/maxek.db < deploy/fix_workers_db.sql

ALTER TABLE workers ADD COLUMN worker_code TEXT;
ALTER TABLE workers ADD COLUMN aadhaar_number TEXT;
ALTER TABLE workers ADD COLUMN worker_category TEXT DEFAULT 'Company Staff';
ALTER TABLE workers ADD COLUMN subcontractor_id INTEGER;
ALTER TABLE workers ADD COLUMN pan_number TEXT;
ALTER TABLE workers ADD COLUMN id_proof TEXT;
ALTER TABLE workers ADD COLUMN aadhaar_document TEXT;
ALTER TABLE workers ADD COLUMN pan_document TEXT;
ALTER TABLE workers ADD COLUMN bank_account TEXT;
ALTER TABLE workers ADD COLUMN bank_name TEXT;
ALTER TABLE workers ADD COLUMN ifsc_code TEXT;
ALTER TABLE workers ADD COLUMN branch_name TEXT;
