"""Document Management bulk import — CSV metadata and bulk file registration."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from bulk_import_service import build_xlsx_template, error_row, validation_result
from document_management_service import (
    DOCUMENT_CATEGORIES,
    DOCUMENT_EXPORT_COLUMNS,
    ensure_document_management_schema,
)


def document_import_template() -> BytesIO:
    headers = list(DOCUMENT_EXPORT_COLUMNS) + ["folder_name", "tag_list"]
    return build_xlsx_template(headers, sheet_name="Documents")


def validate_document_import_rows(db, rows: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    ensure_document_management_schema(db)
    errors: list[dict] = []
    parsed: list[dict] = []
    for row in rows:
        doc_name = _row_val(row, "document_name", "Document Name", "title")
        doc_number = _row_val(row, "document_number", "Document Number")
        if not doc_name and not doc_number:
            continue
        row_num = row.get("_row_num", "?")
        if not doc_name:
            errors.append(error_row(row_num, "Document Name", "Document name is required.", "Enter document name."))
            continue
        folder_name = _row_val(row, "folder_name", "Folder Name", "folder")
        folder_id = None
        if folder_name:
            folder_row = db.execute(
                "SELECT id FROM document_folders WHERE LOWER(folder_name)=LOWER(?) AND COALESCE(is_deleted,0)=0 LIMIT 1",
                (folder_name,),
            ).fetchone()
            if folder_row:
                folder_id = int(folder_row[0])
            else:
                errors.append(
                    error_row(row_num, "Folder Name", f"Folder not found: {folder_name}", "Use an existing folder.")
                )
                continue
        category = _row_val(row, "category", "Category") or "Other"
        if category not in DOCUMENT_CATEGORIES:
            errors.append(
                error_row(row_num, "Category", f"Invalid category: {category}", "Use a valid document category.")
            )
            continue
        parsed.append(
            {
                "document_name": doc_name,
                "document_number": doc_number,
                "document_type": _row_val(row, "document_type", "Document Type") or category,
                "category": category,
                "folder_id": folder_id,
                "module_name": _row_val(row, "module_name", "Module Name") or "enterprise_dms",
                "reference_id": _row_val(row, "reference_id", "Reference ID"),
                "description": _row_val(row, "description", "Description"),
                "expiry_date": _row_val(row, "expiry_date", "Expiry Date"),
                "tags": _row_val(row, "tags", "Tags", "tag_list"),
                "status": _row_val(row, "status", "Status") or "Active",
                "approval_status": _row_val(row, "approval_status", "Approval Status") or "Draft",
                "_row_num": row_num,
            }
        )
    return parsed, errors


def validate_document_import(db, rows: list[dict[str, Any]]) -> dict[str, Any]:
    parsed, errors = validate_document_import_rows(db, rows)
    result = validation_result(parsed, errors)
    result["parsed_rows"] = parsed
    return result


def save_document_import(
    db,
    parsed_rows: list[dict[str, Any]],
    *,
    username: str,
    filename: str = "import.csv",
    dest_root: str = "",
) -> dict[str, Any]:
    """Import metadata rows — files must be uploaded separately or via attach_document."""
    imported = 0
    skipped = 0
    for row in parsed_rows:
        doc_number = (row.get("document_number") or "").strip()
        if doc_number:
            existing = db.execute(
                "SELECT id FROM documents WHERE document_number=? AND COALESCE(is_deleted,0)=0",
                (doc_number,),
            ).fetchone()
            if existing:
                skipped += 1
                continue
        payload = dict(row)
        payload.pop("_row_num", None)
        payload.pop("document_number", None)
        try:
            if dest_root:
                raise ValueError("Metadata-only import requires separate file upload per document.")
            cur = db.execute(
                """
                INSERT INTO documents(
                    document_number, document_name, document_type, category, folder_id,
                    module_name, reference_id, description, expiry_date, tags,
                    status, approval_status, version_number, created_by, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1,?,datetime('now'))
                """,
                (
                    doc_number or None,
                    payload["document_name"],
                    payload.get("document_type"),
                    payload.get("category"),
                    payload.get("folder_id"),
                    payload.get("module_name"),
                    payload.get("reference_id") or None,
                    payload.get("description"),
                    payload.get("expiry_date") or None,
                    payload.get("tags"),
                    payload.get("status", "Active"),
                    payload.get("approval_status", "Draft"),
                    username,
                ),
            )
            doc_id = int(cur.lastrowid)
            if not doc_number:
                from document_management_service import _next_document_number

                num = _next_document_number(db)
                db.execute("UPDATE documents SET document_number=? WHERE id=?", (num, doc_id))
            imported += 1
        except ValueError:
            skipped += 1
    return {"imported": imported, "skipped": skipped, "filename": filename}


def save_document_metadata_import(db, parsed_rows: list[dict[str, Any]], username: str) -> dict[str, Any]:
    """Alias used by bulk import routes."""
    return save_document_import(db, parsed_rows, username=username)


def _row_val(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        val = str(row.get(key) or "").strip()
        if val:
            return val
    return ""
