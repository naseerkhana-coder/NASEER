# MAXEK ERP Release Plan

**Document owner:** MAXEK ERP product / engineering  
**Last updated:** 2026-06-28  
**Production URL:** https://erp.maxekindia.com

This plan defines the **production baseline**, **maintenance release (v1.0.1)**, **UAT gate**, **Git tagging**, and **sequenced feature releases** for bulk import and Phase 2 modules. Operational detail for the 28 Jun 2026 deploy lives in `deploy/DEPLOYMENT_APPROVAL_20260628.md` and `deploy/FINAL_STABILIZATION_BUNDLE_REPORT.md`.

---

## Release map (summary)

| Version | Status | Git anchor | Deploy artifact |
|---------|--------|------------|-----------------|
| **v1.0.0** | Production baseline (deployed 28 Jun 2026) | Tag **`v1.0.0`** on `2e10ed5` (+ bundle `32788c9`, `a4ca636`) | `deploy/dist/vps-patch-latest.zip` (**211** files) — **rollback baseline** |
| **v1.0.1** | Conditional (UAT only) | Patch commits on baseline branch | Same bundle path, incremental hotfix patch after approval |
| **v1.1** | Next approved feature release (bulk import — implemented scope only) | `45c3469` area | Separate VPS patch (rebuild after staging UAT) |
| **v1.2** | Phase 2 import saves + treasury/reconciliation | TBD | After 1.1 stable |
| **v2.0** | Future platform / UX enhancements | TBD | Roadmap |

---

## Release policy (mandatory workflow)

Every release — baseline, maintenance (v1.0.1), or feature (v1.1+) — must follow this sequence. **No release may bypass this workflow.**

```text
Development
    ↓
Internal Testing
    ↓
Staging
    ↓
UAT
    ↓
Production
    ↓
Git Tag
    ↓
Rollback Point
```

Record approvals in the deployment approval doc and UAT checklist sign-off tables for each environment transition.

---

## v1.0.0 — Production baseline

**Version:** `v1.0.0`  
**Baseline commit:** `2e10ed5a72ec334de41553d609049a273edda2a8` — *feat: improve user permission assignment UI with department matrix*  
**Deployment date:** 28 June 2026  
**Deployment bundle:** `deploy/dist/vps-patch-latest.zip` — **211** production files (**816,458** bytes per manifest)

This is the **rollback baseline**. If a later release fails, restore production to **`v1.0.0` / `2e10ed5`** using pre-deploy backups under `/var/backups/maxek-erp/` (application tar and optional `maxek.db` snapshot). Step-by-step commands: **`deploy/DEPLOYMENT_APPROVAL_20260628.md`** (Rollback) and **`deploy/FINAL_STABILIZATION_BUNDLE_REPORT.md`**.

### What shipped

- **Stabilization bundle commits:** `32788c9`, `a4ca636`, `2e10ed5` (standard toolbar, dashboard themes, permissions)  
- **Manifest:** `deploy/dist/VPS-PATCH-LATEST-MANIFEST.txt`  

### In scope (v1.0.0)

- Final Stabilization: **standard list toolbar**, **per-tenant dashboard layout themes**, **department permission matrix**, Command Centre / department navigation, IST greeting, financial widgets on correct department dashboards  
- Full ERP modules already licensed on production (projects, BOQ, DPR, masters, accounts, workflow, reports, ERP Admin, etc.) as present in the baseline patch  

### Explicitly out of scope (v1.0.0)

- **Bulk import / migration wizard** — not in `vps-patch-latest.zip` (work continues on branch at `45c3469` for **v1.1**)  

---

## v1.0.1 — Maintenance release

**Purpose:** Production stabilization only. Fixes defects found during production UAT that block sign-off — not a feature release.

### In scope

- Critical production bugs  
- High-priority workflow failures  
- Broken CRUD operations  
- Permission and security fixes  
- 500/502 errors  
- Data integrity fixes  
- Schema or database changes **only when strictly required** to fix a verified production defect  

**Examples (illustrative UAT findings):**

| Severity | Example |
|----------|---------|
| Critical | BOQ save failure (500 on `/boq/create` or BOQ management save) |
| High | Customer Master delete failure for Super Admin (`/erp-admin/customers`) |
| — | Login failures |
| — | Workflow approval failures |
| — | Permission enforcement bugs |

### Out of scope

Do **not** include in v1.0.1:

- New modules  
- Dashboard redesign  
- Bulk Import & Migration  
- UI improvements and cosmetic polish  
- Feature requests  
- Medium / Low UAT items (defer until after v1.0 sign-off or a later release)  
- Database redesign  
- New APIs unless required for a production bug fix  

While v1.0.1 is active, **no new production deploys** except approved v1.0.1 hotfixes. **Severity 1** (service down, data loss, security) may proceed with technical-lead approval. Feature work for v1.1+ continues on branches; production stays pinned to the signed-off baseline until explicit go-ahead for the next bundle.

---

## UAT gate (v1.0.0 sign-off and v1.0.1 trigger)

Complete browser UAT using **`docs/PRODUCTION_UAT_CHECKLIST.md`** (included in the VPS patch). Record results in the deployment approval **Post-deployment log** and **Production baseline sign-off** tables.

