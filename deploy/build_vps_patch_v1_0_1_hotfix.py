#!/usr/bin/env python3
"""Build deploy/dist/vps-patch-v1.0.1-hotfix.zip — UAT hotfix bundle."""
from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "deploy" / "dist"
ZIP_PATH = DIST / "vps-patch-v1.0.1-hotfix.zip"
MANIFEST_PATH = DIST / "VPS-PATCH-V1.0.1-HOTFIX-MANIFEST.txt"
VPS_APP = "/var/www/maxek-erp-flask"

HOTFIX_FILES = [
    "app.py",
    "api_routes.py",
    "super_admin_service.py",
    "user_context_service.py",
    "tenant_isolation.py",
    "erp_platform_routes.py",
    "workflow_service.py",
    "badge_counts_service.py",
    "ui_shell_config.py",
    "erp_admin_routes.py",
    "dashboard_prefs_service.py",
    "standard_boq_library_service.py",
    "templates/settings.html",
    "templates/accounts_receipt_voucher.html",
    "templates/accounts_book.html",
    "templates/accounts_book_v2.html",
    "templates/accounts_tds_register.html",
    "templates/erp_admin/customers.html",
    "templates/erp_admin/licenses.html",
    "templates/erp_admin/subscriptions.html",
    "templates/erp_admin/change_requests.html",
    "templates/erp_admin/support_tickets.html",
    "templates/erp_admin/platform_dashboard.html",
    "templates/erp_admin/customer_settings.html",
    "templates/macros/erp_ui.html",
    "templates/partials/dashboard_shell_sidebar.html",
    "templates/partials/dashboard_shell_header.html",
    "templates/partials/dashboard_shell_module_header.html",
    "templates/partials/command_centre_dept_tiles.html",
    "templates/partials/workflow_approval_cards.html",
    "templates/dashboard.html",
    "templates/dashboard_theme_executive.html",
    "templates/dashboard_theme_compact.html",
    "static/css/maxek-dashboard.css",
    "static/js/maxek-ui.js",
]


def build() -> None:
    DIST.mkdir(parents=True, exist_ok=True)
    missing = [rel for rel in HOTFIX_FILES if not (ROOT / rel).is_file()]
    if missing:
        raise SystemExit(f"Missing hotfix files: {missing}")

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in HOTFIX_FILES:
            zf.write(ROOT / rel, rel)

    lines = [
        "MAXEK ERP — VPS Patch v1.0.1 Hotfix (UAT fixes)",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Archive: deploy/dist/vps-patch-v1.0.1-hotfix.zip",
        "",
        "Purpose",
        "-------",
        "  1. Fix Accounts module 500 errors (broken url_for in book/receipt templates)",
        "  2. Fix License Registration page (toolbar URL, form panel, edit/delete)",
        "  3. Shared toolbar: disable Open/View/Edit/Delete until row selected;",
        "     Delete enabled for Platform Super Admin only",
        "  4. TDS register back button → Accounts dashboard",
        "  5. Customer Master package panel dark theme",
        "  6. Remove header progress bar; platform dashboard UI refresh",
        "  7. Platform admin security + workflow exempt (prior hotfix retained)",
        "  8. Fix login branding API (sqlite3.Row .get AttributeError on VPS)",
        "  9. Workflow: approved projects stay tenant-visible (customer_id + status=Active)",
        " 10. Checker / approver dashboard pending-approval module cards (tenant-scoped)",
        " 11. Add /erp/dashboard alias redirect to /dashboard (legacy/nginx URL compatibility)",
        "",
        "Files in archive",
        "----------------",
    ]
    for rel in HOTFIX_FILES:
        lines.append(f"  {rel}")

    lines.extend(
        [
            "",
            "Deployment",
            "----------",
            "Extract zip at application root (preserve paths). Restart gunicorn/uwsgi.",
            "No database schema changes required.",
            "",
            "LOCAL -> VPS",
            "-" * 80,
        ]
    )
    for i, rel in enumerate(HOTFIX_FILES, 1):
        lines.append(f"  {i:2}. {ROOT / rel} -> {VPS_APP}/{rel}")

    MANIFEST_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"ZIP: {ZIP_PATH} ({ZIP_PATH.stat().st_size} bytes, {len(HOTFIX_FILES)} files)")
    print(f"Manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    build()
