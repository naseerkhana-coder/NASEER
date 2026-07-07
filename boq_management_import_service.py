"""BOQ Management import — extends legacy boq_import_service with header metadata."""

from __future__ import annotations

from typing import Any, Callable

from boq_import_service import (
    BOQ_IMPORT_COLUMNS,
    boq_import_template,
    save_boq_import,
    validate_boq_import,
    validate_boq_import_rows,
)
from boq_management_service import (
    _now_ts,
    ensure_boq_management_schema,
    generate_boq_number,
    log_boq_audit,
)


def boq_management_import_template():
    return boq_import_template()


def validate_boq_management_import(
    db,
    rows: list[dict[str, Any]],
    *,
    boq_units: list[str],
    project_id: int | None,
    boq_name: str = "",
) -> dict[str, Any]:
    ensure_boq_management_schema(db)
    result = validate_boq_import(db, rows, boq_units=boq_units, project_id=project_id)
    if boq_name:
        result["boq_name"] = boq_name.strip()
    return result


def save_boq_management_import(
    db,
    parsed_rows: list[dict[str, Any]],
    *,
    project_id: int,
    username: str,
    filename: str,
    boq_name: str = "",
    client_reference: str = "",
    contract_reference: str = "",
    create_approval_request_fn: Callable | None = None,
    record_pending_checker: str = "Pending Checker",
) -> dict[str, Any]:
    """Import lines into a new BOQ header with MODULE-017 metadata."""
    ensure_boq_management_schema(db)
    result = save_boq_import(
        db,
        parsed_rows,
        project_id=project_id,
        username=username,
        filename=filename,
        generate_boq_number_fn=generate_boq_number,
        insert_boq_lines_fn=None,
        create_approval_request_fn=create_approval_request_fn or (lambda *a, **k: None),
        record_pending_checker=record_pending_checker,
    )
    boq_id = int(result["boq_id"])
    now = _now_ts()
    db.execute(
        """
        UPDATE boq_master SET boq_name=?, client_reference=?, contract_reference=?,
        revision_number=COALESCE(revision_number,1), revision_date=?, status='Draft',
        is_current_revision=1, modified_by=?, modified_at=? WHERE id=?
        """,
        (
            (boq_name or f"Imported BOQ {result.get('boq_number', '')}").strip(),
            client_reference.strip(),
            contract_reference.strip(),
            now[:10],
            username,
            now,
            boq_id,
        ),
    )
    db.execute(
        """
        UPDATE boq_items SET item_number=COALESCE(item_number, item_code),
        specification=COALESCE(specification, detailed_specification),
        executed_quantity=COALESCE(executed_quantity, 0)
        WHERE boq_id=?
        """,
        (boq_id,),
    )
    log_boq_audit(db, boq_id, "import", username, remarks=f"Imported from {filename}")
    result["boq_name"] = boq_name
    return result


def validate_boq_management_rows(
    db,
    rows: list[dict[str, Any]],
    *,
    boq_units: list[str],
    project_id: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return validate_boq_import_rows(db, rows, boq_units=boq_units, project_id=project_id)


__all__ = [
    "BOQ_IMPORT_COLUMNS",
    "boq_management_import_template",
    "save_boq_management_import",
    "validate_boq_management_import",
    "validate_boq_management_rows",
]
