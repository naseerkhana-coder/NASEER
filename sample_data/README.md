# MAXEK ERP — Sample Migration Dataset (v1.1)

Standard Excel templates for bulk import development, automated tests, staging UAT, demos, and customer onboarding.

Regenerate all files:

```bash
python scripts/build_sample_data_templates.py
```

## Required files

| File | Sprint | Maps to import module | Notes |
|------|--------|----------------------|-------|
| `BOQ.xlsx` | 2 | `boq` | Columns match `boq_import_service.BOQ_IMPORT_COLUMNS` |
| `WBS_Template.xlsx` | 2 | `wbs` (planned) | Standard WBS library — Sprint 2 |
| `Labour_Master.xlsx` | 2 | `labour` (planned) | Labour library — Sprint 2 |
| `Machinery_Master.xlsx` | 2 | `machinery` (planned) | Machinery library — Sprint 2 |
| `Material_Master.xlsx` | 2 | `materials` | Columns match materials bulk validator |
| `Productivity.xlsx` | 2 | `productivity` (planned) | Productivity library — Sprint 2 |
| `Rate_Master.xlsx` | 2 | `rates` (planned) | Rate library — Sprint 2 |
| `Customer_Master.xlsx` | 3 | `customers` | Columns match `accounts_import_service` |
| `Vendor_Master.xlsx` | 3 | `vendors` | Columns match `accounts_import_service` |
| `Employee_Master.xlsx` | 3 | `employees` | Validate-only until Sprint 3 save |
| `COA.xlsx` | 3 | `coa` | Chart of accounts template |
| `Opening_Balance.xlsx` | 3 | `opening_balances` | Opening balance entries |

## Usage

1. Copy templates and fill with tenant-specific data (keep header row unchanged).
2. Upload via **Settings → Data Import** (`/data-import`) or module-specific Import toolbar.
3. Always **Validate & Preview** before **Save Import**.
4. Review **Import Audit Log** (`/data-import/audit-log`); use **Rollback** when supported.

## Column rules

- Header row is required; column names are normalized (case/spacing insensitive).
- Dates: `YYYY-MM-DD` or `DD-MM-YYYY`.
- GSTIN: 15-character format; PAN: `AAAAA9999A`.
- Duplicate codes within a file are rejected before save.

See `docs/V1_1_BULK_IMPORT_SPEC.md` for the full Sprint 1–4 plan.
