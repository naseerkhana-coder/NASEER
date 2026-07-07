"""BOQ Management (MODULE-017) — project BOQs, items, revisions, approval, integration hooks."""

from __future__ import annotations

import csv
import io
import json
import re
from io import BytesIO
from typing import Any, Callable

from company_master_service import _ensure_column, _now_ts, _table_exists

BOQ_STATUSES = ("Draft", "Pending", "Approved", "Rejected", "Superseded")
BOQ_ITEM_STATUSES = ("Active", "Closed", "Hold")
APPROVAL_STATUSES = ("Draft", "Pending Checker", "Pending Approver", "Approved", "Rejected")
BOQ_SORT_COLUMNS = (
    "boq_number",
    "boq_name",
    "project_id",
    "revision_number",
    "total_amount",
    "line_count",
    "status",
    "approval_status",
    "created_at",
)
BOQ_EXPORT_COLUMNS = (
    "boq_number",
    "boq_name",
    "project_code",
    "project_name",
    "revision_number",
    "revision_date",
    "client_reference",
    "contract_reference",
    "status",
    "approval_status",
    "total_amount",
    "line_count",
    "approved_by",
    "approved_date",
    "is_current_revision",
)
BOQ_ITEM_EXPORT_COLUMNS = (
    "item_number",
    "item_code",
    "description",
    "specification",
    "unit",
    "quantity",
    "rate",
    "amount",
    "executed_quantity",
    "balance_quantity",
    "status",
)
BOQ_AUDIT_FIELDS = (
    "boq_number",
    "boq_name",
    "project_id",
    "revision_number",
    "revision_date",
    "client_reference",
    "contract_reference",
    "status",
    "approval_status",
    "total_amount",
    "line_count",
    "parent_boq_id",
    "is_current_revision",
    "remarks",
)
BOQ_MAX_ITEMS = 500
DEFAULT_BOQ_UNITS = (
    "Nos",
    "Sqm",
    "Sqft",
    "Rmt",
    "Kg",
    "MT",
    "Ltr",
    "Cum",
    "Hour",
    "Day",
    "LS",
    "Set",
    "Bag",
)


def _extract_name_prefix(name: str) -> str:
    letters = re.sub(r"[^A-Za-z]", "", str(name or ""))
    if len(letters) >= 2:
        return letters[:2].upper()
    if len(letters) == 1:
        return (letters[0] * 2).upper()
    return "XX"


def _parse_prefixed_number(code: str) -> tuple[str | None, int | None]:
    text = str(code or "").strip().upper()
    if len(text) < 4 or not text[:2].isalpha():
        return None, None
    suffix = text[2:]
    if not suffix.isdigit():
        return None, None
    return text[:2], int(suffix)


def _max_prefixed_number_for_prefix(db, prefix: str) -> int:
    max_num = 99
    prefix = str(prefix or "").upper()
    like_pattern = f"{prefix}%"
    for table, column in (("projects", "project_code"), ("boq_master", "boq_number")):
        if not _table_exists(db, table):
            continue
        rows = db.execute(
            f"SELECT {column} AS code FROM {table} WHERE {column} LIKE ?",
            (like_pattern,),
        ).fetchall()
        for row in rows:
            row_prefix, number = _parse_prefixed_number(row["code"])
            if row_prefix == prefix and number is not None:
                max_num = max(max_num, number)
    return max_num


def _allocate_next_prefixed_number(db, prefix: str) -> str:
    prefix = str(prefix or "XX").upper()[:2]
    db.execute(
        """
        INSERT INTO number_sequences(prefix, last_number) VALUES(?, 99)
        ON CONFLICT(prefix) DO NOTHING
        """,
        (prefix,),
    )
    synced = _max_prefixed_number_for_prefix(db, prefix)
    db.execute(
        """
        UPDATE number_sequences SET last_number = MAX(last_number, ?)
        WHERE prefix=?
        """,
        (synced, prefix),
    )
    db.execute(
        "UPDATE number_sequences SET last_number = last_number + 1 WHERE prefix=?",
        (prefix,),
    )
    row = db.execute(
        "SELECT last_number FROM number_sequences WHERE prefix=?",
        (prefix,),
    ).fetchone()
    num = int(row[0]) if row else synced + 1
    return f"{prefix}{num}"


def generate_boq_number(db, project_id: int) -> str:
    """Project-scoped BOQ number using project name prefix (compatible with legacy app.py)."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS number_sequences(
            prefix TEXT PRIMARY KEY,
            last_number INTEGER NOT NULL DEFAULT 99
        )
        """
    )
    project = db.execute(
        "SELECT project_name FROM projects WHERE id=?",
        (project_id,),
    ).fetchone()
    if not project:
        return _allocate_next_prefixed_number(db, "XX")
    prefix = _extract_name_prefix(project["project_name"])
    return _allocate_next_prefixed_number(db, prefix)


def peek_boq_number(db, project_id: int) -> str:
    project = db.execute(
        "SELECT project_name FROM projects WHERE id=?",
        (project_id,),
    ).fetchone()
    if not project:
        return "—"
    prefix = _extract_name_prefix(project["project_name"])
    next_num = _max_prefixed_number_for_prefix(db, prefix) + 1
    return f"{prefix}{next_num}"


