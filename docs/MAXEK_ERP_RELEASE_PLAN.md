# MAXEK ERP Release Plan

**Document owner:** MAXEK ERP product / engineering  
**Last updated:** 2026-06-28  
**Production URL:** https://erp.maxekindia.com

This plan defines the **production baseline**, **UAT gate**, and **sequenced releases** for bulk import and Phase 2 modules. Operational detail for the 28 Jun 2026 deploy lives in `deploy/DEPLOYMENT_APPROVAL_20260628.md` and `deploy/FINAL_STABILIZATION_BUNDLE_REPORT.md`.

---

## Release map (summary)

| Version | Status | Git anchor | Deploy artifact |
|---------|--------|------------|-----------------|
| **1.0** | Production baseline (deployed 28 Jun 2026) | `2e10ed5` (+ bundle `32788c9`, `a4ca636`) | `deploy/dist/vps-patch-latest.zip` (211 files) |
| **1.1** | Next approved release (bulk import — implemented scope only) | `45c3469` area | Separate VPS patch (rebuild after UAT) |
| **1.2** | Phase 2 import saves + treasury/reconciliation | TBD | After 1.1 stable |
| **2.0** | Future platform / UX enhancements | TBD | Roadmap |

---

## Version 1.0 — Production baseline

### What shipped

- **Deploy date:** 28 June 2026  
- **Git HEAD:** `2e10ed5a72ec334de41553d609049a273edda2a8` — *feat: improve user permission assignment UI with department matrix*  
- **Stabilization bundle commits:** `32788c9`, `a4ca636`, `2e10ed5` (standard toolbar, dashboard themes, permissions)  
- **Patch:** `deploy/dist/vps-patch-latest.zip`  
- **Manifest:** `deploy/dist/VPS-PATCH-LATEST-MANIFEST.txt` — **211** production files, **816,458** bytes  

### In scope (1.0)

- Final Stabilization: **standard list toolbar**, **per-tenant dashboard layout themes**, **department permission matrix**, Command Centre / department navigation, IST greeting, financial widgets on correct department dashboards  
- Full ERP modules already licensed on production (projects, BOQ, DPR, masters, accounts, workflow, reports, ERP Admin, etc.) as present in the baseline patch  

### Explicitly out of scope (1.0)

- **Bulk import / migration wizard** — not in `vps-patch-latest.zip` (see aborted/excluded commit note in deployment approval; work continues on branch at `45c3469` for 1.1)  

### Production baseline rollback

If post-deploy smoke or UAT fails on baseline **1.0**, **do not** layer 1.1 patches. Roll back using pre-deploy backups under `/var/backups/maxek-erp/` (application tar and optional `maxek.db` snapshot). Step-by-step commands: **`deploy/DEPLOYMENT_APPROVAL_20260628.md`** (Rollback) and **`deploy/FINAL_STABILIZATION_BUNDLE_REPORT.md`**.

---

## Production UAT (gate for 1.0 sign-off)

Complete browser UAT using **`docs/PRODUCTION_UAT_CHECKLIST.md`** (included in the VPS patch at `docs/PRODUCTION_UAT_CHECKLIST.md`). Record results in the deployment approval **Post-deployment log** and **Production baseline sign-off** tables.

Organize execution and sign-off by these **release-plan areas** (maps to checklist sections):

### Authentication & session (auth)

- Login with company code, valid/invalid credentials, session persistence, logout  
- Role-appropriate landing (Super Admin vs tenant users)  
- *Checklist:* §1 Login; parts of §7 Permissions by Role  

### Platform (Super Admin)

- Platform Command Centre, Customer Master, licensing and limits  
- Cross-tenant isolation; admin routes blocked for non–Super Admin  
- *Checklist:* §1.7–1.8, §2 navigation (licensed modules), §7.1–7.2, §7.8  

### Company ERP (operational modules)

- Licensed modules load; department hubs; maker → checker → approver on Projects, BOQ, DPR, Material Request, Expenses, Attendance  
- CRUD on masters; reports (global, accounts, cost planning, billing, payroll/treasury as licensed)  
- *Checklist:* §2 Navigation, §4 CRUD, §5 Workflow, §6 Reports  

### Standard toolbar

- New, View, Edit, Search, Filter, Refresh, Export, Reports on sample list modules (Projects, Clients, Vendor Master, Employee Master, Material Request, Accounts Expenses)  
- *Checklist:* §3 Standard Toolbar  

### Customer (tenant admin & branding)

- Customer Admin: tenant dashboard and modules per package; Customer Settings (logo + **dashboard theme** — delivered in baseline via `a4ca636`)  
- My Dashboard Preferences override  
- *Checklist:* §1.8, §2.6, §4.6, §7.3; deployment smoke items 5–6 in `DEPLOYMENT_APPROVAL_20260628.md`  

### Company (legal entity & settings)

- Company Master (legal name, GST, bank — no logo on company master)  
- Company Admin: Settings → Users, permission matrix save persists  
- *Checklist:* §2.4–2.5, §4.5, §7.4; deployment smoke item 7  

