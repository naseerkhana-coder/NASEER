# MAXEK ERP v1.1 — Bulk Import & Migration Specification

**Status:** SPEC ONLY (no implementation in this document)  
**Branch:** `release/v1.1`  
**Baseline:** Production **`v1.0.2`** (`685d7ab`) — tenant isolation, workflow, dashboard, accounts hotfixes  
**Last updated:** 2026-06-29  

This document freezes the **user-approved import sequence** for v1.1 tenant migration. Engineering work must not start from this commit alone; it traces requirements for the v1.1 feature line described in `docs/BULK_IMPORT_MIGRATION.md` and `docs/MAXEK_ERP_RELEASE_PLAN.md`.

---

## Purpose

Deliver a **phased Excel/CSV migration path** for new or resetting tenants so that:

1. Commercial and planning **library seed data** is loaded in dependency order.
2. **Party and accounts masters** load after libraries that reference them.
3. **Validation, audit, and rollback** close each migration before production cutover.

Successful v1.1 import **feeds v1.2 Planning & Costing** per the frozen architecture in `docs/PLANNING_COSTING_V1_2_SPEC.md` on branch `release/v1.2-planning` (master libraries, BOQ auto-load, seven-tab planning). v1.1 does **not** ship the v1.2 planning UI.

---

## Mandatory import order (Phases 1–5)

Imports run **strictly in phase order**. Within a phase, run sheets **top to bottom**. Do not skip phases. Later phases assume earlier data exists for cross-reference validation.

### Phase 1 — Commercial baseline (project-scoped)

| Step | Module | Delivers | v1.2 consumer |
|------|--------|----------|----------------|
| 1.1 | **BOQ** | Standard BOQ library + project BOQ lines (quantities, rates, workflow) | BOQ integration (v1.2 §7) |
| 1.2 | **WBS** | Standard WBS template nodes / project WBS snapshot seed | Master libraries, template snapshot (v1.2 §6, §4.3) |

**Gate:** BOQ line keys and WBS node codes stable; project_id resolved for all project-scoped rows.

### Phase 2 — Resource, productivity, and rate libraries

| Step | Module | Delivers | v1.2 consumer |
|------|--------|----------|----------------|
| 2.1 | **Labour** | Trade / crew labour norms (hours per unit, trade codes) | Labour planning tab, rate roll-up |
| 2.2 | **Machinery** | Equipment types, hours per unit, hire/own flags | Machinery planning tab |
| 2.3 | **Material** | Material master (+ optional store linkage) | Material planning tab, MR/PR |
| 2.4 | **Productivity** | Output norms (crew/equipment productivity by activity) | Productivity library (v1.2 Phase 1) |
| 2.5 | **Rate** | Effective-dated labour, machinery, material, subcontract rates | Rate resolution at planning time (v1.2 §4.2) |

**Gate:** Each rate row references valid resource codes from 2.1–2.3; productivity rows reference WBS/BOQ activity keys where applicable.

### Phase 3 — Party masters (tenant-scoped)

| Step | Module | Delivers | Notes |
|------|--------|----------|-------|
| 3.1 | **Customer** | Client / customer master | Used by projects, billing, rate scope |
| 3.2 | **Vendor** | Supplier master | Procurement, subcontract, AP |
| 3.3 | **Employee** | Employee master | Workforce, attendance, payroll hooks |

**Gate:** GST/PAN/duplicate validators per `bulk_import_service` rules; no orphan project customer references.

### Phase 4 — Accounts opening

| Step | Module | Delivers | Notes |
|------|--------|----------|-------|
| 4.1 | **Chart of Accounts (CoA)** | Ledger hierarchy | Required before balances |
| 4.2 | **Opening balances** | OB vouchers / ledger opening entries | Must tie to CoA; period lock rules apply post-migration |

**Gate:** Trial balance sanity check (debits = credits) before Phase 5 sign-off.

### Phase 5 — Validation, audit, and rollback

| Step | Capability | Delivers |
|------|------------|----------|
| 5.1 | **Validation** | Full-file and cross-phase referential checks; row/column error report (Row, Column, Error, Suggested Fix) |
| 5.2 | **Audit** | `import_audit_log` entries per module/file (user, timestamp, counts, filename, tenant) |
| 5.3 | **Rollback** | Documented rollback point: DB backup taken before Phase 1; per-phase undo policy (delete-by-import-batch or full restore) |

**Gate:** Migration wizard **Finish** step allowed only when Phase 5.1 reports zero blocking errors and audit records exist for every successful save.

---

## End-to-end sequence (single view)

```text
Phase 1:  BOQ → WBS
Phase 2:  Labour → Machinery → Material → Productivity → Rate
Phase 3:  Customer → Vendor → Employee
Phase 4:  CoA → Opening balances
Phase 5:  Validation → Audit → Rollback readiness
```

---

## Prerequisite: sample migration dataset

Before staging UAT, maintain a **reference Excel pack** under:

`docs/samples/v1.1-import/`

See `docs/samples/v1.1-import/README.md` for the canonical file list and column expectations. **Real customer data must not be committed**; use anonymized exports only.

---

## Dependency on v1.2 (frozen spec)

| v1.1 import output | v1.2 planning use |
|--------------------|-------------------|
| BOQ + WBS seed | BOQ-driven auto-load of template, activities, resources |
| Labour, Machinery, Material libraries | Seven-tab planning workspace norms |
| Productivity + Rate libraries | Cost roll-up and effective-dated rate resolution |
| Customer / vendor / employee | Scope for rates, procurement, workforce actuals |
| CoA + opening balances | Accounts integration after budget lock (execution phase) |

**Reference:** `release/v1.2-planning` → `docs/PLANNING_COSTING_V1_2_SPEC.md` (APPROVED / FROZEN 2026-06-29).

---

## Explicitly out of scope for this spec commit

- No new Python routes, services, or templates
- No changes to `bulk_import_service.py`, `data_import_registry.py`, or migration wizard code
- No production deploy or VPS patch build

Implementation tracking continues on `release/v1.1` after this document is merged.

---

## Related documents

| Document | Role |
|----------|------|
| `docs/BULK_IMPORT_MIGRATION.md` | Current implemented vs Phase 2 matrix |
| `docs/MAXEK_ERP_RELEASE_PLAN.md` | Release sequencing and tagging policy |
| `docs/PLANNING_COSTING_V1_2_SPEC.md` | Downstream planning platform (frozen on `release/v1.2-planning`) |