def ensure_boq_management_schema(db) -> None:
    """Extend boq_master / boq_items and create boq_revisions (idempotent)."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS boq_master(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            boq_number TEXT,
            project_id INTEGER,
            total_amount REAL DEFAULT 0,
            line_count INTEGER DEFAULT 0,
            created_by TEXT,
            modified_by TEXT,
            deleted_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            created_at TEXT,
            modified_at TEXT,
            deleted_at TEXT,
            is_deleted INTEGER DEFAULT 0,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS boq_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            boq_id INTEGER,
            line_no INTEGER,
            project_id INTEGER,
            boq_date TEXT,
            item_code TEXT,
            item_description TEXT,
            quantity REAL,
            unit TEXT,
            rate REAL,
            amount REAL,
            remarks TEXT,
            created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            created_at TEXT,
            modified_at TEXT,
            modified_by TEXT,
            deleted_by TEXT,
            deleted_at TEXT,
            is_deleted INTEGER DEFAULT 0,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
        """
    )
    for table, cols in (
        (
            "boq_master",
            (
                ("boq_name", "TEXT"),
                ("revision_number", "INTEGER DEFAULT 1"),
                ("revision_date", "TEXT"),
                ("client_reference", "TEXT"),
                ("contract_reference", "TEXT"),
                ("status", "TEXT DEFAULT 'Draft'"),
                ("approved_by", "TEXT"),
                ("approved_date", "TEXT"),
                ("parent_boq_id", "INTEGER"),
                ("is_current_revision", "INTEGER DEFAULT 1"),
                ("remarks", "TEXT"),
                ("submitted_by", "TEXT"),
                ("submitted_at", "TEXT"),
                ("rejected_by", "TEXT"),
                ("rejected_at", "TEXT"),
            ),
        ),
        (
            "boq_items",
            (
                ("detailed_specification", "TEXT"),
                ("library_item_id", "INTEGER"),
                ("boq_code", "TEXT"),
                ("item_number", "TEXT"),
                ("specification", "TEXT"),
                ("executed_quantity", "REAL DEFAULT 0"),
                ("status", "TEXT DEFAULT 'Active'"),
                ("sequence", "INTEGER"),
            ),
        ),
    ):
        for col, ctype in cols:
            _ensure_column(db, table, col, ctype)

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS boq_revisions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_boq_id INTEGER NOT NULL,
            child_boq_id INTEGER NOT NULL,
            revision_number INTEGER NOT NULL,
            revision_date TEXT,
            created_by TEXT,
            created_at TEXT,
            remarks TEXT,
            FOREIGN KEY(parent_boq_id) REFERENCES boq_master(id),
            FOREIGN KEY(child_boq_id) REFERENCES boq_master(id)
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_boq_master_project ON boq_master(project_id, is_deleted)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_boq_items_boq ON boq_items(boq_id, is_deleted)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_boq_revisions_parent ON boq_revisions(parent_boq_id)"
    )
    ensure_boq_management_permission(db)


