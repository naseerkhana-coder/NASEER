# Phase 2 — Module Validation

**Project:** MAXEK Construction ERP  
**Audit date:** 2026-06-20  
**Phase 1 reference:** [FRAMEWORK.md](./FRAMEWORK.md) (`erp_standard_toolbar`, `module_page_context`, `/reports/run`)  
**Governance:** [MAXEK_ERP_RULES.md](./MAXEK_ERP_RULES.md) · [MODULE_DEFINITION_OF_DONE.md](./MODULE_DEFINITION_OF_DONE.md)  
**Tasks:** [PHASE2_CURSOR_TASKS.md](./PHASE2_CURSOR_TASKS.md)

Phase 2 validates each department module against the Phase 1 shared framework. A module is **not complete** until all 20 Definition of Done items pass in the browser.

---

## Key findings

1. **All 14 modules exist** — routes, templates, and backend code are present. **0 missing.**
2. **Most modules are ⚠️ Partial** — framework alignment, nav visibility, and report wiring gaps remain.
3. **Project Management is the reference** — `/projects` uses `erp_standard_toolbar`, `module_page_context`, server Excel export, and workflow modals (Phase 1).
4. **Legacy adoption** — ~9 screens still use `erp_module_toolbar`; most others use `page_actions` + legacy `erp-table-toolbar`.
5. **Nav gaps** — Subcontract and Plant are hidden from the main toolbar; several orphan routes (Client Billing, Leave, Photos, Corporate DMS) lack sidebar entries.
6. **14-module gap audit** — see [MODULE_GAP_AUDIT_14.md](./MODULE_GAP_AUDIT_14.md) for menu/screen/database status.

---

## Master checklist (14 modules)

| # | Module | Exists | Overall | Toolbar | CRUD | Navigation | Reports |
|---|--------|--------|---------|---------|------|------------|---------|
| 1 | Project Management | ✅ | ⚠️ Partial | ⚠️ | ⚠️ | ✅ | ⚠️ |
| 2 | Planning & WBS | ✅ | ⚠️ Partial | ⚠️ | ✅ | ✅ | ✅ |
| 3 | BOQ | ✅ | ⚠️ Partial | ⚠️ | ✅ | ✅ | ⚠️ |
| 4 | DPR | ✅ | ⚠️ Partial | ⚠️ | ✅ | ✅ | ⚠️ |
| 5 | Procurement | ✅ | ⚠️ Partial | ⚠️ | ✅ | ✅ | ⚠️ |
| 6 | Store & Inventory | ✅ | ⚠️ Partial | ⚠️ | ✅ | ✅ | ⚠️ |
| 7 | Work Order | ✅ | ⚠️ Partial | ⚠️ | ✅ | ⚠️ | ⚠️ |
| 8 | Subcontract | ✅ | ⚠️ Partial | ⚠️ | ✅ | ⚠️ | ⚠️ |
| 9 | QA / QC | ✅ | ⚠️ Partial | ⚠️ | ✅ | ✅ | ⚠️ |
| 10 | Plant & Fleet | ✅ | ⚠️ Partial | ⚠️ | ✅ | ⚠️ | ⚠️ |
| 11 | HR & Payroll | ✅ | ⚠️ Partial | ⚠️ | ✅ | ✅ | ⚠️ |
| 12 | Finance & Accounts | ✅ | ⚠️ Partial | ⚠️ | ✅ | ✅ | ⚠️ |
| 13 | Administration | ✅ | ⚠️ Partial | ⚠️ | ✅ | ✅ | ⚠️ |
| 14 | Reports | ✅ | ⚠️ Partial | ⚠️ | N/A | ✅ | ⚠️ |

**Counts:** ✅ Working 0 (full DoD) · ⚠️ Partial 14 · ❌ Missing 0

---

## Framework reference

| Layer | Location | Phase 2 expectation |
|-------|----------|---------------------|
| Standard toolbar | `templates/macros/erp_ui.html` → `erp_standard_toolbar` | New, Open, View, Edit, Delete, Search, Status, Date, Sort, Refresh, Export Excel/PDF, Print |
| Legacy toolbar | `erp_module_toolbar` | Migrate to `erp_standard_toolbar` per [FRAMEWORK.md](./FRAMEWORK.md) |
| Python helpers | `erp_framework.py` | `ModuleConfig`, `module_page_context`, `parse_crud_request`, `apply_list_filters`, `export_rows_to_excel` |
| Client JS | `static/js/erp-framework.js` | Row selection, toolbar CRUD, client filters |
| Nav / shell | `ui_shell_config.py`, `base_maxek.html` | Dashboard → Dept hub → Module list → View/Edit |
| Reports | `report_registry.py`, `/reports/run` | Wired reports via `erp_report_runner` |

