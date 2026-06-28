#!/usr/bin/env python3
"""Smoke-test v1.0.1 hotfix routes/templates."""
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

results = []


def ok(name, detail=""):
    results.append((name, True, detail))


def fail(name, detail=""):
    results.append((name, False, detail))


try:
    from app import app, get_db
    from super_admin_service import ensure_super_admin_schema, save_license, list_licenses

    with app.app_context():
        db = get_db()
        ensure_super_admin_schema(db)
        db.commit()

        with app.test_request_context():
            from flask import url_for

            for ep in (
                "accounts_receipts",
                "accounts_cash_book_v2",
                "accounts_bank_book_v2",
                "accounts_day_book",
                "accounts_general_ledger",
                "accounts_hub",
                "erp_admin_licenses",
            ):
                try:
                    url_for(ep)
                    ok(f"url_for:{ep}")
                except Exception as exc:
                    fail(f"url_for:{ep}", str(exc))

            bad_eps = ("accounts_receipt_voucher", "accounts_book_v2", "accounts_book")
            for ep in bad_eps:
                try:
                    url_for(ep)
                    fail(f"missing_endpoint:{ep}", "should not exist")
                except Exception:
                    ok(f"missing_endpoint:{ep}", "BuildError expected")

        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["user_id"] = 1
                sess["username"] = "superadmin"
                sess["role"] = "Super Admin"

            for path in (
                "/accounts/receipts",
                "/accounts/cash-book-v2",
                "/accounts/bank-book-v2",
                "/accounts/day-book",
                "/accounts/general-ledger",
                "/accounts/tds",
                "/erp-admin/licenses",
            ):
                try:
                    resp = client.get(path, follow_redirects=False)
                    if resp.status_code >= 500:
                        fail(f"GET {path}", f"status={resp.status_code}")
                    else:
                        ok(f"GET {path}", f"status={resp.status_code}")
                except Exception as exc:
                    fail(f"GET {path}", traceback.format_exc()[-400:])

            try:
                resp = client.post(
                    "/erp-admin/licenses",
                    data={
                        "license_no": "TEST-LIC-001",
                        "customer_code": "INVALID999",
                        "product": "MAXEK ERP",
                        "plan": "Standard",
                        "status": "Active",
                    },
                    follow_redirects=False,
                )
                if resp.status_code >= 500:
                    fail("POST licenses invalid customer", f"status={resp.status_code}")
                else:
                    ok("POST licenses invalid customer", f"status={resp.status_code}")
            except Exception as exc:
                fail("POST licenses", str(exc))

            for path in ("/login/branding?company_code=INVALID999", "/login/branding"):
                try:
                    resp = client.get(path, follow_redirects=False)
                    if resp.status_code >= 500:
                        fail(f"GET {path}", f"status={resp.status_code}")
                    else:
                        ok(f"GET {path}", f"status={resp.status_code}")
                except Exception as exc:
                    fail(f"GET {path}", traceback.format_exc()[-400:])

except Exception as exc:
    fail("import/setup", traceback.format_exc())

for name, passed, detail in results:
    mark = "PASS" if passed else "FAIL"
    print(f"{mark}: {name}" + (f" — {detail}" if detail else ""))

sys.exit(0 if all(p for _, p, _ in results) else 1)