def ensure_boq_management_permission(db) -> None:
    if not _table_exists(db, "permissions"):
        return
    screen = "boq_management"
    hit = db.execute(
        "SELECT id FROM permissions WHERE screen_name=? AND COALESCE(is_deleted,0)=0 LIMIT 1",
        (screen,),
    ).fetchone()
    if hit:
        return
    now = _now_ts()
    db.execute(
        """
        INSERT INTO permissions(
            permission_code, permission_name, module_name, menu_name, screen_name,
            action, description, status, created_by, created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "PRJ-BOQ-MGMT",
            "BOQ Management",
            "Projects",
            "Projects",
            screen,
            "",
            "BOQ Management — quantities, revisions, approval",
            "Active",
            "system",
            now,
        ),
    )


def _row_dict(row) -> dict[str, Any]:
    if row is None:
        return {}
    return dict(row) if hasattr(row, "keys") else {}


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return round(float(value or default), 4)
    except (TypeError, ValueError):
        return default


def compute_balance_quantity(quantity: float, executed_quantity: float) -> float:
    return round(max(_float(quantity) - _float(executed_quantity), 0), 4)


def enrich_boq_item_row(item: dict[str, Any]) -> dict[str, Any]:
    qty = _float(item.get("quantity"))
    executed = _float(item.get("executed_quantity"))
    item = dict(item)
    item["executed_quantity"] = executed
    item["balance_quantity"] = compute_balance_quantity(qty, executed)
    item["description"] = item.get("item_description") or item.get("description") or ""
    item["specification"] = (
        item.get("specification")
        or item.get("detailed_specification")
        or ""
    )
    item["item_number"] = item.get("item_number") or item.get("item_code") or ""
    return item


def validate_boq_uniqueness(
    db,
    *,
    project_id: int,
    boq_number: str,
    exclude_boq_id: int | None = None,
) -> None:
    if not project_id:
        raise ValueError("Project is required.")
    number = (boq_number or "").strip()
    if not number:
        raise ValueError("BOQ number is required.")
    sql = (
        "SELECT id FROM boq_master WHERE project_id=? AND boq_number=? "
        "AND COALESCE(is_deleted,0)=0"
    )
    params: list[Any] = [project_id, number]
    if exclude_boq_id:
        sql += " AND id<>?"
        params.append(exclude_boq_id)
    hit = db.execute(sql, params).fetchone()
    if hit:
        raise ValueError(f"BOQ number {number} already exists for this project.")


def validate_boq_item_row(item: dict[str, Any], *, row_label: str = "Item") -> None:
    desc = (item.get("description") or item.get("item_description") or "").strip()
    if not desc:
        raise ValueError(f"{row_label}: description is required.")
    unit = (item.get("unit") or "").strip()
    if not unit:
        raise ValueError(f"{row_label}: unit is required.")
    qty = _float(item.get("quantity"))
    rate = _float(item.get("rate"))
    if qty < 0 or rate < 0:
        raise ValueError(f"{row_label}: quantity and rate must be non-negative.")
    executed = _float(item.get("executed_quantity"))
    if executed > qty:
        raise ValueError(f"{row_label}: executed quantity cannot exceed BOQ quantity.")
    item_no = (item.get("item_number") or item.get("item_code") or "").strip()
    if not item_no:
        raise ValueError(f"{row_label}: item number is required.")


def parse_boq_items_from_form(form) -> list[dict[str, Any]]:
    getlist = getattr(form, "getlist", None)
    fields = {
        "item_id": "item_id[]",
        "item_number": "item_number[]",
        "description": "item_description[]",
        "specification": "specification[]",
        "unit": "unit[]",
        "quantity": "quantity[]",
        "rate": "rate[]",
        "amount": "amount[]",
        "executed_quantity": "executed_quantity[]",
        "remarks": "remarks[]",
        "boq_code": "boq_code[]",
    }
    lists: dict[str, list[str]] = {}
    for key, form_key in fields.items():
        if getlist:
            lists[key] = [str(v or "").strip() for v in (getlist(form_key) or [])]
        else:
            val = form.get(form_key) or form.get(form_key.replace("[]", ""))
            lists[key] = val if isinstance(val, list) else ([str(val)] if val else [])
    count = max((len(v) for v in lists.values()), default=0)
    items: list[dict[str, Any]] = []
    for idx in range(count):
        desc = lists["description"][idx] if idx < len(lists["description"]) else ""
        qty_raw = lists["quantity"][idx] if idx < len(lists["quantity"]) else ""
        rate_raw = lists["rate"][idx] if idx < len(lists["rate"]) else ""
        if not desc and not qty_raw and not rate_raw:
            continue
        qty = _float(qty_raw)
        rate = _float(rate_raw)
        amount_raw = lists["amount"][idx] if idx < len(lists["amount"]) else ""
        amount = _float(amount_raw) if amount_raw else round(qty * rate, 2)
        item_id_raw = lists["item_id"][idx] if idx < len(lists["item_id"]) else ""
        item_id = int(item_id_raw) if item_id_raw.isdigit() else None
        executed = _float(lists["executed_quantity"][idx] if idx < len(lists["executed_quantity"]) else 0)
        items.append(
            {
                "id": item_id,
                "line_no": idx + 1,
                "sequence": idx + 1,
                "item_number": lists["item_number"][idx] if idx < len(lists["item_number"]) else f"BOQ{idx + 1}",
                "item_code": lists["item_number"][idx] if idx < len(lists["item_number"]) else f"BOQ{idx + 1}",
                "description": desc,
                "item_description": desc,
                "specification": lists["specification"][idx] if idx < len(lists["specification"]) else "",
                "detailed_specification": lists["specification"][idx] if idx < len(lists["specification"]) else "",
                "unit": lists["unit"][idx] if idx < len(lists["unit"]) else "Nos",
                "quantity": qty,
                "rate": rate,
                "amount": amount,
                "executed_quantity": executed,
                "remarks": lists["remarks"][idx] if idx < len(lists["remarks"]) else "",
                "boq_code": lists["boq_code"][idx] if idx < len(lists["boq_code"]) else "",
            }
        )
    return items


def _parse_boq_header_form(form) -> dict[str, Any]:
    project_raw = form.get("project_id")
    project_id = int(project_raw) if project_raw and str(project_raw).isdigit() else None
    rev_raw = form.get("revision_number")
    revision_number = int(rev_raw) if rev_raw and str(rev_raw).isdigit() else 1
    return {
        "project_id": project_id,
        "boq_number": (form.get("boq_number") or "").strip(),
        "boq_name": (form.get("boq_name") or "").strip(),
        "revision_number": revision_number,
        "revision_date": (form.get("revision_date") or "").strip(),
        "client_reference": (form.get("client_reference") or "").strip(),
        "contract_reference": (form.get("contract_reference") or "").strip(),
        "status": (form.get("status") or "Draft").strip(),
        "remarks": (form.get("remarks") or "").strip(),
    }


def list_boqs_master(
    db,
    *,
    search: str = "",
    project_id: int | None = None,
    status: str = "",
    approval_status: str = "",
    current_only: bool = False,
    include_deleted: bool = False,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    page: int = 1,
    per_page: int = 25,
) -> dict[str, Any]:
    ensure_boq_management_schema(db)
    clauses = ["COALESCE(m.is_deleted,0)=0"] if not include_deleted else ["1=1"]
    params: list[Any] = []
    if project_id:
        clauses.append("m.project_id=?")
        params.append(project_id)
    if status:
        clauses.append("COALESCE(m.status,'Draft')=?")
        params.append(status)
    if approval_status:
        clauses.append("COALESCE(m.approval_status,'')=?")
        params.append(approval_status)
    if current_only:
        clauses.append("COALESCE(m.is_current_revision,1)=1")
    if search:
        like = f"%{search.strip().lower()}%"
        clauses.append(
            "(LOWER(COALESCE(m.boq_number,'')) LIKE ? OR LOWER(COALESCE(m.boq_name,'')) LIKE ? "
            "OR LOWER(COALESCE(p.project_name,'')) LIKE ? OR LOWER(COALESCE(p.project_code,'')) LIKE ?)"
        )
        params.extend([like, like, like, like])
    where = " AND ".join(clauses)
    sort_col = sort_by if sort_by in BOQ_SORT_COLUMNS else "created_at"
    direction = "ASC" if str(sort_dir).lower() == "asc" else "DESC"
    total = db.execute(
        f"""
        SELECT COUNT(*) AS c FROM boq_master m
        LEFT JOIN projects p ON p.id=m.project_id
        WHERE {where}
        """,
        params,
    ).fetchone()[0]
    offset = max(page - 1, 0) * per_page
    client_join = ""
    client_cols = ""
    if _table_exists(db, "clients"):
        client_join = "LEFT JOIN clients c ON c.id=p.client_id"
        client_cols = ", c.client_name, c.client_code"
    rows = db.execute(
        f"""
        SELECT m.*, p.project_code, p.project_name{client_cols}
        FROM boq_master m
        LEFT JOIN projects p ON p.id=m.project_id
        {client_join}
        WHERE {where}
        ORDER BY m.{sort_col} {direction}, m.id DESC
        LIMIT ? OFFSET ?
        """,
        (*params, per_page, offset),
    ).fetchall()
    pages = max((total + per_page - 1) // per_page, 1)
    return {
        "items": [_row_dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }


def list_boq_items(db, boq_id: int, *, include_deleted: bool = False) -> list[dict[str, Any]]:
    ensure_boq_management_schema(db)
    clause = "" if include_deleted else "AND COALESCE(is_deleted,0)=0"
    rows = db.execute(
        f"""
        SELECT * FROM boq_items WHERE boq_id=? {clause}
        ORDER BY COALESCE(sequence, line_no, id), id
        """,
        (boq_id,),
    ).fetchall()
    return [enrich_boq_item_row(_row_dict(r)) for r in rows]


def get_boq_master(db, boq_id: int, *, include_deleted: bool = False) -> dict[str, Any] | None:
    ensure_boq_management_schema(db)
    clause = "" if include_deleted else "AND COALESCE(m.is_deleted,0)=0"
    client_join = ""
    client_cols = ""
    if _table_exists(db, "clients"):
        client_join = "LEFT JOIN clients c ON c.id=p.client_id"
        client_cols = ", p.client_id, c.client_name, c.client_code"
    row = db.execute(
        f"""
        SELECT m.*, p.project_code, p.project_name{client_cols}
        FROM boq_master m
        LEFT JOIN projects p ON p.id=m.project_id
        {client_join}
        WHERE m.id=? {clause}
        """,
        (boq_id,),
    ).fetchone()
    if not row:
        return None
    data = _row_dict(row)
    data["items"] = list_boq_items(db, boq_id, include_deleted=include_deleted)
    data["revisions"] = list_boq_revision_history(db, boq_id)
    return data


def list_boq_revision_history(db, boq_id: int) -> list[dict[str, Any]]:
    ensure_boq_management_schema(db)
    root = db.execute(
        "SELECT COALESCE(parent_boq_id, id) AS root_id FROM boq_master WHERE id=?",
        (boq_id,),
    ).fetchone()
    root_id = root["root_id"] if root else boq_id
    rows = db.execute(
        """
        SELECT m.id, m.boq_number, m.boq_name, m.revision_number, m.revision_date,
               m.status, m.approval_status, m.is_current_revision, m.created_at, m.created_by
        FROM boq_master m
        WHERE m.id=? OR m.parent_boq_id=? OR m.id IN (
            SELECT child_boq_id FROM boq_revisions WHERE parent_boq_id=?
        )
        ORDER BY m.revision_number ASC, m.id ASC
        """,
        (root_id, root_id, root_id),
    ).fetchall()
    if not rows:
        row = db.execute(
            "SELECT id, boq_number, boq_name, revision_number, revision_date, status, "
            "approval_status, is_current_revision, created_at, created_by FROM boq_master WHERE id=?",
            (boq_id,),
        ).fetchone()
        return [_row_dict(row)] if row else []
    return [_row_dict(r) for r in rows]


def _insert_boq_items(
    db,
    boq_id: int,
    project_id: int,
    items: list[dict[str, Any]],
    username: str,
    now: str,
    *,
    default_approval: str = "Pending Checker",
) -> None:
    for item in items:
        validate_boq_item_row(item, row_label=f"Line {item.get('line_no', '?')}")
        qty = _float(item.get("quantity"))
        executed = min(_float(item.get("executed_quantity")), qty)
        amount = _float(item.get("amount")) or round(qty * _float(item.get("rate")), 2)
        db.execute(
            """
            INSERT INTO boq_items(
                boq_id, line_no, sequence, item_code, item_number, project_id,
                item_description, detailed_specification, specification, quantity, unit, rate, amount,
                executed_quantity, remarks, boq_code, library_item_id, created_by, created_at,
                approval_status, status, is_deleted
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)
            """,
            (
                boq_id,
                item.get("line_no") or item.get("sequence"),
                item.get("sequence") or item.get("line_no"),
                item.get("item_code") or item.get("item_number"),
                item.get("item_number") or item.get("item_code"),
                project_id,
                item.get("description") or item.get("item_description"),
                item.get("detailed_specification") or item.get("specification") or "",
                item.get("specification") or item.get("detailed_specification") or "",
                qty,
                item.get("unit") or "Nos",
                _float(item.get("rate")),
                amount,
                executed,
                item.get("remarks") or "",
                item.get("boq_code") or "",
                item.get("library_item_id"),
                username,
                now,
                default_approval,
                item.get("status") or "Active",
            ),
        )


def _recalc_boq_totals(db, boq_id: int) -> None:
    row = db.execute(
        """
        SELECT COALESCE(SUM(amount),0) AS total, COUNT(*) AS cnt
        FROM boq_items WHERE boq_id=? AND COALESCE(is_deleted,0)=0
        """,
        (boq_id,),
    ).fetchone()
    db.execute(
        "UPDATE boq_master SET total_amount=?, line_count=? WHERE id=?",
        (_float(row["total"]), int(row["cnt"] or 0), boq_id),
    )


def save_boq_master(
    db,
    form,
    username: str,
    boq_id: int | None = None,
    *,
    create_approval_request_fn: Callable | None = None,
    default_approval: str = "Pending Checker",
) -> int:
    ensure_boq_management_schema(db)
    header = _parse_boq_header_form(form)
    items = parse_boq_items_from_form(form)
    if not header["project_id"]:
        raise ValueError("Project is required.")
    if not items:
        raise ValueError("Add at least one BOQ line item.")
    if len(items) > BOQ_MAX_ITEMS:
        raise ValueError(f"Maximum {BOQ_MAX_ITEMS} line items allowed per BOQ.")
    for idx, item in enumerate(items, start=1):
        validate_boq_item_row(item, row_label=f"Line {idx}")
    now = _now_ts()
    total_amount = round(sum(_float(i.get("amount")) for i in items), 2)
    status = header["status"] if header["status"] in BOQ_STATUSES else "Draft"

    if boq_id:
        existing = get_boq_master(db, boq_id)
        if not existing:
            raise ValueError("BOQ not found.")
        boq_number = header["boq_number"] or existing.get("boq_number") or ""
        validate_boq_uniqueness(
            db,
            project_id=int(header["project_id"]),
            boq_number=boq_number,
            exclude_boq_id=boq_id,
        )
        db.execute(
            """
            UPDATE boq_master SET project_id=?, boq_number=?, boq_name=?, revision_number=?,
            revision_date=?, client_reference=?, contract_reference=?, status=?, remarks=?,
            total_amount=?, line_count=?, modified_by=?, modified_at=? WHERE id=?
            """,
            (
                header["project_id"],
                boq_number,
                header["boq_name"],
                header["revision_number"],
                header["revision_date"],
                header["client_reference"],
                header["contract_reference"],
                status,
                header["remarks"],
                total_amount,
                len(items),
                username,
                now,
                boq_id,
            ),
        )
        db.execute(
            "UPDATE boq_items SET is_deleted=1, deleted_by=?, deleted_at=? WHERE boq_id=?",
            (username, now, boq_id),
        )
        _insert_boq_items(
            db,
            boq_id,
            int(header["project_id"]),
            items,
            username,
            now,
            default_approval=default_approval,
        )
        log_boq_audit(db, boq_id, "update", username, remarks="BOQ updated")
        return boq_id

    boq_number = header["boq_number"] or generate_boq_number(db, int(header["project_id"]))
    validate_boq_uniqueness(db, project_id=int(header["project_id"]), boq_number=boq_number)
    cur = db.execute(
        """
        INSERT INTO boq_master(
            boq_number, boq_name, project_id, revision_number, revision_date,
            client_reference, contract_reference, status, remarks,
            total_amount, line_count, created_by, approval_status, created_at,
            is_current_revision, parent_boq_id
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,NULL)
        """,
        (
            boq_number,
            header["boq_name"],
            header["project_id"],
            header["revision_number"],
            header["revision_date"] or now[:10],
            header["client_reference"],
            header["contract_reference"],
            status,
            header["remarks"],
            total_amount,
            len(items),
            username,
            default_approval,
            now,
        ),
    )
    new_id = int(cur.lastrowid)
    _insert_boq_items(
        db,
        new_id,
        int(header["project_id"]),
        items,
        username,
        now,
        default_approval=default_approval,
    )
    if create_approval_request_fn:
        create_approval_request_fn(db, "boq", new_id, "boq_master", username, None)
    log_boq_audit(db, new_id, "create", username, remarks=f"Created BOQ {boq_number}")
    return new_id


def copy_boq_master(
    db,
    source_boq_id: int,
    username: str,
    *,
    as_revision: bool = True,
    create_approval_request_fn: Callable | None = None,
    default_approval: str = "Pending Checker",
) -> int:
    source = get_boq_master(db, source_boq_id)
    if not source:
        raise ValueError("Source BOQ not found.")
    now = _now_ts()
    parent_id = source.get("parent_boq_id") or source_boq_id
    next_rev = int(source.get("revision_number") or 1) + 1
    if as_revision:
        db.execute(
            "UPDATE boq_master SET is_current_revision=0, status='Superseded', modified_by=?, modified_at=? "
            "WHERE id=? OR (parent_boq_id=? AND COALESCE(is_current_revision,0)=1)",
            (username, now, parent_id, parent_id),
        )
    boq_number = source.get("boq_number") or generate_boq_number(db, int(source["project_id"]))
    cur = db.execute(
        """
        INSERT INTO boq_master(
            boq_number, boq_name, project_id, revision_number, revision_date,
            client_reference, contract_reference, status, remarks,
            total_amount, line_count, created_by, approval_status, created_at,
            is_current_revision, parent_boq_id
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)
        """,
        (
            boq_number,
            source.get("boq_name") or "",
            source["project_id"],
            next_rev if as_revision else 1,
            now[:10],
            source.get("client_reference") or "",
            source.get("contract_reference") or "",
            "Draft",
            source.get("remarks") or "",
            source.get("total_amount") or 0,
            source.get("line_count") or 0,
            username,
            default_approval,
            now,
            parent_id if as_revision else None,
        ),
    )
    new_id = int(cur.lastrowid)
    items = list_boq_items(db, source_boq_id)
    for item in items:
        item.pop("id", None)
        item["executed_quantity"] = 0
    _insert_boq_items(
        db,
        new_id,
        int(source["project_id"]),
        items,
        username,
        now,
        default_approval=default_approval,
    )
    _recalc_boq_totals(db, new_id)
    if as_revision:
        db.execute(
            """
            INSERT INTO boq_revisions(parent_boq_id, child_boq_id, revision_number, revision_date, created_by, created_at, remarks)
            VALUES(?,?,?,?,?,?,?)
            """,
            (parent_id, new_id, next_rev, now[:10], username, now, f"Revision from BOQ #{source_boq_id}"),
        )
    if create_approval_request_fn:
        create_approval_request_fn(db, "boq", new_id, "boq_master", username, None)
    log_boq_audit(db, new_id, "revision", username, remarks=f"Copied from BOQ #{source_boq_id}")
    return new_id


def submit_boq_for_approval(db, boq_id: int, username: str) -> None:
    now = _now_ts()
    db.execute(
        """
        UPDATE boq_master SET status='Pending', approval_status='Pending Checker',
        submitted_by=?, submitted_at=?, modified_by=?, modified_at=? WHERE id=?
        """,
        (username, now, username, now, boq_id),
    )
    log_boq_audit(db, boq_id, "submit", username)


def approve_boq_master(db, boq_id: int, username: str) -> None:
    now = _now_ts()
    db.execute(
        """
        UPDATE boq_master SET status='Approved', approval_status='Approved',
        approved_by=?, approved_date=?, modified_by=?, modified_at=? WHERE id=?
        """,
        (username, now[:10], username, now, boq_id),
    )
    db.execute(
        "UPDATE boq_items SET approval_status='Approved', modified_by=?, modified_at=? WHERE boq_id=?",
        (username, now, boq_id),
    )
    log_boq_audit(db, boq_id, "approve", username)


def reject_boq_master(db, boq_id: int, username: str, remarks: str = "") -> None:
    now = _now_ts()
    db.execute(
        """
        UPDATE boq_master SET status='Rejected', approval_status='Rejected',
        rejected_by=?, rejected_at=?, remarks=COALESCE(?, remarks),
        modified_by=?, modified_at=? WHERE id=?
        """,
        (username, now, remarks or None, username, now, boq_id),
    )
    log_boq_audit(db, boq_id, "reject", username, remarks=remarks)


def soft_delete_boq_master(db, boq_id: int, username: str) -> None:
    now = _now_ts()
    db.execute(
        "UPDATE boq_master SET is_deleted=1, deleted_by=?, deleted_at=? WHERE id=?",
        (username, now, boq_id),
    )
    db.execute(
        "UPDATE boq_items SET is_deleted=1, deleted_by=?, deleted_at=? WHERE boq_id=?",
        (username, now, boq_id),
    )
    log_boq_audit(db, boq_id, "delete", username)


def log_boq_audit(db, boq_id: int, action: str, username: str, *, remarks: str = "") -> None:
    try:
        from audit_trail_service import log_record_change

        log_record_change(
            db,
            "boq_master",
            boq_id,
            action,
            username,
            remarks=remarks or action,
        )
    except Exception:
        pass


def list_boq_audit_trail(db, boq_id: int, limit: int = 100) -> list[dict[str, Any]]:
    try:
        from audit_trail_service import list_audit_trail

        return list_audit_trail(db, "boq_master", boq_id, limit=limit)
    except Exception:
        return []


def user_can_boq_management(
    db,
    user_id: int | None,
    action: str,
    *,
    is_admin: bool = False,
) -> bool:
    if is_admin:
        return True
    if not user_id:
        return False
    action_map = {
        "import": "import",
        "revision": "revision",
        "deactivate": "edit",
        "activate": "edit",
    }
    check = action_map.get(action, action)
    try:
        from user_permission_service import empty_permission_actions, normalize_permission_actions

        row = db.execute(
            """
            SELECT granted, action_flags FROM user_tab_permissions
            WHERE user_id=? AND granted=1 AND endpoint='boq_management'
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        if not row:
            return False
        raw_flags = row["action_flags"] if hasattr(row, "keys") else row[1]
        actions = normalize_permission_actions(
            json.loads(raw_flags) if raw_flags else empty_permission_actions()
        )
        if check == "import":
            return bool(actions.get("import") or actions.get("create"))
        if check == "revision":
            return bool(actions.get("create") or actions.get("edit"))
        if check == "delete":
            return bool(actions.get("delete") or actions.get("edit"))
        return bool(actions.get(check))
    except Exception:
        return False


def boqs_for_export(db, **filters) -> list[dict[str, Any]]:
    listing = list_boqs_master(db, per_page=10000, **filters)
    return listing["items"]


def export_boqs_excel(db, **filters) -> BytesIO:
    from openpyxl import Workbook

    rows = boqs_for_export(db, **filters)
    wb = Workbook()
    ws = wb.active
    ws.title = "BOQ Register"
    headers = list(BOQ_EXPORT_COLUMNS)
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h, "") for h in headers])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def export_boqs_csv(db, **filters) -> str:
    rows = boqs_for_export(db, **filters)
    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow(list(BOQ_EXPORT_COLUMNS))
    for row in rows:
        writer.writerow([row.get(h, "") for h in BOQ_EXPORT_COLUMNS])
    return si.getvalue()


