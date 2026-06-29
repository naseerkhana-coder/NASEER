#!/usr/bin/env python3
"""Build deploy/vps-patch-v1.1-sprint2.zip — Sprint 2 scoped VPS patch only."""
from __future__ import annotations

import os
import subprocess
import zipfile
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPLOY = os.path.join(ROOT, "deploy")
ZIP_NAME = "vps-patch-v1.1-sprint2.zip"
ZIP_PATH = os.path.join(DEPLOY, ZIP_NAME)
MANIFEST_PATH = os.path.join(DEPLOY, "vps-patch-v1.1-sprint2_MANIFEST.txt")
DEPLOY_DOC = os.path.join(DEPLOY, "VPS_DEPLOY_v1.1_Sprint2.md")

PATCH_FILES = [
    "app.py",
    "accounts_import_service.py",
    "boq_import_service.py",
    "bulk_import_routes.py",
    "data_import_registry.py",
    "data_import_routes.py",
    "import_audit_service.py",
    "import_tenant_helpers.py",
    "master_library_import_service.py",
    "master_library_service.py",
    "standard_boq_library_import_service.py",
    "standard_boq_library_service.py",
    "templates/boq_library.html",
    "tenant_isolation.py",
    "user_context_service.py",
    "tests/test_bulk_import.py",
    "scripts/build_sample_data_templates.py",
    "docs/V1_1_BULK_IMPORT_SPEC.md",
    "docs/samples/v1.1-import/README.md",
    "templates/data_import/audit_log.html",
    "templates/data_import/hub.html",
    "templates/data_import/migration_wizard.html",
    "templates/data_import/module_import.html",
    "sample_data/README.md",
    "sample_data/BOQ.xlsx",
    "sample_data/COA.xlsx",
    "sample_data/Customer_Master.xlsx",
    "sample_data/Employee_Master.xlsx",
    "sample_data/Labour_Master.xlsx",
    "sample_data/Machinery_Master.xlsx",
    "sample_data/Material_Master.xlsx",
    "sample_data/Opening_Balance.xlsx",
    "sample_data/Productivity.xlsx",
    "sample_data/Rate_Master.xlsx",
    "sample_data/Vendor_Master.xlsx",
    "sample_data/WBS_Template.xlsx",
    "deploy/VPS_DEPLOY_v1.1_Sprint2.md",
    "deploy/vps-patch-v1.1-sprint2_PACKAGE_README.txt",
]

def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"




def write_deploy_doc(commit: str, entries: list[tuple[str, int]], zip_size: int) -> None:
    file_lines = "\n".join(f"- `{arc}` ({size} bytes)" for arc, size in sorted(entries))
    body = f"""# VPS deploy — MAXEK ERP v1.1 Sprint 2 (partial patch)

**Branch:** `release/v1.1`  
**Git commit:** `{commit}`  
**Package:** `deploy/vps-patch-v1.1-sprint2.zip` ({zip_size} bytes)  
**Baseline on VPS:** v1.0.2 / frozen main overlay

Scope: master library imports, import audit + rollback payloads, tenant helpers, bulk import routes/UI. Sales/Purchase/Payment import modules remain registry stubs only (not implemented in this patch).

## 1. Backup (VPS)

```bash
cd /var/www/maxek-erp-flask
sudo mkdir -p /var/backups/maxek-erp
sudo cp -a database/maxek.db "/var/backups/maxek-erp/maxek.db.$(date +%Y%m%d_%H%M%S)"
```

Do **not** overwrite production `.env` or `database/*.db` when applying the patch.

## 2. Upload and apply

From Windows:

```powershell
scp "deploy/vps-patch-v1.1-sprint2.zip" root@72.61.224.204:/tmp/
```

On VPS:

```bash
cd /var/www/maxek-erp-flask
sudo unzip -o /tmp/vps-patch-v1.1-sprint2.zip -d /tmp/sprint2-patch
sudo rsync -av --exclude='.env' --exclude='database/' --exclude='venv/' /tmp/sprint2-patch/ /var/www/maxek-erp-flask/
sudo chown -R www-data:www-data /var/www/maxek-erp-flask
sudo systemctl restart maxek-erp
sudo systemctl status maxek-erp --no-pager
```

## 3. Schema / migrations (lazy)

No standalone SQL migration script in this patch. Schemas are ensured on first use:

| Trigger | Function |
|---------|----------|
| `/data-import/audit` | `ensure_import_audit_schema` — creates/extends `import_audit_log` including `rollback_payload` |
| Master library imports | `ensure_master_library_schemas` in `master_library_service` |
| Standard BOQ library | existing `ensure_standard_boq_library_schema` on `/boq-library` |
| Materials import | `ensure_store_schema` via store service |

## 4. Rollback

**Application rollback (single import):** Data Import → Audit log → Rollback on rows that recorded `rollback_payload` at import time (`rollback_import` in `import_audit_service.py`).

**Deploy rollback (revert code):** Restore previous file tree from git tag/backup zip; restore `database/maxek.db` from backup if imports were applied.

## 5. UAT checklist

- [ ] Login as tenant admin; open **Data Import** hub — master modules visible; Sales/Purchase/Payment show as not ready (stubs).
- [ ] Import a small **Material** or **Rate** sample; confirm success counts and audit row.
- [ ] Open **Audit log**; verify entry; run **Rollback** on test import; confirm rows removed/reverted.
- [ ] **BOQ library** page loads; standard BOQ import path still works.
- [ ] `pytest tests/test_bulk_import.py -q` on staging (optional on VPS if venv has pytest).

## 6. Files in this patch

{file_lines}

See also: `deploy/vps-patch-v1.1-sprint2_MANIFEST.txt` and `deploy/vps-patch-v1.1-sprint2_PACKAGE_README.txt`.
"""
    DEPLOY_DOC.write_text(body.replace("{file_lines}", file_lines), encoding="utf-8", newline="\n")

def main() -> None:
    commit = git_commit()
    entries: list[tuple[str, int]] = []
    missing: list[str] = []

    os.makedirs(DEPLOY, exist_ok=True)
    if os.path.isfile(ZIP_PATH):
        os.remove(ZIP_PATH)

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for rel in PATCH_FILES:
            full = os.path.join(ROOT, rel.replace("/", os.sep))
            if not os.path.isfile(full):
                missing.append(rel)
                continue
            arc = rel.replace("\\", "/")
            zf.write(full, arc)
            entries.append((arc, os.path.getsize(full)))

    zip_size = os.path.getsize(ZIP_PATH)
    lines = [
        f"MAXEK ERP v1.1 Sprint 2 VPS patch manifest",
        f"Generated (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
        f"Git branch: release/v1.1",
        f"Git commit: {commit}",
        f"ZIP: deploy/{ZIP_NAME}",
        f"ZIP bytes: {zip_size}",
        f"File count: {len(entries)}",
        "",
        "Paths (relative to /var/www/maxek-erp-flask/):",
        "",
    ]
    for arc, size in sorted(entries):
        lines.append(f"{arc}\t{size}")
    if missing:
        lines.extend(["", "MISSING (not packaged):", ""])
        lines.extend(missing)

    with open(MANIFEST_PATH, "w", encoding="utf-8", newline="\n") as mf:
        mf.write("\n".join(lines) + "\n")

    write_deploy_doc(commit, entries, zip_size)

    print(f"Commit: {commit}")
    print(f"Created: {ZIP_PATH} ({zip_size} bytes)")
    print(f"Manifest: {MANIFEST_PATH}")
    print(f"Files: {len(entries)}")
    if missing:
        print("Missing:", ", ".join(missing))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
