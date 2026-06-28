# Bulk Data Import & Migration

Phased rollout for MAXEK ERP bulk import and tenant migration.

## Phase A — Core Framework (implemented)

| Component | Location |
|-----------|----------|
| Spreadsheet parser (xlsx/csv) | `bulk_import_service.py` |
| Import audit log | `import_audit_service.py` → `import_audit_log` table |
| Shared validators | duplicate, required, date, GST, PAN, account, unit, project refs |
| Error format | Row, Column, Error, Suggested Fix |
| Routes | `GET /api/bulk-import/<module>/template`, `POST .../validate`, `POST .../save` |

## Phase B — BOQ (implemented)

- **Standard BOQ Library** — `/boq-library` — fields: boq_code, item_number, description, detailed_specification, unit, category, sub_category, standard_rate
- **BOQ create** — pick from library or typical template on `boq.html`
- **BOQ Excel import** — toolbar Import on BOQ Management; template columns: Item No, BOQ Code, Description, Specification, Unit, Quantity, Rate, Amount, Remarks
- Row-by-row validation before save; creates one `boq_master` + lines with approval workflow

## Phase C — Migration Wizard (implemented)

- Route: `/erp-admin/customers/<id>/migration-wizard?step=1..6`
- Steps: Company Details, Admin User, Import Masters, Import Transactions, Validation, Finish
- BOQ and materials wired; other masters have template + validate; save returns Phase 2 where noted

## Phase D — Remaining modules (planned)

### Accounts opening

| Module | Template | Validate | Save |
|--------|----------|----------|------|
| Chart of Accounts (`coa`) | Yes | Yes | Phase 2 |
| Opening balances | Yes | Yes | Phase 2 |
| Bank accounts master | Yes | Yes | Phase 2 |

### Sales, Purchase, Payment imports

- Sales invoices / credit notes — Phase 2
- Purchase orders / GRN history — Phase 2
- Payment & receipt vouchers bulk — Phase 2

### Bank statement & reconciliation

- CSV/xlsx bank statement import — Phase 2 (see Treasury → Reconciliation stub)
- Auto-match rules and unreconciled report — Phase 2

### Master stubs (validate-only save)

- **Vendors** — template + validate; save Phase 2
- **Employees** — template + validate; save Phase 2
- **Materials** — full validate + save via existing `import_materials_excel`

## API usage

```http
GET  /api/bulk-import/boq/template
POST /api/bulk-import/boq/validate   (multipart: file, project_id)
POST /api/bulk-import/boq/save       (multipart: file or parsed_rows JSON, project_id)
```

## Audit

All successful BOQ imports write to `import_audit_log` with counts and filename.

## Testing

```bash
python -m pytest tests/test_bulk_import.py -v
```

## Deploy

Rebuild VPS patch after this feature (separate from Final Stabilization bundle):

```bash
python deploy/build_vps_patch_latest.py
```

See `deploy/dist/VPS-PATCH-LATEST-MANIFEST.txt` for file list.