def export_boq_items_excel(db, boq_id: int) -> BytesIO:
    from openpyxl import Workbook

    items = list_boq_items(db, boq_id)
    wb = Workbook()
    ws = wb.active
    ws.title = "BOQ Items"
    headers = list(BOQ_ITEM_EXPORT_COLUMNS)
    ws.append(headers)
    for item in items:
        ws.append([item.get(h, "") for h in headers])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def export_boqs_pdf(db, *, report_title: str = "BOQ Report", **filters) -> BytesIO:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas

    rows = boqs_for_export(db, **filters)
    buf = BytesIO()
    page_size = landscape(A4)
    c = canvas.Canvas(buf, pagesize=page_size)
    _, height = page_size
    y = height - 40
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, f"MAXEK ERP — {report_title}")
    y -= 24
    c.setFont("Helvetica", 9)
    for row in rows[:300]:
        line = (
            f"{row.get('boq_number')} | {row.get('project_code')} | Rev {row.get('revision_number')} | "
            f"{row.get('status')} | {row.get('total_amount')}"
        )
        if y < 40:
            c.showPage()
            y = height - 40
            c.setFont("Helvetica", 9)
        c.drawString(40, y, line[:140])
        y -= 14
    c.save()
    buf.seek(0)
    return buf


def boq_report(db, report_key: str, **filters) -> list[dict[str, Any]]:
    key = (report_key or "register").lower().strip()
    if key == "summary":
        listing = list_boqs_master(db, per_page=5000, current_only=True, **filters)
        return listing["items"]
    if key == "revision":
        listing = list_boqs_master(db, per_page=5000, include_deleted=False, **filters)
        out: list[dict[str, Any]] = []
        for row in listing["items"]:
            for rev in list_boq_revision_history(db, int(row["id"])):
                out.append({**row, **rev})
        return out
    if key == "quantity_balance":
        listing = list_boqs_master(db, per_page=500, current_only=True, **filters)
        out = []
        for row in listing["items"]:
            for item in list_boq_items(db, int(row["id"])):
                out.append(
                    {
                        "boq_number": row.get("boq_number"),
                        "project_code": row.get("project_code"),
                        "item_number": item.get("item_number"),
                        "description": item.get("description"),
                        "quantity": item.get("quantity"),
                        "executed_quantity": item.get("executed_quantity"),
                        "balance_quantity": item.get("balance_quantity"),
                        "unit": item.get("unit"),
                    }
                )
        return out
    if key == "item_summary":
        listing = list_boqs_master(db, per_page=200, **filters)
        out = []
        for row in listing["items"]:
            for item in list_boq_items(db, int(row["id"])):
                out.append(
                    {
                        "boq_number": row.get("boq_number"),
                        "project_code": row.get("project_code"),
                        **{k: item.get(k) for k in BOQ_ITEM_EXPORT_COLUMNS},
                    }
                )
        return out
    listing = list_boqs_master(db, per_page=5000, **filters)
    return listing["items"]


