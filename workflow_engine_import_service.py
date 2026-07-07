"""Workflow Engine bulk import — workflows and stage designations from spreadsheet."""

from __future__ import annotations

from typing import Any

from workflow_engine_service import (
    MODULE_007_SEEDS,
    save_workflow_engine,
    validate_workflow_stages,
)
from workflow_service import DEFAULT_WORKFLOW_MODE, WORKFLOW_MODES

IMPORT_COLUMNS = (
    "workflow_code",
    "workflow_name",
    "module_id",
    "module_name",
    "workflow_mode",
    "status",
    "maker_designation",
    "checker_designation",
    "approver_designation",
    "description",
)


def _designation_id_by_name(db, name: str) -> int | None:
    if not name or not str(name).strip():
        return None
    row = db.execute(
        "SELECT id FROM designations WHERE LOWER(designation_name)=LOWER(?) AND COALESCE(is_deleted,0)=0",
        (str(name).strip(),),
    ).fetchone()
    return int(row[0]) if row else None


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {str(k).strip().lower().replace(" ", "_"): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}


def validate_workflow_import(db, rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    parsed: list[dict[str, Any]] = []
    seen_codes: set[str] = set()
    seen_modules: set[str] = set()
    for idx, raw in enumerate(rows, start=2):
        row = _normalize_row(raw)
        code = (row.get("workflow_code") or "").strip()
        module_id = (row.get("module_id") or "").strip().lower().replace(" ", "_")
        name = (row.get("workflow_name") or row.get("module_name") or "").strip()
        mode = (row.get("workflow_mode") or DEFAULT_WORKFLOW_MODE).strip()
        if not module_id and not name:
            errors.append({"row": str(idx), "column": "module_id", "error": "Module ID or workflow name required"})
            continue
        if not module_id:
            module_id = name.lower().replace(" ", "_")
        if not code:
            for seed in MODULE_007_SEEDS:
                if seed["module_id"] == module_id:
                    code = seed["workflow_code"]
                    break
            if not code:
                code = f"WF-{module_id.upper()[:6]}"
        if code.upper() in seen_codes:
            errors.append({"row": str(idx), "column": "workflow_code", "error": f"Duplicate code {code} in file"})
            continue
        if module_id in seen_modules:
            errors.append({"row": str(idx), "column": "module_id", "error": f"Duplicate module {module_id} in file"})
            continue
        seen_codes.add(code.upper())
        seen_modules.add(module_id)
        if mode not in WORKFLOW_MODES:
            errors.append({"row": str(idx), "column": "workflow_mode", "error": f"Invalid mode: {mode}"})
            continue
        maker_id = _designation_id_by_name(db, row.get("maker_designation") or "")
        checker_id = _designation_id_by_name(db, row.get("checker_designation") or "")
        approver_id = _designation_id_by_name(db, row.get("approver_designation") or "")
        if not maker_id:
            errors.append({"row": str(idx), "column": "maker_designation", "error": "Maker designation not found"})
            continue
        stages = [
            {
                "stage_type": "Maker",
                "stage_number": 1,
                "stage_name": "Maker",
                "sequence": 1,
                "designation_id": maker_id,
            }
        ]
        if checker_id:
            stages.append(
                {
                    "stage_type": "Checker",
                    "stage_number": 2,
                    "stage_name": "Checker",
                    "sequence": 2,
                    "designation_id": checker_id,
                }
            )
        if approver_id:
            stages.append(
                {
                    "stage_type": "Approver",
                    "stage_number": 3,
                    "stage_name": "Approver",
                    "sequence": 3,
                    "designation_id": approver_id,
                }
            )
        try:
            validate_workflow_stages(stages, mode)
        except ValueError as exc:
            errors.append({"row": str(idx), "column": "stages", "error": str(exc)})
            continue
        existing = db.execute(
            "SELECT id FROM workflows WHERE module_id=? AND COALESCE(is_deleted,0)=0",
            (module_id,),
        ).fetchone()
        parsed.append(
            {
                "workflow_code": code,
                "workflow_name": name or module_id,
                "module_id": module_id,
                "module_name": (row.get("module_name") or name or module_id).strip(),
                "workflow_mode": mode,
                "status": (row.get("status") or "Active").strip(),
                "description": (row.get("description") or "").strip(),
                "stages": stages,
                "existing_id": int(existing[0]) if existing else None,
            }
        )
    return {"ok": not errors, "errors": errors, "parsed_rows": parsed, "row_count": len(parsed)}


def save_workflow_import(
    db,
    parsed_rows: list[dict[str, Any]],
    username: str,
    *,
    filename: str = "import.xlsx",
    customer_id: int | None = None,
) -> dict[str, Any]:
    imported = 0
    updated = 0
    for row in parsed_rows:
        form = {
            "workflow_code": row["workflow_code"],
            "workflow_name": row["workflow_name"],
            "module_id": row["module_id"],
            "module_name": row["module_name"],
            "workflow_mode": row["workflow_mode"],
            "status": row["status"],
            "description": row.get("description", ""),
            "stages": row["stages"],
        }
        wf_id = row.get("existing_id")
        save_workflow_engine(db, form, username, wf_id, customer_id=customer_id)
        if wf_id:
            updated += 1
        else:
            imported += 1
    return {"ok": True, "imported": imported, "updated": updated, "filename": filename}


def workflow_import_template() -> Any:
    from io import BytesIO

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Workflows"
    ws.append(list(IMPORT_COLUMNS))
    ws.append(
        [
            "WF-PR",
            "Purchase Request",
            "purchase_request",
            "Purchase Request",
            "full",
            "Active",
            "Project Engineer",
            "Purchase Manager",
            "Managing Director",
            "Maker → Checker → Approver",
        ]
    )
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
