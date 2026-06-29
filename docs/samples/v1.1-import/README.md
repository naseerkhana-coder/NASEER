# v1.1 migration sample pack (reference filenames)

Place **anonymized** Excel (`.xlsx`) or CSV files in this folder for staging UAT. Filenames below are the **canonical order** matching `docs/V1_1_BULK_IMPORT_SPEC.md`. Do not commit production customer data to git.

## Phase 1 — Commercial baseline

| File | Contents |
|------|----------|
| `01_boq_standard_library.xlsx` | Reusable BOQ catalogue rows (code, description, unit, category, standard rate) |
| `02_boq_project_lines.xlsx` | Project BOQ import (item no, code, qty, rate, amount, project key) |
| `03_wbs_template_nodes.xlsx` | WBS template tree (node code, parent, description, level, project type) |

## Phase 2 — Libraries

| File | Contents |
|------|----------|
| `04_labour_library.xlsx` | Trades, hours per unit, crew codes |
| `05_machinery_library.xlsx` | Equipment types, hours per unit |
| `06_material_master.xlsx` | Material code, name, unit, category |
| `07_productivity_norms.xlsx` | Activity ↔ output norms |
| `08_rate_schedule.xlsx` | Effective-dated rates (resource type, code, rate, UOM, from/to dates) |

## Phase 3 — Party masters

| File | Contents |
|------|----------|
| `09_customer_master.xlsx` | Customer / client records |
| `10_vendor_master.xlsx` | Vendor / supplier records |
| `11_employee_master.xlsx` | Employee HR master |

## Phase 4 — Accounts opening

| File | Contents |
|------|----------|
| `12_chart_of_accounts.xlsx` | Ledger hierarchy (code, name, group, parent) |
| `13_opening_balances.xlsx` | Opening balance lines (ledger, debit, credit, as-on date) |

## Phase 5 — Validation artifacts (generated, not hand-authored)

| Artifact | Description |
|----------|-------------|
| `validation_report_<run_id>.json` | Machine-readable errors from validate APIs |
| `import_audit_export_<run_id>.csv` | Export of `import_audit_log` after successful saves |

## Obtaining files

1. Export from a **sanitized** staging tenant after manual master setup, or  
2. Build from API templates: `GET /api/bulk-import/<module>/template` (when available per module).

Add files to this directory locally or in secure storage; only this README is required in the repository until real samples are approved for check-in.
