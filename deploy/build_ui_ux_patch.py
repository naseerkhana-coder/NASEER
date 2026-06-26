#!/usr/bin/env python3
"""Build MAXEK_ERP_UI_UX_patch_<date>.zip for VPS deploy (UI/UX + employee age + billing fixes)."""
from __future__ import annotations

import re
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEPLOY = ROOT / "deploy"
DATE_TAG = datetime.now().strftime("%Y%m%d")
ZIP_PATH = DEPLOY / f"MAXEK_ERP_UI_UX_patch_{DATE_TAG}.zip"
STAGING = DEPLOY / "patch-ui-ux"
VPS_APP = "/var/www/maxek-erp-flask"

FROM_IMPORT_RE = re.compile(r"^from ([a-z_][a-z0-9_]*) import", re.M)

# Explicit UI/UX work-stream files (employee age, standards, shell, petty cash, billing).
PATCH_UI_UX = [
    # Shell config + search
    "ui_shell_config.py",
    "global_search_service.py",
    "erp_platform_routes.py",
    "alert_engine_service.py",
    "badge_counts_service.py",
    "user_context_service.py",
    "dashboard_prefs_service.py",
    "command_center_service.py",
    # Routes / services touched by petty cash & workflow UI
    "treasury_routes.py",
    "treasury_service.py",
    "workflow_service.py",
    "store_service.py",
    "company_master_service.py",
    "budget_service.py",
    "profitability_service.py",
    "client_billing_service.py",
    # Admin / API (app.py imports — required on VPS)
    "super_admin_service.py",
    "erp_admin_routes.py",
    "api_routes.py",
    "ai_routes.py",
    "ai_service.py",
    "auth_jwt.py",
    "tenant_isolation.py",
    "seed_super_admin.py",
    "attachment_service.py",
    "audit_trail_service.py",
    "report_registry.py",
    # CSS standards
    "static/css/maxek-field-standards.css",
    "static/css/maxek-table-standards.css",
    "static/css/maxek-dashboard.css",
    "static/css/maxek-login.css",
    # JS (age, data entry, shell)
    "static/js/dob-age.js",
    "static/js/data-entry.js",
    "static/js/maxek-ui.js",
    "static/js/staff-forms.js",
    "static/js/login.js",
    "static/js/boq-forms.js",
    "static/js/ai-assistant.js",
    "static/images/maxek-logo.png",
    # Shell partials
    "templates/partials/shell_global_search.html",
    "templates/partials/shell_action_panel.html",
    "templates/partials/shell_help_center.html",
    "templates/partials/shell_quick_panel.html",
    "templates/partials/shell_status_strip.html",
    "templates/partials/ai_assistant_panel.html",
    "templates/partials/universal_view_panel.html",
    # Core layout + macros
    "templates/base_maxek.html",
    "templates/macros/erp_ui.html",
    "templates/login.html",
    "templates/dashboard.html",
    # Employee age & data entry masters
    "templates/staff.html",
    "templates/workers.html",
    "templates/purchase_vendors.html",
    # Petty cash & treasury UI
    "templates/petty_cash.html",
    "templates/treasury/alert_engine.html",
    "templates/treasury/alert_settings.html",
    "templates/treasury/hub.html",
    # Client billing fixes
    "templates/client_billing_form.html",
    "templates/client_billing_gst_print.html",
    "templates/client_billing_print.html",
    "templates/dpr_client_bill_print.html",
    # UI-standard template sweep (git-modified)
    "templates/accounts_payment_voucher.html",
    "templates/attendance.html",
    "templates/bbs_print.html",
    "templates/boq.html",
    "templates/clients.html",
    "templates/cost_planning.html",
    "templates/dpr.html",
    "templates/employee_timesheet_print.html",
    "templates/material_request.html",
    "templates/payroll.html",
    "templates/payroll_print_slip.html",
    "templates/payroll_run_print.html",
    "templates/plant_asphalt_dispatch_print.html",
    "templates/plant_rmc_dispatch_print.html",
    "templates/projects.html",
    "templates/purchase_order_print.html",
    "templates/purchase_orders.html",
    "templates/settings.html",
    "templates/store_grn.html",
    "templates/store_materials.html",
    "templates/sub_billing_print.html",
    "templates/vehicle_print.html",
    # Deploy helpers
    "deploy/migrate_production.py",
    "deploy/fix_petty_cash_db.sql",
    "requirements.txt",
    "wsgi.py",
]


def app_direct_root_modules() -> set[str]:
    text = (ROOT / "app.py").read_text(encoding="utf-8", errors="replace")
    files: set[str] = set()
    for mod in FROM_IMPORT_RE.findall(text):
        path = ROOT / f"{mod}.py"
        if path.is_file():
            files.add(f"{mod}.py")
    return files


