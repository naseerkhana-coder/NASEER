-- Fix incomplete dpr_measurements schema on VPS (safe to re-run; ignore duplicate column errors).
ALTER TABLE dpr_measurements ADD COLUMN project_id INTEGER;
ALTER TABLE dpr_measurements ADD COLUMN report_date TEXT;
ALTER TABLE dpr_measurements ADD COLUMN boq_item_id INTEGER;
ALTER TABLE dpr_measurements ADD COLUMN boq_number TEXT;
ALTER TABLE dpr_measurements ADD COLUMN boq_description TEXT;
ALTER TABLE dpr_measurements ADD COLUMN unit TEXT;
ALTER TABLE dpr_measurements ADD COLUMN calculated_quantity REAL DEFAULT 0;
ALTER TABLE dpr_measurements ADD COLUMN measurement_type TEXT;
ALTER TABLE dpr_measurements ADD COLUMN bill_client INTEGER DEFAULT 0;
ALTER TABLE dpr_measurements ADD COLUMN for_costing INTEGER DEFAULT 0;
ALTER TABLE dpr_measurements ADD COLUMN billing_status TEXT DEFAULT 'none';
ALTER TABLE dpr_measurements ADD COLUMN costing_status TEXT DEFAULT 'none';
ALTER TABLE dpr_measurements ADD COLUMN measurement_data TEXT;
ALTER TABLE dpr_measurements ADD COLUMN created_by TEXT;
ALTER TABLE dpr_measurements ADD COLUMN approval_status TEXT DEFAULT 'Pending Checker';
ALTER TABLE dpr_measurements ADD COLUMN created_at TEXT;
ALTER TABLE dpr_measurements ADD COLUMN work_description TEXT;
