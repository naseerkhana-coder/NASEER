#!/usr/bin/env python3
"""Build deploy/dist/vps-patch-v1.0.1-hotfix.zip — platform admin security + workflow exempt."""
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
    "workflow_service.py",
    "ui_shell_config.py",
    "erp_admin_routes.py",
    "dashboard_prefs_service.py",
    "standard_boq_library_service.py",
    "templates/settings.html",
    "templates/erp_admin/customers.html",
    "templates/erp_admin/licenses.html",
    "templates/erp_admin/subscriptions.html",
    "templates/erp_admin/change_requests.html",
    "templates/erp_admin/support_tickets.html",
    "templates/erp_admin/platform_dashboard.html",
    "templates/erp_admin/customer_settings.html",
    "templates/macros/erp_ui.html",
    "templates/partials/dashboard_shell_sidebar.html",
    "templates/dashboard.html",
    "templates/dashboard_theme_executive.html",
    "templates/dashboard_theme_compact.html",
    "templates/partials/command_centre_dept_tiles.html",
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
        "MAXEK ERP — VPS Patch v1.0.1 Hotfix (platform admin security)",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Archive: deploy/dist/vps-patch-v1.0.1-hotfix.zip",
        "",
        "Purpose",
        "-------",
        "  1. Platform menu + /erp-admin/* + /super-admin/* restricted to Platform Super Admin (403 otherwise)",
        "  2. Platform admin modules save immediately — no maker/checker/approver workflow",
        "  3. Dashboard theme + department tiles fixes from prior hotfix retained",
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