**v1.0.1 is created only if Critical or High issues are found during production UAT.**

If UAT passes **without** Critical or High issues:

- **No v1.0.1 release is required.**  
- Proceed directly to Git tagging and v1.1 planning (below).

Classify every finding as Critical, High, Medium, or Low. Only Critical and High may drive v1.0.1 scope under the maintenance rules above.

### UAT focus areas (maps to checklist)

Organize execution and sign-off by these **release-plan areas**:

#### Authentication & session (auth)

- Login with company code, valid/invalid credentials, session persistence, logout  
- Role-appropriate landing (Super Admin vs tenant users)  
- *Checklist:* §1 Login; parts of §7 Permissions by Role  

#### Platform (Super Admin)

- Platform Command Centre, Customer Master, licensing and limits  
- Cross-tenant isolation; admin routes blocked for non–Super Admin  
- *Checklist:* §1.7–1.8, §2 navigation (licensed modules), §7.1–7.2, §7.8  

#### Company ERP (operational modules)

- Licensed modules load; department hubs; maker → checker → approver on Projects, BOQ, DPR, Material Request, Expenses, Attendance  
- CRUD on masters; reports (global, accounts, cost planning, billing, payroll/treasury as licensed)  
- *Checklist:* §2 Navigation, §4 CRUD, §5 Workflow, §6 Reports  

#### Standard toolbar

- New, View, Edit, Search, Filter, Refresh, Export, Reports on sample list modules (Projects, Clients, Vendor Master, Employee Master, Material Request, Accounts Expenses)  
- *Checklist:* §3 Standard Toolbar  

#### Customer (tenant admin & branding)

- Customer Admin: tenant dashboard and modules per package; Customer Settings (logo + **dashboard theme** — delivered in baseline via `a4ca636`)  
- My Dashboard Preferences override  
- *Checklist:* §1.8, §2.6, §4.6, §7.3; deployment smoke items 5–6 in `DEPLOYMENT_APPROVAL_20260628.md`  

#### Company (legal entity & settings)

- Company Master (legal name, GST, bank — no logo on company master)  
- Company Admin: Settings → Users, permission matrix save persists  
- *Checklist:* §2.4–2.5, §4.5, §7.4; deployment smoke item 7  

### UAT sign-off

- **Overall:** checklist §8 Sign-off  
- **Baseline reference:** commit `2e10ed5` — Final Stabilization patch — bulk import excluded  


## Change freeze policy (during v1.0 UAT)

- No new features
- No UI redesign
- No database schema changes (except emergency production fixes for verified defects)
- Only approved v1.0.1 maintenance fixes

---

## Git tagging and post–sign-off sequencing

**After successful production UAT** (and any required **v1.0.1** fixes deployed and re-verified):

1. **Create Git tag `v1.0.0`** on commit **`2e10ed5`** (production baseline).  
2. **Create a release branch for v1.1** (feature work isolated from production hotfixes).  
3. **Merge only approved Bulk Import work** (commit **`45c3469`** and follow-ups in that feature line).  
4. **Run separate staging UAT** for bulk import (APIs, BOQ import, wizard, audit log).  
5. **Deploy v1.1 to production only after approval** — separate patch bundle; do not mix with the v1.0.0 stabilization zip.  

Until **`v1.0.0`** is tagged, treat **`2e10ed5` / `vps-patch-latest`** as the effective rollback point even if the tag is not yet pushed.

---

## Version 1.1 — Bulk import (implemented scope)

**Target anchor:** `45c3469` — *feat: add bulk import and migration module (Phase A-D foundation + BOQ)* (and follow-up commits in the same feature line).

**Purpose:** Ship **working** bulk import and tenant migration for masters already implemented — **not** Phase 2 validate-only stubs.

**Prerequisites:** v1.0.0 UAT **passed**, tag **`v1.0.0`** on `2e10ed5`, and baseline signed off. **Do not** enable bulk import on production before v1.1 approval.

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

- v1.0.0 tagged and UAT signed off  
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

### Enhancements already in v1.0.0 baseline (not waiting for 2.0)

Per commit **`a4ca636`** (*feat: add per-tenant dashboard layout theme system*), **Dashboard Themes** and **My Dashboard Preferences** are **already production features in version 1.0.0**. Version 2.0 may extend theming (new presets, widget packs, admin defaults) but must not be documented as “new in 2.0” only — that would contradict the stabilization deploy.

---

## Related documents

| Document | Use |
|----------|-----|
| `deploy/DEPLOYMENT_APPROVAL_20260628.md` | v1.0.0 deploy runbook, smoke, rollback, sign-off |
| `docs/PRODUCTION_UAT_CHECKLIST.md` | Full UAT test cases |
| `docs/BULK_IMPORT_MIGRATION.md` | 1.1 vs Phase 2 module matrix |
| `deploy/FINAL_STABILIZATION_BUNDLE_REPORT.md` | v1.0.0 file groups and toolbar backlog |

---

## Revision history

| Date | Change |
|------|--------|
| 2026-06-28 | Initial release plan v1.0–v2.0; aligned with stabilization deploy and bulk import branch |
| 2026-06-28 | v1.0.0 baseline naming, v1.0.1 maintenance scope, UAT gate, Git tagging policy, mandatory release workflow |
