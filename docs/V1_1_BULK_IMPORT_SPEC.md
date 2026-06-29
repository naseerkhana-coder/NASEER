# MAXEK ERP v1.1 — Bulk Import & Migration Specification

**Branch:** `release/v1.1`  
**Production baseline:** `main` @ `v1.0.2` (frozen — emergency Critical hotfixes only)  
**Depends on:** `sample_data/` Excel templates for dev, UAT, and demos  
**Feeds:** v1.2 Planning & Costing libraries (frozen spec on `release/v1.2-planning`)

---

## Objective

Deliver a tenant-facing **Bulk Import & Migration** platform so new customers can load master data and opening transactions before go-live. Sprint 1 establishes the core engine; Sprints 2–3 add module saves; Sprint 4 validates and deploys.

---

## Sprint plan

### Sprint 1 — Core Import Engine ✅ (this release)

| Component | Status | Location |
|-----------|--------|----------|
| Import module registry | Done | `data_import_registry.py` |
| UI routes (hub, module, wizard, audit) | Done | `data_import_routes.py`, `templates/data_import/` |
| Spreadsheet parse (xlsx/csv) | Done | `bulk_import_service.py` |
| Shared validators | Done | `bulk_import_service.py` |
| Error report (Row, Column, Error, Suggested Fix) | Done | validation + module templates |
| Import audit log | Done | `import_audit_service.py` → `import_audit_log` |
| Rollback (minimal viable) | Done | `rollback_import()` — customers, vendors, BOQ |
| REST API (template / validate / save) | Done | `bulk_import_routes.py` |
| Sample dataset | Done | `sample_data/` + `scripts/build_sample_data_templates.py` |

**Sprint 1 modules with validate + save:** BOQ, customers, vendors, materials (via store import).

### Sprint 2 — Master Data Imports

Import and maintain standard libraries required by v1.2:

| Module | Sample file | Target |
|--------|-------------|--------|
| BOQ Library | `BOQ.xlsx` (line items) + library UI | `standard_boq_library` |
| Standard WBS Library | `WBS_Template.xlsx` | WBS library tables (new) |
| Labour Library | `Labour_Master.xlsx` | Labour rate library |
| Machinery Library | `Machinery_Master.xlsx` | Equipment library |
| Material Library | `Material_Master.xlsx` | `materials` master |
| Productivity Library | `Productivity.xlsx` | Productivity assumptions |
| Rate Library | `Rate_Master.xlsx` | Composite rate analysis |

Each module: template download → validate → preview errors → save → audit log → rollback payload.

### Sprint 3 — Business Data Imports

| Module | Sample file | Notes |
|--------|-------------|-------|
| Customers | `Customer_Master.xlsx` | ✅ Sprint 1 |
| Vendors | `Vendor_Master.xlsx` | ✅ Sprint 1 |
| Employees | `Employee_Master.xlsx` | Validate in Sprint 1; save in Sprint 3 |
| Chart of Accounts | `COA.xlsx` | Validate in Sprint 1; save in Sprint 3 |
| Opening Balances | `Opening_Balance.xlsx` | Sprint 3 |
| Companies / Projects | TBD | Sprint 3 |

### Sprint 4 — Final Validation & Release

1. Staging deploy from `release/v1.1`
2. Full migration wizard UAT (6 steps)
3. Performance test large files (10k+ rows per module)
4. Import audit + rollback spot checks
5. Customer UAT sign-off
6. Production deploy (separate bundle — do **not** merge to `main` until approved)
7. Tag `v1.1.0` on `release/v1.1` after production promotion

---

## Architecture

```text
sample_data/*.xlsx
        ↓
bulk_import_service.parse_upload + validators
        ↓
module service (boq_import_service, accounts_import_service, …)
        ↓
import_audit_service.log_import (+ rollback_payload)
        ↓
/data-import hub + /api/bulk-import/* API
```

### UI entry points

| Route | Purpose |
|-------|---------|
| `/data-import` | Import hub — all modules by category |
| `/data-import/<module_key>` | Upload, validate, save |
| `/data-import/audit-log` | Audit history + rollback |
| `/data-import/migration-wizard` | 6-step customer migration |
| `/api/bulk-import/<module>/template` | Download template |
| `/api/bulk-import/<module>/validate` | POST multipart validate |
| `/api/bulk-import/<module>/save` | POST save |
| `/api/bulk-import/audit/<id>/rollback` | POST undo import |

### Error format

Every validation failure returns:

| Field | Example |
|-------|---------|
| row | `5` (Excel row) |
| column | `GST Number` |
| error | `Invalid GSTIN: ABC` |
| suggested_fix | `Enter a valid 15-character GSTIN.` |

### Rollback rules (Sprint 1)

- Recorded only when save succeeds and inserts are tracked.
- Supported: `customers`, `vendors`, `boq`.
- Marks audit row `status=rolled_back`; does not re-import automatically.
- Sprint 2+ modules will extend payload schema.

---

## Sample data

See `sample_data/README.md`. Regenerate templates:

```bash
python scripts/build_sample_data_templates.py
```

---

## Testing

```bash
python -m pytest tests/test_bulk_import.py -v
```

Manual:

1. Start app: `python app.py` (or gunicorn locally)
2. Login → `/data-import`
3. Import `sample_data/Customer_Master.xlsx` via Customers module — validate then save
4. Open audit log → Rollback → confirm client removed

---

## Out of scope for v1.1

Do **not** implement on `release/v1.1`:

- Planning & Costing screens (v1.2)
- Cost Engine / WBS execution / Project Cost Control
- Phase 2 transaction imports (sales, purchase, payments) beyond templates

---

## Git policy

- All v1.1 work on **`release/v1.1`** only
- **Never merge to `main`** until v1.1 staging + customer UAT complete
- `release/v1.2-planning` remains specification-only until v1.1 ships

---

## Related docs

- `docs/BULK_IMPORT_MIGRATION.md` — Phase A–D history from initial foundation
- `docs/MAXEK_ERP_RELEASE_PLAN.md` — version roadmap
