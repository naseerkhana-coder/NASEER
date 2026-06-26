# Petty Cash FRS Gap Analysis

Audit date: 2026-06-16  
Scope: FRS sections 1–13 vs MAXEK_ERP implementation after Phase B.

## Summary

| Section | Topic | Status |
|---------|-------|--------|
| 1 | Request entry | **DONE** |
| 2 | Request management | **DONE** |
| 3 | Maker-checker workflow | **DONE** |
| 4 | Fund transfer | **DONE** |
| 5 | Amount received | **DONE** |
| 6 | Expense entry | **DONE** |
| 7 | Document upload | **PARTIAL** |
| 8 | Expense validation | **DONE** |
| 9 | Running balance | **DONE** |
| 10 | Settlement submission | **DONE** |
| 11 | Settlement approval | **DONE** |
| 12 | Reports & dashboard | **PARTIAL** |
| 13 | Audit trail | **PARTIAL** |

---

## Section 1 — Request Entry

| Requirement | Status | Notes |
|-------------|--------|-------|
| Menu: Accounts → Petty Cash → New Request | DONE | Nav item + page action + `#new-request` anchor |
| Request date | DONE | |
| Project name / ID sync | DONE | `petty-cash-form.js` bidirectional sync |
| Staff name / employee ID sync | DONE | Linked to `staff` master |
| Department | DONE | From departments master + staff auto-fill |
| Purpose, description | DONE | |
| Required amount | DONE | |
| Priority (Normal / Urgent) | DONE | |
| Remarks | DONE | |
| Save Draft / Submit Request | DONE | |
| Auto PCR-YYYY-NNNN numbers | DONE | `generate_petty_cash_request_number()` |
| Full status lifecycle | DONE | Draft → Submitted → … → Closed |

## Section 2 — Request Management

| Requirement | Status | Notes |
|-------------|--------|-------|
| View | DONE | `?view=` |
| Edit (before approval) | DONE | Draft, Submitted/Pending Checker, Rejected |
| Delete (before approval) | DONE | |
| List with filters | DONE | Status, project, text search |

## Section 3 — Maker-Checker Workflow

| Requirement | Status | Notes |
|-------------|--------|-------|
| Integration with `workflow_service` | DONE | Module `petty_cash`, table `petty_cash_requests` |
| Maker → Checker → Approver | DONE | Existing approval center |
| Approve / Reject with mandatory comments | DONE | Via `workflow.js` modals (reject requires comment) |
| Send back | DONE | Rejection returns to maker (existing pattern) |

## Section 4 — Fund Transfer

| Requirement | Status | Notes |
|-------------|--------|-------|
| Transfer form (accounts) | DONE | `?transfer=` |
| Date, amount, bank, account, UTR, ref, mode, remarks | DONE | |
| Status → Funds Transferred | DONE | |

## Section 5 — Amount Received

| Requirement | Status | Notes |
|-------------|--------|-------|
| Staff confirms receipt | DONE | Confirm button on view screen |
| Status → Amount Received | DONE | |

## Sections 6–8 — Expenses

| Requirement | Status | Notes |
|-------------|--------|-------|
| Multiple expenses per request | DONE | `petty_cash_expenses` |
| Category, description, vendor, bill no, amount | DONE | |
| Staff auto-fill | DONE | |
| Expense ≤ available balance | DONE | Server-side validation |
| Delete expense (pre-settlement) | DONE | |

## Section 7 — Document Upload

| Requirement | Status | Notes |
|-------------|--------|-------|
| Desktop JPG, PNG, PDF | DONE | |
| DOC / XLS optional | DONE | Allowed extensions include office formats |
| Linked to expense / request | DONE | `petty_cash_attachments` |
| View / download | DONE | `/petty_cash/attachment/<id>` |
| Mobile camera capture | **MISSING** | Deferred — requires mobile UI / `capture` attribute |

## Section 9 — Running Balance

| Requirement | Status | Notes |
|-------------|--------|-------|
| Transferred − expenses = balance | DONE | View + expenses screens |
| Running expense total | DONE | `expenses_total` column refreshed on change |

## Sections 10–11 — Settlement

| Requirement | Status | Notes |
|-------------|--------|-------|
| Submit settlement with remarks | DONE | |
| Accounts approve / reject with comment | DONE | Mandatory comment on both actions |
| Status Settlement Pending → Settled | DONE | |
| Close request | DONE | Settled → Closed |

## Section 12 — Reports & Dashboard

| Requirement | Status | Notes |
|-------------|--------|-------|
| Basic status counts on list page | DONE | Chip counts per status |
| Full dashboard / analytics suite | **MISSING** | Deferred |
| Export / period reports | **MISSING** | Deferred |

## Section 13 — Audit Trail

| Requirement | Status | Notes |
|-------------|--------|-------|
| `created_by`, `created_at` | DONE | |
| `modified_by`, `modified_at` | DONE | |
| Workflow audit via `approval_audit` | DONE | Existing module |
| Dedicated petty-cash audit UI | **MISSING** | Deferred |
| Per-field change history | **MISSING** | Deferred |

---

## Legacy Note

The original `petty_cash` table (single expense rows) remains in the database for historical data but is **no longer used** by the UI. New work uses `petty_cash_requests` and related tables.

---

## Recommended Backlog (priority order)

1. Mobile camera upload for bill photos (`<input capture="environment">` + responsive layout)
2. Petty Cash dashboard widget on main dashboard (open requests, pending settlement)
3. Accounts reports: requests by project/period, settlement aging
4. Full audit trail UI (timeline per request)
5. Email / notification templates specific to petty cash milestones
6. Migrate or archive legacy `petty_cash` rows