# --- Integration hooks for DPR / Client Billing (future modules) ---


def get_boq_items_for_project(db, project_id: int, boq_id: int | None = None) -> list[dict[str, Any]]:
    ensure_boq_management_schema(db)
    clauses = ["COALESCE(bi.is_deleted,0)=0", "bi.project_id=?"]
    params: list[Any] = [project_id]
    if boq_id:
        clauses.append("bi.boq_id=?")
        params.append(boq_id)
    else:
        clauses.append("COALESCE(bm.is_current_revision,1)=1")
    where = " AND ".join(clauses)
    rows = db.execute(
        f"""
        SELECT bi.*, bm.boq_number, bm.boq_name, bm.approval_status AS boq_approval_status
        FROM boq_items bi
        INNER JOIN boq_master bm ON bm.id=bi.boq_id
        WHERE {where}
        ORDER BY bm.boq_number, COALESCE(bi.sequence, bi.line_no, bi.id)
        """,
        params,
    ).fetchall()
    return [enrich_boq_item_row(_row_dict(r)) for r in rows]


def update_executed_quantity(db, boq_item_id: int, executed_delta: float) -> None:
    """Apply executed quantity delta (DPR / billing integration hook)."""
    ensure_boq_management_schema(db)
    row = db.execute(
        "SELECT quantity, executed_quantity FROM boq_items WHERE id=? AND COALESCE(is_deleted,0)=0",
        (boq_item_id,),
    ).fetchone()
    if not row:
        raise ValueError("BOQ item not found.")
    qty = _float(row["quantity"])
    new_executed = min(_float(row["executed_quantity"]) + _float(executed_delta), qty)
    if new_executed < 0:
        raise ValueError("Executed quantity cannot be negative.")
    db.execute(
        "UPDATE boq_items SET executed_quantity=?, modified_at=? WHERE id=?",
        (new_executed, _now_ts(), boq_item_id),
    )


