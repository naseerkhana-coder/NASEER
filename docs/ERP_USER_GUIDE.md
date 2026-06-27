# MAXEK ERP — User Guide

**Version:** MAXEK ERP v1.0  
**Audience:** End users, department heads, and customer administrators  
**Production URL:** https://erp.maxekindia.com

---

## 1. Getting started

### 1.1 Sign in

1. Open the ERP URL in Chrome or Edge.
2. Enter your **username** and **password**.
3. After login you land on the **Command Centre** (`/dashboard`) — a department grid, not a legacy top module bar.

**Roles (typical):**

| Role | Purpose |
|------|---------|
| **Super Admin** | Platform operator — customer licenses, limits, ERP settings (`superadmin`) |
| **Customer Admin** | Your organisation’s administrator — users, masters, all modules (`admin`) |
| **Manager / Maker / Checker / Approver** | Day-to-day operations with workflow |
| **Guest / User** | Limited module access |

Password changes: use **Settings → User Management** (admin) or ask your administrator. The login page “Forgot password” notifies an admin; there is no self-service email reset.

### 1.2 Command Centre (main dashboard)

The dashboard shows **department tiles** (Projects, HR & Payroll, Accounts, Store, etc.). Click a tile to open that department’s **workspace** (`/dept/<slug>`) with its own left sidebar.

**Bottom widgets** (placeholders / KPIs): Project Progress, Pending Approvals, Cash vs Budget, Expense Breakdown.

**Quick actions** (Overview tab): Create DPR, Material Request, New PO, Attendance.

### 1.3 Company & project context

If your site shows a **company / branch / project** selector in the header, pick the legal entity and active project before entering transactions. Selection is saved per user.

---

## 2. Main toolbar (global navigation)

When you work outside a single department portal, the **top toolbar** groups modules:

| Toolbar | What it covers |
|---------|----------------|
| **Dashboard** | Executive dashboard, KPIs, approvals queue |
| **Projects** | Clients, projects, BOQ, DPR, billing, documents |
| **Planning** | SmartQTO, cost planning, WBS, rate analysis |
| **Procurement** | Material request → PR → PO → GRN |
| **Store** | Receipt, issue, transfer, stock |
| **Accounts** | Vouchers, books, GST, TDS, petty cash |
| **HR & Payroll** | Staff, attendance, timesheet, payroll, leave |
| **Fleet & Mechanical** | Vehicles, fuel, maintenance |
| **Plant Operations** | Asphalt, RMC, crusher, wet mix, dispatch |
| **Quality Control** | QC masters and plant QC |
| **Administration** | Office inward/outward, letters, fleet dashboard |
| **Reports** | Operational and financial reports |
| **Settings** | Users, masters, workflow, backups |

Each toolbar item opens a **sub-toolbar** with standard shortcuts (e.g. Accounts: Payment Voucher, Receipt Voucher, GST, Reports).

---

## 3. Department workspaces

Department portals isolate tools in one sidebar. Access via dashboard tiles or `/dept/<slug>`.

### 3.1 Projects (`/dept/projects`)

| Menu item | Use for |
|-----------|---------|
| Project Master | Create and maintain projects |
| BOQ Management | Bill of quantities — items, rates, amounts |
| DPR Entry | Daily progress report — work done, manpower, materials |
| Client Billing | Running account (RA) bills to clients |
| WBS Planning | Work breakdown / planning link |
| Costing | Project expenses and cost tracking |
| Project Reports | Excel / PDF exports |

**Typical flow:** Client → Project → BOQ → DPR (site progress) → Client Billing.

### 3.2 HR & Payroll (`/dept/hr-payroll`)

| Menu item | Use for |
|-----------|---------|
| Employee Master | Staff records, salary structure |
| Attendance | Daily / monthly staff attendance |
| Timesheet | Time booking by project |
| Payroll | Monthly payroll run, approvals |
| Salary Payment | Disbursement tracking |
| Leave Management | Leave applications |
| PF / ESI | Statutory registers |
| Reports | HR exports |

### 3.3 Accounts (`/dept/accounts`)

Grouped as **Masters | Transactions | Books**.

| Area | Items |
|------|-------|
| Masters | Chart of Accounts, Bank Master, Petty Cash setup |
| Transactions | Daily expenses, expense/purchase vouchers, receipts, payments |
| Books | Cash book, bank book, day book, general ledger, GST, TDS, reports |

**Chart of Accounts** is seeded with standard construction heads (Cash, Bank, Material Purchase, Labour, Client Billing, etc.). Activate or add heads before posting vouchers.

