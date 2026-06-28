# Production UAT Checklist — MAXEK ERP

**Environment:** https://erp.maxekindia.com  
**Date tested:** _______________  
**Tester:** _______________

Use this checklist during browser testing. Tick each box when verified. Note failures in the **Issues** column.

---

## 1. Login

| # | Test case | Super Admin | Customer Admin | Company Admin | Normal User | Checker | Approver | Issues |
|---|-----------|:-----------:|:--------------:|:-------------:|:-----------:|:-------:|:--------:|--------|
| 1.1 | Login page loads with company code field | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 1.2 | Valid credentials → dashboard | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 1.3 | Invalid password shows clear error | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 1.4 | Wrong company code blocked / message shown | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 1.5 | Session persists on refresh | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 1.6 | Logout clears session and returns to login | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 1.7 | Super Admin: Platform Command Centre accessible | ☐ | — | — | — | — | — | |
| 1.8 | Customer Admin: tenant dashboard only (no platform admin) | — | ☐ | — | — | — | — | |

---

## 2. Navigation

| # | Test case | Super Admin | Customer Admin | Company Admin | Normal User | Checker | Approver | Issues |
|---|-----------|:-----------:|:--------------:|:-------------:|:-----------:|:-------:|:--------:|--------|
| 2.1 | Sidebar loads all licensed modules | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 2.2 | Breadcrumbs correct on module pages | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 2.3 | Department hub links open correct workspace | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 2.4 | Settings → Company Master opens legal registration | ☐ | ☐ | ☐ | — | ☐ | ☐ | |
| 2.5 | Settings → Users opens user list | ☐ | ☐ | ☐ | — | ☐ | ☐ | |
| 2.6 | Super Admin → Customer Settings (branding only) | ☐ | — | — | — | — | — | |
| 2.7 | Unlicensed module shows placeholder / blocked | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 2.8 | Mobile / narrow viewport: sidebar usable | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |

---

## 3. Standard Toolbar (List / CRUD modules)

Verify on sample modules: **Projects**, **Clients**, **Vendor Master**, **Employee Master**, **Material Request**, **Accounts Expenses**.

| # | Test case | Super Admin | Customer Admin | Company Admin | Normal User | Checker | Approver | Issues |
|---|-----------|:-----------:|:--------------:|:-------------:|:-----------:|:-------:|:--------:|--------|
| 3.1 | Toolbar visible: New, View, Edit, Search, Filter, Refresh | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 3.2 | Export Excel downloads data | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 3.3 | Export PDF / Print works on list | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 3.4 | Search filters table rows | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 3.5 | Status filter works (workflow modules) | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 3.6 | Select row → View / Edit enabled | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 3.7 | New opens form panel or new URL | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 3.8 | Refresh reloads list | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 3.9 | Reports link opens reports module (where applicable) | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 3.10 | Delete on toolbar: Super Admin only (Customer Master) | ☐ | — | — | — | — | — | |

---

## 4. CRUD Operations

| # | Test case | Super Admin | Customer Admin | Company Admin | Normal User | Checker | Approver | Issues |
|---|-----------|:-----------:|:--------------:|:-------------:|:-----------:|:-------:|:--------:|--------|
| 4.1 | Create master record (Client / Vendor / Staff) | ☐ | ☐ | ☐ | ☐ | — | — | |
| 4.2 | Edit existing record saves changes | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 4.3 | View read-only mode (no accidental edit) | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 4.4 | Required field validation on save | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 4.5 | Company Master: save legal name, GST, bank (no logo field) | ☐ | ☐ | ☐ | — | ☐ | ☐ | |
| 4.6 | Customer Settings: logo upload + theme only | ☐ | — | — | — | — | — | |
| 4.7 | Pagination on long lists | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |

---

## 5. Workflow (Maker → Checker → Approver)

Test on: **Projects**, **BOQ**, **DPR**, **Material Request**, **Expenses**, **Attendance**.

| # | Test case | Super Admin | Customer Admin | Company Admin | Normal User | Checker | Approver | Issues |
|---|-----------|:-----------:|:--------------:|:-------------:|:-----------:|:-------:|:--------:|--------|
| 5.1 | Maker: Save → Pending Checker | ☐ | ☐ | ☐ | ☐ | — | — | |
| 5.2 | Maker: Edit while Pending Checker | ☐ | ☐ | ☐ | ☐ | — | — | |
| 5.3 | Maker: Delete via row action (pending only) | ☐ | ☐ | ☐ | ☐ | — | — | |
| 5.4 | Checker: Verify → Pending Approval | ☐ | ☐ | ☐ | — | ☐ | — | |
| 5.5 | Checker: Reject with remarks | ☐ | ☐ | ☐ | — | ☐ | — | |
| 5.6 | Approver: Approve → Approved | ☐ | ☐ | ☐ | — | — | ☐ | |
| 5.7 | Approver: Reject with remarks | ☐ | ☐ | ☐ | — | — | ☐ | |
| 5.8 | Approval history timeline visible on view | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 5.9 | Toolbar Delete NOT used for workflow delete (row Actions used) | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |

---

## 6. Reports

| # | Test case | Super Admin | Customer Admin | Company Admin | Normal User | Checker | Approver | Issues |
|---|-----------|:-----------:|:--------------:|:-------------:|:-----------:|:-------:|:--------:|--------|
| 6.1 | Global Reports module opens | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 6.2 | Accounts Reports generate | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 6.3 | Cost Planning Reports | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 6.4 | Client Billing Reports | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 6.5 | Payroll / attendance exports | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 6.6 | Treasury reports (if licensed) | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |

---

## 7. Permissions by Role

| # | Test case | Super Admin | Customer Admin | Company Admin | Normal User | Checker | Approver | Issues |
|---|-----------|:-----------:|:--------------:|:-------------:|:-----------:|:-------:|:--------:|--------|
| 7.1 | Super Admin: Customer Master CRUD + cascade delete | ☐ | — | — | — | — | — | |
| 7.2 | Super Admin: License & limits management | ☐ | — | — | — | — | — | |
| 7.3 | Customer Admin: full tenant modules per package | — | ☐ | — | — | — | — | |
| 7.4 | Company Admin: settings, users, company master | — | — | ☐ | — | — | — | |
| 7.5 | Normal User: maker modules only, no admin settings | — | — | — | ☐ | — | — | |
| 7.6 | Checker: verify/reject, no approve | — | — | — | — | ☐ | — | |
| 7.7 | Approver: final approve/reject | — | — | — | — | — | ☐ | |
| 7.8 | Cross-tenant data isolation (cannot see other customer) | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | |
| 7.9 | Direct URL to admin route blocked for non-admin | — | ☐ | ☐ | ☐ | ☐ | ☐ | |

---

## 8. Sign-off

| Role | Name | Signature | Date | Pass / Fail |
|------|------|-----------|------|-------------|
| Super Admin tester | | | | |
| Customer Admin tester | | | | |
| Company Admin tester | | | | |
| Normal User tester | | | | |
| Checker tester | | | | |
| Approver tester | | | | |
| UAT lead | | | | |

**Overall production sign-off:** ☐ Approved  ☐ Blocked — see issues log

---

## Issues log

| ID | Module | Role | Steps to reproduce | Expected | Actual | Severity |
|----|--------|------|-------------------|----------|--------|----------|
| | | | | | | |
| | | | | | | |