def get_boq_balance_summary(db, project_id: int) -> dict[str, Any]:
    items = get_boq_items_for_project(db, project_id)
    total_qty = sum(_float(i.get("quantity")) for i in items)
    total_executed = sum(_float(i.get("executed_quantity")) for i in items)
    total_balance = sum(_float(i.get("balance_quantity")) for i in items)
    total_amount = sum(_float(i.get("amount")) for i in items)
    return {
        "project_id": project_id,
        "item_count": len(items),
        "total_quantity": round(total_qty, 4),
        "total_executed": round(total_executed, 4),
        "total_balance": round(total_balance, 4),
        "total_amount": round(total_amount, 2),
        "items": items,
    }


# --- AI interfaces (rule-based stubs; no external AI) ---


def validate_boq(db, boq_id: int | None = None, *, form: dict | None = None) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    if boq_id:
        boq = get_boq_master(db, boq_id)
        if not boq:
            return {"ok": False, "issues": [{"field": "boq_id", "message": "BOQ not found."}]}
        if not boq.get("project_id"):
            issues.append({"field": "project_id", "message": "Project is required."})
        for item in boq.get("items") or []:
            try:
                validate_boq_item_row(item)
            except ValueError as exc:
                issues.append({"field": "items", "message": str(exc)})
    if form:
        header = _parse_boq_header_form(form)
        if not header.get("project_id"):
            issues.append({"field": "project_id", "message": "Project is required."})
        if not (header.get("boq_number") or boq_id):
            warnings.append({"field": "boq_number", "message": "BOQ number will be auto-generated."})
    dup = detect_duplicate_items(db, boq_id=boq_id)
    if dup.get("duplicates"):
        warnings.extend(
            {"field": "items", "message": f"Duplicate item number: {d}"} for d in dup["duplicates"]
        )
    anomalies = quantity_anomaly_check(db, boq_id=boq_id)
    warnings.extend({"field": "quantity", "message": m} for m in anomalies.get("warnings", []))
    return {"ok": not issues, "issues": issues, "warnings": warnings, "ai_hook": "stub_ready"}