### 3.4 Store (`/dept/store`)

| Menu item | Use for |
|-----------|---------|
| Material Request | Site requisition to store/purchase |
| Store Receipt | GRN — goods inward |
| Store Issue | Issue to project/site |
| Purchase Request | Formal PR for purchase team |
| Stock Register | On-hand balances |
| Inventory Reports | Stock movement reports |

### 3.5 Subcontract (`/dept/subcontract`)

Subcontractors, workers, worker attendance/timesheet, subcontract bills, payments.

### 3.6 Planning & Costing (`/dept/planning-wbs`)

Cost planning, WBS, BOQ, project expenses, planning reports.

### 3.7 Plant operations

Separate portals: **Plant Operations**, **Asphalt Plant**, **Concrete Plant (RMC)**, **Precast Yard** — production, dispatch, QC, costing.

### 3.8 Vehicle / Fleet (`/dept/vehicle`)

Vehicle master, documents, running log, diesel purchase/stock/issue.

### 3.9 QC (`/dept/qc`)

QC test master, plant QC records, QC reports.

### 3.10 Administration (`/dept/administration`)

Office inward/outward registers, letters, agreements, legal documents, corporate DMS, fleet dashboard.

### 3.11 Consultancy (`/dept/consultancy`)

Client register, tender review, drawings, BOQ/estimate, consultancy billing, MIS reports.

---

## 4. Approvals workflow

Most operational documents use **Maker → Checker → Approver**:

1. **Maker** creates or edits a draft.
2. **Checker** reviews (Pending Checker).
3. **Approver** final approval (Pending Approver).

Open **Approval Dashboard** from the dashboard toolbar or notifications bell. Workflow roles tie to **designations** configured under Settings / Workflow Master.

---

## 5. Common tasks (step-by-step)

### 5.1 New project

1. **Projects** → Client Master (if new client).
2. **Projects** → Project List → Create Project.
3. Fill location, dates, manager, budget → Save.
4. Optional: BOQ Management → add items.

### 5.2 Daily site progress (DPR)

1. Select **project** in header context.
2. **DPR Entry** → choose date → enter work done, manpower, materials.
3. Submit for approval if required.

### 5.3 Material procurement

1. **Material Request** (site need).
2. **Purchase Request** → **Purchase Order** after approval.
3. **Store Receipt (GRN)** when material arrives.
4. **Store Issue** to project.

### 5.4 Payment to vendor

1. **Accounts** → Expense / Purchase voucher (or Payment Voucher).
2. Select **Chart of Accounts** head, party, GST if applicable.
3. Route through approval → appears in bank/cash book after posting.

### 5.5 Monthly payroll

1. Complete **Attendance** / timesheets for the month.
2. **Payroll** → create run → review lines.
3. Submit for checker/approver → **Salary Payment** when paid.

---

## 6. Settings & administration (Customer Admin)

| Area | Location | Purpose |
|------|----------|---------|
| User Management | Settings | Create users, roles, workflow role |
| Designations | Settings / Masters | Job titles for workflow routing |
| Departments | Settings / Masters | Org departments (dropdowns) |
| Workflow Master | Settings | Per-module maker/checker/approver |
| Company Master | Settings | Legal entities, branches, GST |
| Backups | Settings / Admin | Scheduled DB backups |

**Super Admin only** (platform): Customer Master, License Master, Subscriptions, User/Branch/Storage Limits, Login Monitoring, Support Tickets, ERP Settings — under **ERP Administration** menu when logged in as `superadmin`.

---

## 7. Search & help

- **Global search** (header): projects, BOQ, DPR, materials, employees, vendors, POs, invoices.
- **Help Center**: User manual, videos, contact support, WhatsApp support link.

---

## 8. Tips

1. Always set **company / project context** before transactional entry.
2. Use **department portals** for focused work; use the **main toolbar** to cross modules quickly.
3. Watch the **notifications** and **approval** badges on sub-toolbars.
4. Export reports from module **Reports** screens or Accounts Reports for finance.
5. For demos, use the isolated **Demo Customer** login (see admin runbook) — not production data.

---

## 9. Support

- In-app: **Help → Contact Support**
- Administrator: reset passwords via User Management or VPS admin script (IT)
- Platform: Super Admin → Support Tickets

---

*This guide reflects `ui_shell_config.py` and the Command Centre layout as deployed on erp.maxekindia.com. Menu labels may vary slightly if your administrator hides modules by role.*
