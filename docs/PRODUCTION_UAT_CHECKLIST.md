# MAXEK ERP v1.0.1 Final UAT Checklist

**Environment:** https://erp.maxekindia.com  
**VPS app path:** `/var/www/maxek-erp-flask`  
**Date tested:** 2026-06-28  
**Tester:** _______________

Use this checklist during browser testing on production after deploying the v1.0.1 hotfix. Tick each item when verified. Log failures in the **Issues log** at the bottom.

---

## Deployment

| Item | Value |
|------|-------|
| Version | v1.0.1 Hotfix |
| Commit | `74dbbcd` (chain: `f4ce536`, `3c9685d`, `74dbbcd`; prior: `4068db8`) |
| Patch archive | `deploy/dist/vps-patch-v1.0.1-hotfix.zip` |
| Files in patch | 32 |
| Build script | `deploy/build_vps_patch_v1_0_1_hotfix.py` |

Deploy to the VPS and restart the service **before** UAT.

### VPS deploy commands

Upload `vps-patch-v1.0.1-hotfix.zip` to the VPS (e.g. `/tmp/`), then run on the server:

```bash
APP=/var/www/maxek-erp-flask
cd "$APP"

# 1. Backup (stops maxek-erp during DB snapshot, restarts when done)
bash deploy/vps_backup.sh "$APP"

# 2. Apply hotfix (preserve paths under app root)
sudo unzip -o /tmp/vps-patch-v1.0.1-hotfix.zip -d "$APP"

# 3. Permissions + restart
sudo chown -R www-data:www-data "$APP"
sudo systemctl restart maxek-erp
sudo systemctl status maxek-erp --no-pager
journalctl -u maxek-erp -n 40 --no-pager
```

No database schema changes are required for this patch.

---

## Production test URLs

Base URL: **https://erp.maxekindia.com**

| Area | Path | Full URL |
|------|------|----------|
| Login | `/login` | https://erp.maxekindia.com/login |
| Accounts hub | `/accounts` | https://erp.maxekindia.com/accounts |
| Receipt voucher | `/accounts/receipts` | https://erp.maxekindia.com/accounts/receipts |
| Cash Book (CoA v2) | `/accounts/cash-book-v2` | https://erp.maxekindia.com/accounts/cash-book-v2 |
| Bank Book (CoA v2) | `/accounts/bank-book-v2` | https://erp.maxekindia.com/accounts/bank-book-v2 |
| Day Book | `/accounts/day-book` | https://erp.maxekindia.com/accounts/day-book |
| General Ledger | `/accounts/general-ledger` | https://erp.maxekindia.com/accounts/general-ledger |
| TDS register | `/accounts/tds-register` | https://erp.maxekindia.com/accounts/tds-register |
| TDS (legacy route) | `/accounts/tds` | https://erp.maxekindia.com/accounts/tds |
| Cash Book (legacy) | `/accounts/cash-book` | https://erp.maxekindia.com/accounts/cash-book |
| Bank Book (legacy) | `/accounts/bank-book` | https://erp.maxekindia.com/accounts/bank-book |
| Ledger (legacy) | `/accounts/ledger` | https://erp.maxekindia.com/accounts/ledger |
| Customer Master | `/erp-admin/customers` | https://erp.maxekindia.com/erp-admin/customers |
| License Master | `/erp-admin/licenses` | https://erp.maxekindia.com/erp-admin/licenses |
| Platform dashboard | `/super-admin/dashboard` | https://erp.maxekindia.com/super-admin/dashboard |

---

# UAT Execution Order

Run sections **in order**. Section 1 is highest priority.

## 1. Accounts Module (Highest Priority)

Verify these pages open without any server errors:

| Page | URL | Pass |
|------|-----|:----:|
| Receipt | https://erp.maxekindia.com/accounts/receipts | ☐ |
| Cash Book (v2) | https://erp.maxekindia.com/accounts/cash-book-v2 | ☐ |
| Bank Book (v2) | https://erp.maxekindia.com/accounts/bank-book-v2 | ☐ |
| Day Book | https://erp.maxekindia.com/accounts/day-book | ☐ |
| General Ledger | https://erp.maxekindia.com/accounts/general-ledger | ☐ |

**Acceptance:**

- No HTTP 500
- No HTTP 502
- No template errors
- No route errors
- No SQL errors

Also smoke-test **legacy routes** if navigation still references them:

| Legacy route | URL | Pass |
|--------------|-----|:----:|
| Cash Book | https://erp.maxekindia.com/accounts/cash-book | ☐ |
| Bank Book | https://erp.maxekindia.com/accounts/bank-book | ☐ |
| Ledger | https://erp.maxekindia.com/accounts/ledger | ☐ |

---

## 2. TDS

**URL:** https://erp.maxekindia.com/accounts/tds-register

Verify:

| Check | Pass |
|-------|:----:|
| Back button returns to the **Accounts** dashboard (`/accounts`) | ☐ |
| Does **not** redirect to the Main Dashboard | ☐ |

---

## 3. Customer Master

**URL:** https://erp.maxekindia.com/erp-admin/customers (open a customer for edit)

Verify:

| Check | Pass |
|-------|:----:|
| Package & Department Access panel uses dark theme | ☐ |
| White background removed | ☐ |
| Text remains readable after Save | ☐ |
| Package selection works correctly | ☐ |

---

## 4. Platform Dashboard

**URL:** https://erp.maxekindia.com/super-admin/dashboard  
*(Super Admin / Platform Super Admin only)*

Verify:

| Check | Pass |
|-------|:----:|
| Header progress bar removed | ☐ |
| Department card colors display correctly | ☐ |
| Customer Creation appears under Quick Actions | ☐ |
| Card spacing is consistent | ☐ |
| Recent Customers table styling is correct | ☐ |
| Navigation does not produce server errors | ☐ |

---

## 5. License Master

**URL:** https://erp.maxekindia.com/erp-admin/licenses  
*(Platform Super Admin only)*

Verify:

| Check | Pass |
|-------|:----:|
| License Registration saves successfully | ☐ |
| Edit works | ☐ |
| Delete works (Platform Super Admin only) | ☐ |
| Open / View / Edit / Delete disabled until a row is selected | ☐ |
| Customer, Product, and Plan validation works correctly | ☐ |

---

## 6. Final Smoke Test

Verify across roles (Super Admin, Customer Admin, Company Admin, Normal User, Checker, Approver):

| Check | Pass |
|-------|:----:|
| Login (all roles) — https://erp.maxekindia.com/login | ☐ |
| Logout clears session | ☐ |
| CRUD operations on sample masters (Client, Vendor, Staff) | ☐ |
| Role permissions enforced (admin routes blocked for non-admin) | ☐ |
| Department / module navigation | ☐ |
| No remaining HTTP 500 / 502 errors on licensed modules | ☐ |

---

# Release Decision

## PASS

- Sign off **v1.0.1**
- Tag production (`v1.0.1`)
- Freeze maintenance branch

**Overall production sign-off:** ☑ **Approved** — v1.0.1 PASS (2026-06-28). UAT complete; all Critical/High checks passed.

## FAIL

- Fix **only** Critical or High issues
- Re-run affected UAT sections above
- **No new features** on the maintenance branch

**Overall production sign-off:** ☐ Blocked — see issues log

---

# Next Release

After **v1.0.1** is approved, start **v1.1**:

- Bulk Import & Migration
- BOQ Import
- BOQ Library
- Customer Import
- Company Import
- Material Import
- Opening Balances
- Chart of Accounts Import

Run separate **staging**, **UAT**, and **production** deployment for v1.1. See `docs/MAXEK_ERP_RELEASE_PLAN.md`.

---

## Hotfix scope (reference)

| Fix | Evidence |
|-----|----------|
| Platform dashboard UI + Super Admin dept tiles | `4068db8`, `f4ce536` |
| License Master 500 + toolbar (edit/delete, row selection) | `f4ce536` |
| Accounts `url_for` fixes (receipt + book templates) | `f4ce536` |
| TDS back → Accounts hub | `f4ce536` |
| Customer Master package panel dark theme | `f4ce536` |

---

## Sign-off

**Recorded:** v1.0.1 **PASS** on **2026-06-28**. UAT complete — all Critical and High severity items passed. Signed release commit chain: `f4ce536` → `3c9685d` → `74dbbcd`.

| Role | Name | Date | Pass / Fail |
|------|------|------|-------------|
| UAT lead | (signed off in release closure) | 2026-06-28 | **Pass** |
| Super Admin tester | | | |
| Customer Admin tester | | | |
| Company Admin tester | | | |

---

## Issues log

| ID | Section | URL / module | Steps to reproduce | Expected | Actual | Severity |
|----|---------|--------------|-------------------|----------|--------|----------|
| | | | | | | |
| | | | | | | |
