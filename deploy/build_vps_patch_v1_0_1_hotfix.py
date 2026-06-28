#!/usr/bin/env python3
"""Build deploy/dist/vps-patch-v1.0.1-hotfix.zip — dashboard settings + all dept tiles."""
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
    "dashboard_prefs_service.py",
    "user_context_service.py",
    "erp_admin_routes.py",
    "erp_platform_routes.py",
    "standard_boq_library_service.py",
    "templates/settings.html",
    "templates/erp_admin/customer_settings.html",
    "templates/erp_admin/platform_dashboard.html",
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
        "MAXEK ERP — VPS Patch v1.0.1 Hotfix (revised)",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Archive: deploy/dist/vps-patch-v1.0.1-hotfix.zip",
        "",
        "Purpose",
        "-------",
        "Fix production UAT issues after initial v1.0.1 hotfix:",
        "  1. Dashboard theme settings (Settings + Customer Settings templates/services)",
        "  2. Main dashboard shows all 14 department tiles (locked when not subscribed)",
        "  3. Super Admin two-level dashboard (Platform + Company ERP when company selected)",
        "  4. WSGI-safe bulk import registration (try/except in app.py)",
        "",
        "Root cause",
        "----------",
        "Initial hotfix zip deployed app.py only. VPS kept older templates without",
        "dashboard_layout_theme / dashboard_theme UI. Department tiles were filtered by",
        "subscription enabled_departments and user favorite_modules preferences.",
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
            "Schema columns (dashboard_theme, dashboard_layout_theme) auto-migrate on boot.",
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