def collect_files() -> list[str]:
    files: set[str] = set(app_direct_root_modules())
    files.add("app.py")
    for rel in PATCH_UI_UX:
        path = ROOT / rel.replace("/", "\\") if "\\" in str(ROOT) else ROOT / rel
        if path.is_file():
            files.add(rel.replace("\\", "/"))
        else:
            print(f"WARN: missing (skipped): {rel}")
    return sorted(files)


def write_deploy_readme(file_list: list[str]) -> str:
    lines = [
        "MAXEK ERP — UI/UX PATCH DEPLOY",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Package: {ZIP_PATH.name}",
        f"Files: {len(file_list)}",
        "",
        "WORK STREAMS INCLUDED",
        "-" * 60,
        "1. Employee age & data entry (dob-age.js, data-entry.js, staff/workers/purchase_vendors/base_maxek)",
        "2. Final UI/UX standards (field/table CSS, shell partials, maxek-ui.js, ui_shell_config.py, petty_cash, alert_engine, macros)",
        "3. Client billing print/form fixes",
        "",
        "VPS TARGET ROOT",
        "-" * 60,
        VPS_APP,
        "",
        "FILE LIST (local relative path -> VPS path)",
        "-" * 60,
    ]
    for i, rel in enumerate(file_list, 1):
        lines.append(f"  {i:3}. {rel}  ->  {VPS_APP}/{rel}")
    lines.extend(
        [
            "",
            "UPLOAD (from Windows PowerShell)",
            "-" * 60,
            f"scp deploy/{ZIP_PATH.name} root@srv1704727:/tmp/",
            "",
            "APPLY ON VPS (SSH)",
            "-" * 60,
            f"cd {VPS_APP}",
            "sudo cp -a database/maxek.db database/maxek.db.bak-$(date +%Y%m%d%H%M)  # optional backup",
            f"sudo unzip -o /tmp/{ZIP_PATH.name} -d {VPS_APP}",
            "source venv/bin/activate",
            "export MAXEK_SKIP_DEMO_SEED=1",
            "python deploy/migrate_production.py",
            f"sudo chown -R www-data:www-data {VPS_APP}/app.py {VPS_APP}/templates {VPS_APP}/static {VPS_APP}/*.py",
            "sudo systemctl restart maxek-erp",
            "sudo systemctl status maxek-erp --no-pager",
            "",
            "ONE-LINE DEPLOY (after scp to /tmp/)",
            "-" * 60,
            f"cd {VPS_APP} && sudo unzip -o /tmp/{ZIP_PATH.name} -d {VPS_APP} && source venv/bin/activate && export MAXEK_SKIP_DEMO_SEED=1 && python deploy/migrate_production.py && sudo chown -R www-data:www-data app.py templates static *.py && sudo systemctl restart maxek-erp",
            "",
            "BROWSER — HARD REFRESH CSS/JS CACHE",
            "-" * 60,
            "After deploy, hard-refresh each browser session: Ctrl+Shift+R (Windows) or Cmd+Shift+R (Mac).",
            "base_maxek.html cache-bust query params: ?v=20260623-fieldwidth / ?v=20260623-ux / ?v=20260623-shell",
            "",
            "VERIFY",
            "-" * 60,
            "1. App loads (no 502) — confirms app.py + service imports match",
            "2. Staff/Workers: DOB shows computed age; data-entry tab order works",
            "3. Global search (Ctrl+K) opens from header",
            "4. Petty cash + Treasury > Alert engine pages render with new table/field standards",
            "5. Client billing form + print layouts",
        ]
    )
    return "\n".join(lines) + "\n"


def stage_folder(file_list: list[str], readme: str) -> None:
    if STAGING.exists():
        import shutil

        shutil.rmtree(STAGING)
    for rel in file_list:
        src = ROOT / rel
        dest = STAGING / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
    (STAGING / "DEPLOY_README.txt").write_text(readme, encoding="utf-8")


def build() -> None:
    file_list = collect_files()
    readme = write_deploy_readme(file_list)

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in file_list:
            zf.write(ROOT / rel, rel)
        zf.writestr("DEPLOY_README.txt", readme)

    stage_folder(file_list, readme)
    (DEPLOY / "DEPLOY_README_UI_UX.txt").write_text(readme, encoding="utf-8")

    size_kb = ZIP_PATH.stat().st_size / 1024
    print(f"ZIP: {ZIP_PATH}")
    print(f"Staging: {STAGING}")
    print(f"Files in zip: {len(file_list)} (+ DEPLOY_README.txt)")
    print(f"Size: {size_kb:.1f} KB")


if __name__ == "__main__":
    build()
