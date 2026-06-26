# DPR FRS Gap Analysis

**Module:** MAXEK ERP — Daily Progress Report (DPR)  
**Audit date:** 2026-06-16  
**Sources reviewed:** `templates/dpr.html`, `static/js/dpr-forms.js`, `app.py` (DPR routes & APIs)

Legend: **DONE** · **PARTIAL** · **MISSING**

---

## Section 1 — Project Selection

| Requirement | Status | Notes |
|-------------|--------|-------|
| Select Project Number or Project Name | **DONE** | Linked dropdowns in DPR entry form |
| Auto-sync Number ↔ Name | **DONE** | `syncProjectDropdowns()` in `dpr-forms.js` |
| Project details auto-populate | **PARTIAL** | Project ID synced; extended project metadata not shown on DPR form |

---

## Section 2 — BOQ Selection

| Requirement | Status | Notes |
|-------------|--------|-------|
| Select BOQ Number or BOQ Specification | **DONE** | BOQ number + description (item) dropdowns |
| Auto-sync Number ↔ Specification | **DONE** | `selectBoqItem()` |
| Unit auto-fill | **DONE** | From selected `boq_items` row |
| BOQ Quantity auto-fill | **DONE** | `data-dpr-boq-qty-display` (this session) |
| Balance Quantity auto-fill | **DONE** | `data-dpr-balance-qty-display` + progress API (this session) |

---

## Section 3 — Client Billing Selection

| Requirement | Status | Notes |
|-------------|--------|-------|
| Bill Client YES/NO | **DONE** | `bill_client` select |
| YES → Client Billing Register flow | **DONE** | `billing_status='pending'`, Client Bill Pending tab, print/export |
| NO → internal tracking only | **DONE** | Costing resources panel, `for_costing` flag |
| Draft excluded from billing queue | **DONE** | Drafts do not set `billing_status=pending` (this session) |

---

## Section 4 — Measurement Entry Module

| Requirement | Status | Notes |
|-------------|--------|-------|
| Multiple measurement rows per BOQ | **PARTIAL** | **m³ / m²:** multiple L/W/D readings with average (preserved). **Steel BBS:** multiple bar lines (preserved). **Simple units:** unlimited description + value rows with total/average (this session) |
| Add / Delete measurement rows | **DONE** | Per unit-type UI (readings, steel lines, simple rows) |
| Save Measurements | **DONE** | Submit DPR / Save Measurements buttons |
| Total quantity | **DONE** | Calculated qty display + server-side parse |
| Average quantity (optional) | **DONE** | Simple-unit checkbox `use_average` |
| Unlimited rows | **DONE** | No hard cap on reading/steel/simple rows |
| History per BOQ | **DONE** | Each save inserts `dpr_measurements`; continue-same-BOQ modal |

---

## Section 5 — BOQ Activity Split-Up

| Requirement | Status | Notes |
|-------------|--------|-------|
| Activity master | **PARTIAL** | Default activity list in `DEFAULT_DPR_ACTIVITIES` + custom activity (this session) |
| Multiple activities per BOQ item | **DONE** | Activity rows UI |
| Activity-wise quantity | **DONE** | Stored in `measurement_data.activities` |
| Activity progress / BOQ progress rollup | **PARTIAL** | Activity total shown in UI; not yet rolled into BOQ completion % separately |
| BOQ Activity Master table | **MISSING** | No dedicated master CRUD; uses static list |

---

## Section 6 — Manpower Entry

| Requirement | Status | Notes |
|-------------|--------|-------|
| Worker Name / ID / Trade | **DONE** | Linked selects + `/api/dpr/workers` |
| Auto-fill from employee master | **DONE** | Staff + subcontractor workers |
| Add / Delete manpower | **DONE** | Row template |
| Save Manpower | **PARTIAL** | Section "Save Manpower" validates & stages payload; persists on DPR submit |
| Multiple entries | **DONE** | Unlimited rows |

---

## Section 7–9, 11 — Equipment Utilization & Charging

| Requirement | Status | Notes |
|-------------|--------|-------|
| Select by Reg No or Type | **DONE** | Equipment master + dropdowns (this session) |
| Auto-fill name / reg / type / owner | **DONE** | `equipment_master` seed data |
| Start / End reading → worked units | **DONE** | Auto-calculated worked hrs/km |
| Rate types: hourly, km, trip, lump sum | **DONE** | Rate type select + amount calc |
| Add / Delete / Save equipment | **PARTIAL** | Add/delete + Save Equipment staging; persists on DPR submit |
| Unlimited equipment rows | **DONE** | No row cap |
| Equipment master maintenance UI | **MISSING** | Seeded table only |

