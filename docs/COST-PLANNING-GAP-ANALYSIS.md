# Cost Planning FRS — Integration Gap Analysis

**Module:** Project Cost Planning & Monitoring System  
**Status:** MVP implemented (Flask + SQLite)

## Implemented (MVP)

| FRS Section | Status | Notes |
|-------------|--------|-------|
| 1. Cost Planning per BOQ item | DONE | `cost_plans` linked to project, BOQ master, BOQ item |
| 2. Categories (Manpower, Machinery, Material) | DONE | Child tables with planned qty/cost calc |
| 3. Material Planning | DONE | Consumption factor × BOQ qty × rate |
| 4. Manpower Planning | DONE | Hours/unit × BOQ qty × labour rate |
| 5. Machinery Planning | DONE | Hours/unit × BOQ qty × hourly rate |
| 6. BOQ Activity Split-Up | DONE | `cost_plan_activities` user-defined activities |
| 7. WBS hierarchy | DONE | Tree: Project → BOQ → Item → Activity |
| 8. Micro Planning | DONE | Daily/Weekly/Monthly `micro_plan_entries` |
| 9. DPR Integration | PARTIAL | See gaps below |
| 10–12. Planned vs Actual, Variance, Productivity | PARTIAL | Monitoring table + dashboard widgets |
| 13. Dashboard | DONE | Summary cards on cost planning page |
| 14. Reports | PARTIAL | Excel register + print summary; other reports stubbed |

## DPR Integration — What Works

- **Actual quantity:** `SUM(dpr_measurements.calculated_quantity)` per `boq_item_id`
- **Manpower hours:** `dpr_manpower.hours_worked` joined via `measurement_id`
- **Equipment:** Parsed from `measurement_data.equipment[]` (`hours_used`, `amount`)
- **Materials:** Parsed from `measurement_data.materials[]`
- **Activities:** Parsed from `measurement_data.activities[]` (name match, fuzzy)

## Integration Gaps

1. **No `cost_plan_activity_id` on DPR rows** — DPR links to `boq_item_id` only. Activity-level actuals rely on matching activity names in DPR `activities_payload` JSON. Renamed activities may not align.

2. **Labour actual cost** — DPR stores manpower hours, not rupee cost. Actual labour cost is estimated using planned average labour rate (hours × proxy rate), not payroll/subcontractor rates.

3. **Material actual cost** — DPR materials store qty/unit only; no rates. Material variance uses equipment cost + labour proxy only at header level.

4. **Equipment cost** — Only amounts entered in DPR equipment rows are summed; hired equipment without amount field is under-reported.

5. **Micro plan vs DPR** — No automatic comparison of micro plan entries to same-day DPR (manual monitoring only).

6. **Workflow / approval** — Cost plans do not use maker-checker workflow (Draft/Active status only).

7. **Material Management / Store** — No link to `material_requests`, `store_issues`, or inventory.

8. **Client Billing / Accounts** — No link to `project_expenses` or `dpr_measurement_id` costing flow.

9. **Reports** — Nine report types listed; only cost plan register Excel and project print summary are live.

10. **Profitability** — BOQ item `rate`/`amount` vs planned cost not shown on dashboard (management outcome §15).

## Recommended Next Steps

1. Add optional `activity_id` FK on DPR `activities_payload` when saving DPR (backward compatible).
2. Pull labour rates from `subcontractor_manpower_rates` or staff salary for actual cost.
3. Wire material rates from store/PO for material actual cost.
4. Add workflow module `cost_plan` in `workflow_master`.
5. Micro plan vs DPR daily variance report.

## VPS Deploy

Tables are created automatically via `ensure_cost_planning_tables()` on first page load. No separate SQL migration required unless you prefer offline migration.
