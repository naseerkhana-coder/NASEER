# Payroll FRS — Gap Analysis (MVP vs Full FRS)

**Project:** MAXEK ERP  
**Date:** 2026-06-17  
**Scope:** Final Payroll System MVP implementation

## MVP Delivered

| FRS Area | Status | Notes |
|----------|--------|-------|
| Employee categories (staff, company workers, subcontractors) | ✅ Partial | Uses existing `staff` + `workers` tables; company workers = non-subcontractor workers |
| Employee master fields (salary_type, OT, holiday pay, bank) | ✅ | Added `ot_rate_per_hour`, `holiday_pay_applicable` on staff/workers; bank fields already present |
| Salary revision management | ✅ | `salary_revisions` table + staff increment sync + `/payroll/revisions` + staff profile history |
| Employee profile view | ✅ | `/employee/<type>/<id>` with salary, revisions, attendance summary, payroll summary |
| Daily wage calculation | ✅ | `calculate_daily_wage()` in `payroll_service.py` per FRS rules |
| Monthly staff salary | ✅ | Pro-rata from attendance + OT + holiday pay in `calculate_monthly_staff_pay()` |
| Holiday master | ✅ | `holidays` + `holiday_applicability` + CRUD at `/payroll/holidays` |
| Payroll generation (monthly / date range / filters / bulk select) | ✅ | `/payroll` draft generation via `generate_payroll_run()` |
| Draft workflow | ✅ Partial | Draft → Employee Verification → Checker → Approver via `payroll_runs` + `workflow_service` |
| Salary payment module | ✅ | `salary_payments` + `/payroll/payments` + slip print |
| Payroll freeze | ✅ | `locked` flag on runs/lines after payment; admin reopen |
| Reports | ✅ Partial | Monthly register Excel export; print salary slip template |
| Navigation | ✅ | Workforce subbar: Payroll, Holidays, Salary Revisions, Payments |
| Legacy salary page | ✅ Preserved | `/salary` unchanged for worker salary records |

## Deferred / Gaps

### High priority (post-MVP)

1. **Dedicated leave module integration** — Leave days are approximated as `working_days - present_days`; no link to `leave_requests` table for paid/unpaid leave rules.
2. **Statutory deductions** — PF, ESI, TDS, professional tax not calculated; `deductions` field is manual/zero by default.
3. **Advance / loan recovery** — No advance master; `advance_deduction` not auto-populated from accounts.
4. **Employee self-service verification** — Verification is HR marking lines verified; no employee login/OTP confirmation step.
5. **PDF salary slip** — Print-friendly HTML only; no WeasyPrint/reportlab PDF generation.
6. **Company worker CRUD page** — Company workers managed via workers table; no dedicated UI separate from subcontractors page.
7. **Subcontractor revision UI on worker profile** — Revisions via central page; worker edit form has no inline revision block (staff has increment UI).

### Medium priority

8. **Payroll line edit form in UI** — Backend supports `update_line` but no inline edit modal on payroll view.
9. **Multi-project split pay** — Single project filter only; no split when employee worked multiple projects in period.
10. **Salary component breakdown on slip** — Monthly staff component split (HRA, basic, etc.) not shown on slip.
11. **Attendance approval gate** — Includes non-approved attendance with soft filter; stricter approval-only mode not configurable.
12. **Bulk payment batch** — Payments recorded one line at a time; no single bank file for full run.
13. **Audit trail on payroll edits** — No dedicated payroll audit log beyond workflow audit.
14. **Email / SMS payslip dispatch** — Not implemented.

### Low priority / FRS stretch

15. **Shift-wise / night allowance rules**
16. **Arrear and retrospective revision runs**
17. **Cost centre / WBS allocation of payroll cost**
18. **Integration with account_payments auto-voucher**
19. **Biometric attendance import**
20. **Full report pack** (PF register, ESI, bank advice, department-wise summary)

## Technical Notes

- **Tables added:** `payroll_runs`, `payroll_lines`, `salary_revisions`, `holidays`, `holiday_applicability`, `salary_payments`
- **Service:** `payroll_service.py` — keep calculation logic here; routes stay thin
- **Pending dashboard:** `list_pending_payroll_months()` on `/payroll` lists staff/workers with attendance data but no finalized payroll per month
- **Workflow:** Module id `payroll` uses `payroll_runs` as record table (legacy `salary` table still used by old salary page)
- **Schema bootstrap:** `ensure_payroll_tables()` called from `init_db`, `ensure_runtime_schema`, `prepare_staff_page_db`, `prepare_payroll_page_db`

## WinSCP Deploy List

Upload or sync these paths to VPS:

```
app.py
payroll_service.py
workflow_service.py
templates/payroll.html
templates/payroll_holidays.html
templates/payroll_payments.html
templates/payroll_print_slip.html
templates/payroll_revisions.html
templates/employee_profile.html
templates/staff.html
static/js/payroll-forms.js
docs/PAYROLL-FRS-GAP-ANALYSIS.md
```

After deploy: restart gunicorn/uwsgi; SQLite migrations run automatically on first request via `ensure_runtime_schema`.

## Verification Checklist

- [ ] `python -m py_compile app.py payroll_service.py`
- [ ] Generate monthly draft payroll for staff
- [ ] Generate date-range payroll for company worker with attendance
- [ ] Submit run through checker/approver workflow
- [ ] Record payment and confirm run locks
- [ ] Export register Excel
- [ ] Print salary slip
- [ ] Confirm `/salary` and `/attendance` still work unchanged