---

## Section 12 — Site Photo & Document Upload

| Requirement | Status | Notes |
|-------------|--------|-------|
| Desktop upload PDF/JPG/PNG | **DONE** | Site DPR upload section |
| Multiple uploads | **DONE** | One file per upload; list/filter/history |
| Link to DPR measurement | **DONE** | Optional `measurement_id` |
| View / download attachments | **DONE** | `dpr_attachment_file` route |
| Mobile camera direct capture | **MISSING** | Deferred — future mobile app |

---

## Section 13 — DPR Submission Workflow

| Requirement | Status | Notes |
|-------------|--------|-------|
| Save Draft | **DONE** | `dpr_status=draft` (this session) |
| Submit DPR | **DONE** | `dpr_status=submitted` + approval request |
| Edit DPR | **MISSING** | No edit screen for existing measurement |
| View DPR | **PARTIAL** | Recent list + costing/client bill views |
| View / download documents | **DONE** | Attachment viewer |
| Download DPR PDF | **MISSING** | No PDF export of full DPR |
| Draft → Review → Submit → Approve | **PARTIAL** | Draft/submit + existing checker/approver workflow on submit |

---

## Section 14 — DPR vs BOQ Comparison

| Requirement | Status | Notes |
|-------------|--------|-------|
| BOQ Qty | **DONE** | Progress panel + API |
| Today's Qty | **DONE** | Includes in-form calculated qty |
| Total Executed | **DONE** | Sum of submitted measurements |
| Balance Qty | **DONE** | |
| Completion % | **DONE** | |

---

## Section 15 — Client Billing Integration

| Requirement | Status | Notes |
|-------------|--------|-------|
| Transfer measurements & quantities | **DONE** | Client Bill Pending |
| BOQ reference | **DONE** | `boq_item_id`, number, description |
| Activity-wise quantities | **PARTIAL** | Stored in JSON; not yet on client bill print/export |
| Supporting documents | **PARTIAL** | Attachments linked by measurement; not auto-attached to bill export |

---

## Section 16 — Dashboard Reports

| Requirement | Status | Notes |
|-------------|--------|-------|
| Project / BOQ / Activity progress reports | **MISSING** | Deferred |
| Client billing quantities report | **PARTIAL** | Client bill pending + Excel export only |
| Equipment / manpower utilization reports | **MISSING** | Deferred |
| DPR status report | **MISSING** | Deferred |

---

## Section 17 — Audit Trail

| Requirement | Status | Notes |
|-------------|--------|-------|
| Created By / Created Date | **DONE** | `created_by`, `created_at` |
| Modified By / Modified Date | **PARTIAL** | Columns added; set on create (this session); no edit updates yet |
| DPR / measurement revision history | **MISSING** | Deferred |
| Document upload history | **PARTIAL** | `dpr_attachments` list with uploader/timestamp |

---

## Implemented This Session

1. BOQ quantity + balance display and live **DPR vs BOQ** comparison panel (`/api/dpr/boq-progress`)
2. **Simple-unit** multiple measurement rows (total + optional average) — steel & m³ UIs unchanged
3. **BOQ activity split-up** rows with default activity master list
4. **Equipment master** (`equipment_master` table), reg/type selection, readings, rate types, amount calc
5. **Save Draft / Submit DPR** workflow via `dpr_status`
6. `modified_at` / `modified_by` columns on `dpr_measurements`
7. APIs: `/api/dpr/equipment`, `/api/dpr/activities`, `/api/dpr/boq-progress`

---

## Recommended Next Phase

1. DPR edit / view detail page with revision history
2. Dedicated BOQ Activity Master CRUD
3. Equipment Master maintenance screen
4. Dashboard reports (Section 16)
5. DPR PDF export
6. Mobile camera capture for site photos
7. Roll activity quantities into client bill export and BOQ progress charts

---

## WinSCP Deploy File List

Upload to `/var/www/maxek-erp-flask/`:

| Local file | Remote path |
|------------|-------------|
| `app.py` | `/var/www/maxek-erp-flask/app.py` |
| `templates/dpr.html` | `/var/www/maxek-erp-flask/templates/dpr.html` |
| `static/js/dpr-forms.js` | `/var/www/maxek-erp-flask/static/js/dpr-forms.js` |
| `docs/DPR-FRS-GAP-ANALYSIS.md` | `/var/www/maxek-erp-flask/docs/DPR-FRS-GAP-ANALYSIS.md` |

**Post-deploy (SSH):** restart Gunicorn/service. New tables/columns are created automatically on first DPR page load via `prepare_dpr_page_db()`.

```bash
sudo systemctl restart maxek-erp
# or your service name
```