def detect_duplicate_items(db, boq_id: int | None = None, items: list[dict] | None = None) -> dict[str, Any]:
    source = items
    if source is None and boq_id:
        source = list_boq_items(db, boq_id)
    source = source or []
    seen: dict[str, int] = {}
    duplicates: list[str] = []
    for item in source:
        key = (item.get("item_number") or item.get("item_code") or "").strip().lower()
        if not key:
            continue
        seen[key] = seen.get(key, 0) + 1
        if seen[key] == 2:
            duplicates.append(key)
    return {"duplicates": duplicates, "ai_hook": "stub_ready"}


def quantity_anomaly_check(db, boq_id: int | None = None, items: list[dict] | None = None) -> dict[str, Any]:
    source = items
    if source is None and boq_id:
        source = list_boq_items(db, boq_id)
    source = source or []
    warnings: list[str] = []
    for item in source:
        qty = _float(item.get("quantity"))
        rate = _float(item.get("rate"))
        amount = _float(item.get("amount"))
        if qty == 0 and rate > 0:
            warnings.append(f"Zero quantity with non-zero rate on {item.get('item_number', '?')}")
        if qty > 0 and rate == 0:
            warnings.append(f"Non-zero quantity with zero rate on {item.get('item_number', '?')}")
        if qty > 0 and rate > 0 and abs(amount - qty * rate) > 0.05:
            warnings.append(f"Amount mismatch on {item.get('item_number', '?')}")
    return {"warnings": warnings, "ai_hook": "stub_ready"}


