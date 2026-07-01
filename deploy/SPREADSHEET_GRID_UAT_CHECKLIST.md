# Spreadsheet grid UAT — required before production merge

**Feature branch:** `feature/spreadsheet-grid`  
**Do not merge to `release/v1.1` until every item below passes on staging.**

## Modules to test

| Module | Route / entry | Focus |
|--------|----------------|-------|
| BOQ | BOQ management → line items | Add/remove rows, qty × rate, keyboard nav |
| DPR | DPR entry | Measurement sub-grids, save draft/submit |
| Daily Timesheet | Timesheet / attendance daily | Single + bulk subcontractor checklist |
| Employee Timesheet | Monthly timesheet form | 31-day grid entry |
| Payroll | Payroll run lines | Inline edit panels |
| Store GRN | Store receipt | Multi-line material rows |
| Material Transfer | Material transfer | Line-item table |
| Client Billing | Client billing form | Measurement, RA, extra lines |

## Verification (each module)

- [ ] **Existing data unchanged** — open saved records; values match pre-deploy.
- [ ] **Save** — create/edit and save; record persists correctly.
- [ ] **Update** — edit approved/rejected records where allowed; changes persist.
- [ ] **Delete** — remove line/record where allowed; no orphan data.
- [ ] **No backend regressions** — no new 500 errors; no unexpected POST shape changes.
- [ ] **No database changes** — no migration required for this feature.
- [ ] **No JavaScript errors** — browser devtools console clean during full flow.
- [ ] **Scroll position** — after save/add/delete, grid does not jump to top.
- [ ] **Focus** — Tab/Enter moves between cells; cursor not lost after row actions.

## Sign-off

| Role | Name | Date | Pass |
|------|------|------|------|
| Maker / UAT | | | |
| Technical | | | |

After sign-off: merge `feature/spreadsheet-grid` → `release/v1.1`, build VPS patch including spreadsheet files, deploy to production.