**Reference module:** `/projects` — see [FRAMEWORK.md § Reference module: Projects](./FRAMEWORK.md#reference-module-projects).

---

## Recommended fix order

1. **Project Management** — close remaining toolbar gaps (Delete with workflow guard, server search, status filter); validate all 20 DoD items
2. **BOQ + DPR** — migrate to `erp_standard_toolbar`; wire export/print
3. **Procurement** — PO, GRN toolbar parity; RFQ / quotation comparison (routes or document embedded flow)
4. **Subcontract + Work Order** — restore main-toolbar access; align WO naming with `/subcontract-payments`
5. **Store & Inventory** — GRN, issue, transfer toolbar parity
6. **HR & Payroll** — leave, timesheets, salary screens
7. **Finance & Accounts** — voucher list screens (large surface)
8. **Plant & Fleet** — fix virtual toolbar ↔ route mapping; sidebar for `/plant`, `/fleet`
9. **QA / QC** — NCR/cube registers vs nav labels; standard toolbar on QC master
10. **Administration** — Corporate DMS nav; office registers
11. **Reports** — wire stubs in corporate hub; expand or deprecate legacy `/reports`
12. **Orphan modules** — Client Billing, Project Photos, Leave — add `NAV_GROUPS` entries

---

## Per-module validation

### 1. Project Management — ⚠️ Partial (reference)

| Area | Routes / templates | Status |
|------|-------------------|--------|
| Dept hub | `/projects/dashboard` | ✅ |
| Project CRUD | `/projects` → `projects.html` | ⚠️ |
| Clients | `/clients` → `clients.html` | ⚠️ |
| Documents | embedded on project form; `/project-documents` | ⚠️ |
| Photos | `/project-photos` | ⚠️ orphan nav |
| Client billing | `/client-billing` | ⚠️ orphan nav |
| Securities | `/securities-guarantees` | ⚠️ orphan nav |

**Toolbar (`/projects`):** Uses `erp_standard_toolbar` (Phase 1). Remaining gaps:

| Control | Status | Notes |
|---------|--------|-------|
| New | ✅ | `#add-project` |
| Open | ⚠️ | Project 360 hub modal, not toolbar Open |
| View / Edit | ⚠️ | Row-level; workflow-gated |
| Delete | ❌ | No delete handler; toolbar Delete not wired |
| Search | ⚠️ | Client-side; needs server `q` param |
| Status / Date / Sort / Refresh | ⚠️ | Partial via standard toolbar; verify end-to-end |
| Export Excel | ✅ | `/projects/export` (server) |
| Export PDF | ❌ | Not implemented |
| Print | ✅ | `print_target` on list |

**CRUD:** Create, view, edit, list work with workflow `project_creation`. **Delete not implemented.**

**Navigation:** ✅ Dashboard → Projects → list. Breadcrumbs via `module_page_context`.

**Reports:** ⚠️ Nav "Project Reports" → `/reports` (attendance/salary only). Corporate hub has project entries (mixed wired/stub).

**Phase 2 tasks:** See [PHASE2_CURSOR_TASKS.md § Project Management](./PHASE2_CURSOR_TASKS.md#1-project-management).

---

### 2. Planning & WBS — ⚠️ Partial

- **Routes:** `/cost-planning`, `/api/cost-planning/wbs/<project_id>`, WBS Report
- **Service:** `cost_planning_service.py`
- **Toolbar:** `page_actions` only — not `erp_standard_toolbar`
- **CRUD:** ✅ WBS tree, activities, materials, manpower, machinery
- **Navigation:** ✅ Projects → Planning
- **Reports:** ✅ WBS Report in cost planning
- **Gaps:** No standard status/date filters; WBS embedded tab, not standalone module screen

---

### 3. BOQ — ⚠️ Partial

- **Routes:** `/boq-management`, `/boq-multiple-entry`, `/boq-print/<id>`
- **Toolbar:** Legacy `erp-table-toolbar`; New in `page_actions`
- **CRUD:** ✅ Full + workflow + `delete_boq`
- **Navigation:** ✅ Projects → BOQ Management
- **Reports:** ⚠️ Print per BOQ; no list export via standard toolbar
- **Gaps:** Migrate to `erp_standard_toolbar`; wire Excel/PDF export

---

### 4. DPR — ⚠️ Partial

- **Routes:** `/dpr-entry`, pending/costing tabs, print on client-bill tab
- **CRUD:** ✅ Workflow on measurements
- **Navigation:** ✅ Projects → Progress Monitoring
- **Toolbar:** No standard module toolbar on main measurement list
- **Gaps:** Search/export toolbar; adopt `erp_standard_toolbar` on list view

---

### 5. Procurement — ⚠️ Partial

- **Routes:** `/material-request`, `/purchase-request`, `/purchase/orders`, `/store-receipt`
- **Framework:** MR + PR use `erp_module_toolbar`; PO/GRN use `page_actions` only
- **CRUD:** ✅ Full workflow on MR, PR, PO
- **Navigation:** ✅ Store & Procurement nav group
- **Gaps:** RFQ and Quotation Comparison in `STANDARD_SUB_LABELS` but no dedicated routes (quotations embedded in PO)

---

### 6. Store & Inventory — ⚠️ Partial

- **Routes:** `/store` hub, `/store-receipt`, `/store-issue`, `/material-transfer`, `/inventory`
- **CRUD:** ✅ GRN, issue, transfer with workflow
- **Navigation:** ✅ Virtual Store sub-toolbar
- **Gaps:** GRN/issue/transfer lack `erp_standard_toolbar`; inventory read-focused

---

### 7. Work Order — ⚠️ Partial

- **Primary:** `/subcontract-payments` — subcontract WOs + payments
- **Also:** Private project WO fields on `/projects` form
- **CRUD:** ✅ `subcontract_work_orders`, payment entries
- **Navigation:** ⚠️ Subcontract → Subcontract Payments only; no unified "Work Order" label
- **Gaps:** Not in main toolbar; naming inconsistent across screens

---

### 8. Subcontract — ⚠️ Partial

- **Routes:** `/subcontractors`, `/workers`, `/sub-billing`, `/subcontract-payments`, `/dept/subcontract`
- **CRUD:** ✅ Full subcontractor, worker, billing, payment flows
- **Navigation:** ⚠️ `subcontract-management` removed from main toolbar (`build_main_toolbar`); reachable via dept portal
- **Gaps:** Hidden from top toolbar; legacy toolbars on most screens

---

### 9. QA / QC — ⚠️ Partial

- **Routes:** `/qc-master`, `/quality-control`, `/plant/qc`
- **CRUD:** ✅ QC master CRUD; plant QC separate
- **Navigation:** ⚠️ QC in toolbar but site/plant QC split; no sidebar for orphans
- **Gaps:** NCR, cube register labels vs stubs; no standard toolbar

---

### 10. Plant & Fleet — ⚠️ Partial

- **Routes:** `/plant/*` (13+ sub-modules), `/fleet/*`
- **CRUD:** ✅ Production, dispatch, QC, costing, maintenance
- **Navigation:** ⚠️ Virtual `fleet-mechanical` + `plant-operations` toolbar; full surface via `/plant` hub only
- **Gaps:** Many sub-modules orphan from sidebar; virtual toolbar labels don't match all routes

---

### 11. HR & Payroll — ⚠️ Partial

- **Routes:** `/staff`, `/attendance`, `/payroll`, `/leave-request`, `/timesheet`, `/salary`
- **Framework:** staff, attendance, payroll use `erp_module_toolbar`
- **CRUD:** ✅ Employee, attendance, payroll; leave has workflow
- **Navigation:** ✅ Workforce nav; ⚠️ leave/timesheets orphan
- **Gaps:** Leave, timesheets, salary screens need `erp_standard_toolbar` migration

---

### 12. Finance & Accounts — ⚠️ Partial

- **Routes:** `/accounts/*`, `/treasury/*`, `/petty_cash`
- **CRUD:** ✅ Vouchers, GST, TDS, ledger, treasury (BG ✅ per gap audit)
- **Navigation:** ✅ Best sub-toolbar UX (Masters | Transactions | Books)
- **Gaps:** Individual voucher screens lack standard toolbar; treasury stubs (CSV import, email alerts)

---

### 13. Administration — ⚠️ Partial

- **Routes:** `/office-admin`, inward/outward, letters, agreements, `/settings/corporate-dms`
- **CRUD:** ✅ Office registers; Corporate DMS with folders/versions
- **Navigation:** ⚠️ `admin-compliance` slug; Corporate DMS not in Settings nav
- **Gaps:** Legacy forms; DMS discoverability

---

### 14. Reports — ⚠️ Partial

- **Routes:** `/reports/corporate` (hub), `/reports`, `/reports/workflow-audit`, module print routes
- **Navigation:** ✅ Corporate hub + per-module report links
- **Gaps:** Legacy `/reports` = attendance + salary only; many corporate hub entries stub; Run-from-hub not universal

---

## 14-module gap audit cross-reference

| # | Module (gap audit) | Menu | Working |
|---|-------------------|------|---------|
| 1 | Company Master | Settings button | ✅ |
| 2 | Project Documents | Embedded | ⚠️ |
| 3 | Project Photos | None | ⚠️ |
| 4 | WBS | Planning sub-feature | ✅ |
| 5 | Client Billing | None | ⚠️ |
| 6 | Salary Increment | Employees / payroll revisions | ⚠️ |
| 7 | Leave | None | ⚠️ |
| 8 | Work Orders | Subcontract Payments | ✅ |
| 9 | Rate Revision | Subcontractor + payroll | ⚠️ |
| 10 | Fleet | Office hub only | ⚠️ |
| 11 | Plant | None | ⚠️ |
| 12 | QC | None | ⚠️ |
| 13 | Documents (DMS) | None | ⚠️ |
| 14 | BG/Treasury | Accounts → Treasury | ✅ |

Full detail: [MODULE_GAP_AUDIT_14.md](./MODULE_GAP_AUDIT_14.md)

---

## Sign-off process

1. Fix module per [PHASE2_CURSOR_TASKS.md](./PHASE2_CURSOR_TASKS.md)
2. Run all 20 checks in [MODULE_DEFINITION_OF_DONE.md](./MODULE_DEFINITION_OF_DONE.md)
3. Record pass/fail in the module sign-off template (DoD doc)
4. Commit after each completed module task per [MAXEK_ERP_RULES.md](./MAXEK_ERP_RULES.md)