### UAT sign-off

- **Overall:** checklist §8 Sign-off  
- **Baseline tag:** HEAD `2e10ed5` — Final Stabilization patch — bulk import excluded  

---

## Change freeze (until UAT passes)

From **28 Jun 2026 production deploy** until **Production baseline sign-off** is recorded:

1. **No new production deploys** except hotfixes for **Severity 1** (service down, data loss, security) approved by technical lead.  
2. **No enabling** bulk import routes or migration wizard on production before **version 1.1** approval and a **separate** patch bundle.  
3. **Feature work** for 1.1+ may continue on git branches; production remains pinned to **`2e10ed5` / `vps-patch-latest`** until UAT pass and explicit go-ahead for the next bundle.  

---

## Version 1.1 — Bulk import (implemented scope)

**Target anchor:** `45c3469` — *feat: add bulk import and migration module (Phase A-D foundation + BOQ)* (and follow-up commits in the same feature line).

**Purpose:** Ship **working** bulk import and tenant migration for masters already implemented — **not** Phase 2 validate-only stubs.

### In scope for 1.1

| Area | Capability |
|------|------------|
| **Core framework** | `bulk_import_service.py`, validators, template / validate / save APIs, `import_audit_log` |
| **BOQ library** | Standard BOQ Library (`/boq-library`), pick-from-library on BOQ create |
| **BOQ import** | Excel import on BOQ Management; row validation; audit on successful import |
| **Materials** | Full validate + save (existing materials Excel path) |
| **Migration wizard** | `/erp-admin/customers/<id>/migration-wizard` steps 1–6 (company, admin, masters, transactions shell, validation, finish) with BOQ + materials wired |
| **Audit** | Import audit UI and `import_audit_service.py` |
| **Hub / settings entry points** | Data import hub and related templates as in feature branch |

**Reference:** `docs/BULK_IMPORT_MIGRATION.md`

### Out of scope for 1.1 (remains Phase 2 / 1.2)

- Vendor, employee **save** from bulk import (validate-only stubs)  
- Chart of accounts, opening balances, bank accounts master **save**  
- Sales, purchase, payment voucher bulk **save**  
- Bank statement import and reconciliation **save**  

### 1.1 deploy prerequisites

- 1.0 UAT **passed** and baseline signed off  
- Rebuild patch: `python deploy/build_vps_patch_latest.py` (separate from stabilization bundle)  
- Dedicated deployment approval + smoke (bulk import APIs, BOQ import, wizard, audit log)  
- `python -m pytest tests/test_bulk_import.py -v` green before deploy  

---

## Version 1.2 — Phase 2 imports

**Purpose:** Implement **save** paths and production hardening for modules that currently expose template + validate only.

### Planned modules (1.2)

| Module | 1.1 state | 1.2 deliverable |
|--------|-----------|-----------------|
| Vendors | Template + validate | Bulk save |
| Employees | Template + validate | Bulk save |
| Chart of accounts (COA) | Template + validate | Bulk save |
| Opening balances | Template + validate | Bulk save |
| Bank accounts master | Template + validate | Bulk save |
| Sales | Phase 2 | Invoices / credit notes import |
| Purchase | Phase 2 | PO / GRN history import |
| Payment | Phase 2 | Payment & receipt voucher bulk |
| Reconciliation | Phase 2 stub | Bank statement CSV/xlsx import, matching rules, unreconciled reporting |

Wizard steps that today return “Phase 2” on save should be wired as each module completes.

---

## Version 2.0 — Future roadmap

Planned **major** themes (non-exhaustive):

- Deeper analytics and executive dashboards  
- Extended treasury automation beyond 1.2 reconciliation  
- Mobile / field workflows  
- Integration APIs and webhooks for third-party systems  
- Additional toolbar coverage on remaining list modules (see backlog in `FINAL_STABILIZATION_BUNDLE_REPORT.md`)  

### Enhancements already in 1.0 baseline (not waiting for 2.0)

Per commit **`a4ca636`** (*feat: add per-tenant dashboard layout theme system*), **Dashboard Themes** and **My Dashboard Preferences** are **already production features in version 1.0**. Version 2.0 may extend theming (new presets, widget packs, admin defaults) but must not be documented as “new in 2.0” only — that would contradict the stabilization deploy.

---

## Related documents

| Document | Use |
|----------|-----|
| `deploy/DEPLOYMENT_APPROVAL_20260628.md` | 1.0 deploy runbook, smoke, rollback, sign-off |
| `docs/PRODUCTION_UAT_CHECKLIST.md` | Full UAT test cases |
| `docs/BULK_IMPORT_MIGRATION.md` | 1.1 vs Phase 2 module matrix |
| `deploy/FINAL_STABILIZATION_BUNDLE_REPORT.md` | 1.0 file groups and toolbar backlog |

---

## Revision history

| Date | Change |
|------|--------|
| 2026-06-28 | Initial release plan v1.0–v2.0; aligned with stabilization deploy and bulk import branch |