def compare_boqs(db, boq_id_a: int, boq_id_b: int) -> dict[str, Any]:
    a = get_boq_master(db, boq_id_a)
    b = get_boq_master(db, boq_id_b)
    if not a or not b:
        return {"ok": False, "error": "One or both BOQs not found.", "ai_hook": "stub_ready"}
    map_a = {
        (i.get("item_number") or "").strip().lower(): i for i in (a.get("items") or [])
    }
    map_b = {
        (i.get("item_number") or "").strip().lower(): i for i in (b.get("items") or [])
    }
    added = [k for k in map_b if k and k not in map_a]
    removed = [k for k in map_a if k and k not in map_b]
    changed = []
    for key in map_a:
        if key in map_b and (
            _float(map_a[key].get("quantity")) != _float(map_b[key].get("quantity"))
            or _float(map_a[key].get("rate")) != _float(map_b[key].get("rate"))
        ):
            changed.append(key)
    return {
        "ok": True,
        "added": added,
        "removed": removed,
        "changed": changed,
        "total_amount_a": a.get("total_amount"),
        "total_amount_b": b.get("total_amount"),
        "ai_hook": "stub_ready",
    }


def list_projects_for_boq_form(db) -> list[dict[str, Any]]:
    client_join = ""
    client_cols = ""
    if _table_exists(db, "clients"):
        client_join = "LEFT JOIN clients c ON c.id=p.client_id"
        client_cols = ", p.client_id, c.client_name"
    rows = db.execute(
        f"""
        SELECT p.id, p.project_code, p.project_name{client_cols}
        FROM projects p
        {client_join}
        WHERE p.status IS NULL OR p.status NOT IN ('Inactive','Cancelled','Closed')
        ORDER BY p.project_name
        """
    ).fetchall()
    return [_row_dict(r) for r in rows]
