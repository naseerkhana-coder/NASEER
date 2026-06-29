# VPS deploy — MAXEK ERP v1.1 Sprint 2 (partial patch)

**Branch:** `release/v1.1`  
**Git commit:** `4fc48f376ec846a62f3bbd17674eb3a9094b5564`  
**Package:** `deploy/vps-patch-v1.1-sprint2.zip` (261159 bytes)  
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

- `accounts_import_service.py` (9256 bytes)
- `app.py` (942048 bytes)
- `boq_import_service.py` (9746 bytes)
- `bulk_import_routes.py` (24433 bytes)
- `data_import_registry.py` (4726 bytes)
- `data_import_routes.py` (16223 bytes)
- `deploy/VPS_DEPLOY_v1.1_Sprint2.md` (4546 bytes)
- `deploy/vps-patch-v1.1-sprint2_PACKAGE_README.txt` (722 bytes)
- `docs/V1_1_BULK_IMPORT_SPEC.md` (5561 bytes)
- `docs/samples/v1.1-import/README.md` (2229 bytes)
- `import_audit_service.py` (7804 bytes)
- `import_tenant_helpers.py` (1348 bytes)
- `master_library_import_service.py` (23148 bytes)
- `master_library_service.py` (11208 bytes)
- `sample_data/BOQ.xlsx` (5003 bytes)
- `sample_data/COA.xlsx` (4925 bytes)
- `sample_data/Customer_Master.xlsx` (5048 bytes)
- `sample_data/Employee_Master.xlsx` (4986 bytes)
- `sample_data/Labour_Master.xlsx` (4925 bytes)
- `sample_data/Machinery_Master.xlsx` (4929 bytes)
- `sample_data/Material_Master.xlsx` (4953 bytes)
- `sample_data/Opening_Balance.xlsx` (4904 bytes)
- `sample_data/Productivity.xlsx` (4927 bytes)
- `sample_data/README.md` (2031 bytes)
- `sample_data/Rate_Master.xlsx` (4955 bytes)
- `sample_data/Vendor_Master.xlsx` (5054 bytes)
- `sample_data/WBS_Template.xlsx` (4935 bytes)
- `scripts/build_sample_data_templates.py` (3458 bytes)
- `standard_boq_library_import_service.py` (11339 bytes)
- `standard_boq_library_service.py` (6003 bytes)
- `templates/boq_library.html` (5357 bytes)
- `templates/data_import/audit_log.html` (2816 bytes)
- `templates/data_import/hub.html` (4005 bytes)
- `templates/data_import/migration_wizard.html` (6411 bytes)
- `templates/data_import/module_import.html` (5260 bytes)
- `tenant_isolation.py` (6270 bytes)
- `tests/test_bulk_import.py` (9980 bytes)
- `user_context_service.py` (8224 bytes)

See also: `deploy/vps-patch-v1.1-sprint2_MANIFEST.txt` and `deploy/vps-patch-v1.1-sprint2_PACKAGE_README.txt`.

