#!/usr/bin/env python3
"""Build deploy/dist/vps-patch-latest.zip with all app.py root imports + MR/PR UI files."""
from __future__ import annotations

import re
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "deploy" / "dist"
ZIP_PATH = DIST / "vps-patch-latest.zip"
MANIFEST_PATH = DIST / "VPS-PATCH-LATEST-MANIFEST.txt"
VPS_APP = "/var/www/maxek-erp-flask"

# Last VPS bundle doc commit; auto-include template/static changes since then.
STABILIZATION_BASELINE_COMMIT = "1edd62e"


def stabilization_bundle_paths() -> list[str]:
    """Production templates/static changed since last deploy bundle (final stabilization)."""
    import subprocess

    try:
        out = subprocess.check_output(
            [
                "git",
                "diff",
                f"{STABILIZATION_BASELINE_COMMIT}..HEAD",
                "--name-only",
            ],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    rels: list[str] = []
    for line in out.splitlines():
        line = line.strip().replace("\\", "/")
        if not line.startswith(("templates/", "static/")):
            continue
        if line.startswith(("tests/", "scripts/")):
            continue
        p = ROOT / line
        if p.is_file():
            rels.append(line)
    return rels


# Final Stabilization Bundle (excludes aborted bulk import 410b68f5 — superseded by this commit)
STABILIZATION_COMMITS = (
    "32788c9",  # Standard Toolbar Rollout
    "a4ca636",  # Dashboard Themes
    "2e10ed5",  # User Permission Management
)

# Bulk import module (separate from stabilization bundle — include explicitly)
BULK_IMPORT_PATCH = [
    "bulk_import_service.py",
    "import_audit_service.py",
    "standard_boq_library_service.py",
    "boq_import_service.py",
    "bulk_import_routes.py",
    "library_service.py",
    "templates/boq.html",
    "templates/boq_library.html",
    "templates/erp_admin/migration_wizard.html",
    "templates/erp_admin/customers.html",
    "static/js/boq-import.js",
    "static/js/boq-forms.js",
    "docs/BULK_IMPORT_MIGRATION.md",
    "tests/test_bulk_import.py",
]
STABILIZATION_BASE = "114de03"

FROM_IMPORT_RE = re.compile(r"^from ([a-z_][a-z0-9_]*) import", re.M)

# UI + deploy helpers beyond Python modules (MR/PR view/edit, store/vendor, base layout).
PATCH_UI = [
    "templates/base_maxek.html",
    "templates/dashboard.html",
    "templates/department_dashboard.html",
    "templates/department_workspace.html",
    "templates/material_request.html",
    "templates/module_request.html",
    "templates/macros/erp_ui.html",
    "templates/store_materials.html",
    "templates/store_grn.html",
    "templates/purchase_vendors.html",
    "templates/purchase_orders.html",
    "templates/purchase_request.html",
    "templates/subcontractors.html",
    "templates/projects.html",
    "templates/clients.html",
    "templates/staff.html",
    "templates/users.html",
    "templates/workers.html",
    "templates/login.html",
    "templates/company_master.html",
    "templates/reports.html",
    "templates/cost_planning.html",
    "templates/qc_master.html",
    "templates/fleet_vehicles.html",
    "templates/plant_master.html",
    "templates/accounts_payment_voucher.html",
    "templates/erp_admin/customers.html",
    "templates/erp_admin/customer_settings.html",
    "templates/erp_admin/platform_dashboard.html",
    "templates/settings.html",
    "templates/user_management.html",
    "templates/dashboard_theme_compact.html",
    "templates/dashboard_theme_executive.html",
    "static/css/maxek-login.css",
    "static/js/login.js",
    "static/css/maxek-table-standards.css",
    "static/css/maxek-field-standards.css",
    "templates/boq.html",
    "templates/dpr.html",
    "templates/attendance.html",
    "static/js/attendance-form.js",
    "static/js/attendance-monthly.js",
    "static/js/data-entry.js",
    "static/css/maxek-dashboard.css",
    "static/js/master-forms.js",
    "static/js/boq-forms.js",
    "static/js/subcontractors.js",
    "static/js/maxek-ui.js",
    "deploy/migrate_production.py",
    "deploy/VPS_PATCH_maxek-erp-flask.txt",
    "docs/PRODUCTION_UAT_CHECKLIST.md",
    "docs/DASHBOARD_THEMES.md",
]

REQUIRED_PY = (
    "app.py",
    "erp_framework.py",
    "super_admin_service.py",
    "store_service.py",
    "workflow_service.py",
    "erp_admin_routes.py",
    "api_routes.py",
    "tenant_isolation.py",
    "auth_jwt.py",
    "user_permission_service.py",
    "user_context_service.py",
    "dashboard_prefs_service.py",
)


def git_diff_paths(base: str, head: str = "HEAD") -> list[str]:
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", f"{base}..{head}"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    return [line.strip().replace("\\", "/") for line in out.splitlines() if line.strip()]


def stabilization_deploy_paths() -> set[str]:
    """Deployable paths from stabilization commits; skip dev-only trees."""
    skip_prefixes = ("scripts/", "tests/", "docs/COMPANY")
    paths: set[str] = set()
    for rel in git_diff_paths(STABILIZATION_BASE):
        if rel.startswith(skip_prefixes):
            continue
        if rel.endswith(".py") and "/" not in rel:
            paths.add(rel)
            continue
        if rel.startswith(("templates/", "static/")):
            paths.add(rel)
    return paths


def app_direct_root_modules() -> set[str]:
    """Every top-level .py module imported directly by app.py."""
    text = (ROOT / "app.py").read_text(encoding="utf-8", errors="replace")
    files: set[str] = set()
    for mod in FROM_IMPORT_RE.findall(text):
        path = ROOT / f"{mod}.py"
        if path.is_file():
            files.add(f"{mod}.py")
    return files


def collect_files() -> list[str]:
    files = app_direct_root_modules()
    files.add("app.py")
    if (ROOT / "wsgi.py").is_file():
        files.add("wsgi.py")
    for name in REQUIRED_PY:
        if (ROOT / name).is_file():
            files.add(name)
    files |= stabilization_deploy_paths()
    for rel in PATCH_UI:
        path = ROOT / rel
        if path.is_file():
            files.add(rel.replace("\\", "/"))
        else:
            print(f"WARN: patch UI file missing (skipped): {rel}")
    for rel in stabilization_bundle_paths():
        files.add(rel)
    for rel in BULK_IMPORT_PATCH:
        if (ROOT / rel).is_file():
            files.add(rel.replace("\\", "/"))
    return sorted(files)


def build() -> None:
    DIST.mkdir(parents=True, exist_ok=True)
    files = collect_files()

    missing_required = [name for name in REQUIRED_PY if name not in files]
    if missing_required:
        raise SystemExit(f"Patch set missing required modules: {missing_required}")

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            zf.write(ROOT / rel, rel)

    size = ZIP_PATH.stat().st_size
    lines = [
        "MAXEK ERP VPS patch (vps-patch-latest)",
        "Bundle: Final Stabilization + Bulk Import & Migration module",
        f"Stabilization commits: {', '.join(STABILIZATION_COMMITS)}",
        "Bulk import: separate feature bundle (not part of 410b68f5 aborted attempt)",
        f"Generated: {datetime.now().isoformat()}",
        f"Production files: {len(files)}",
        f"Zip: {ZIP_PATH}",
        f"Size bytes: {size}",
        "",
        "Includes ALL app.py root imports plus stabilization templates/static.",
        "",
        "LOCAL -> VPS",
        "-" * 80,
    ]
    for i, rel in enumerate(files, 1):
        local = ROOT / rel
        lines.append(f"  {i:2}. {local} -> {VPS_APP}/{rel}")

    MANIFEST_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"ZIP: {ZIP_PATH}")
    print(f"Files: {len(files)}")
    print(f"Size: {size} bytes")
    print(f"Manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    build()
