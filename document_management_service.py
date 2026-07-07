"""Enterprise Document Management System (MODULE-010) — centralized DMS for all ERP modules."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import os
import re
from datetime import date, datetime
from io import BytesIO
from typing import Any, BinaryIO

from company_master_service import (
    _ensure_column,
    _now_ts,
    _table_exists,
    ensure_company_master_schema,
    list_companies,
)

logger = logging.getLogger(__name__)

DEFAULT_FOLDERS = (
    "Legal",
    "HR",
    "Finance",
    "Projects",
    "Compliance",
    "Contracts",
    "Drawings",
    "General",
)

DOCUMENT_CATEGORIES = (
    "Policy",
    "Contract",
    "Certificate",
    "License",
    "Report",
    "Circular",
    "Memo",
    "Drawing",
    "Invoice",
    "Correspondence",
    "Photo",
    "Other",
)

DOCUMENT_TYPES = DOCUMENT_CATEGORIES

DOCUMENT_STATUSES = ("Active", "Inactive", "Draft")
APPROVAL_STATUSES = ("Draft", "Pending", "Approved", "Rejected")
OCR_STATUSES = ("pending", "completed", "failed", "skipped", "not_applicable")

DMS_ALLOWED_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".csv",
    ".txt",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".zip",
    ".dwg",
    ".dxf",
}

PREVIEW_INLINE_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".txt"}
MAX_DMS_UPLOAD_BYTES = 25 * 1024 * 1024
EXPIRY_ALERT_DAYS = (90, 60, 30, 7)

DOCUMENT_SORT_COLUMNS = (
    "document_number",
    "document_name",
    "document_type",
    "category",
    "module_name",
    "status",
    "approval_status",
    "created_at",
    "file_size",
    "expiry_date",
)

DOCUMENT_EXPORT_COLUMNS = (
    "document_number",
    "document_name",
    "document_type",
    "category",
    "module_name",
    "reference_id",
    "company_code",
    "branch_code",
    "project_id",
    "folder_name",
    "tags",
    "description",
    "status",
    "approval_status",
    "version_number",
    "file_extension",
    "file_size",
    "expiry_date",
    "archive_flag",
    "confidential_flag",
    "created_by",
    "created_at",
)

DOCUMENT_AUDIT_FIELDS = (
    "document_name",
    "document_type",
    "category",
    "folder_id",
    "module_name",
    "reference_id",
    "status",
    "approval_status",
    "archive_flag",
    "confidential_flag",
    "expiry_date",
    "description",
)


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _parse_date(value: str | None) -> date | None:
    if not value or not str(value).strip():
        return None
    try:
        return datetime.strptime(str(value).strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def virus_scan_file(file_path: str) -> dict[str, Any]:
    """Callable virus-scan hook — logs and passes; replace with ClamAV or similar in production."""
    logger.info("Virus scan stub passed: %s", file_path)
    return {"clean": True, "scanner": "stub", "message": "Scan skipped (stub interface ready)"}


def compute_file_hash(file_obj: BinaryIO) -> str:
    file_obj.seek(0)
    digest = hashlib.sha256()
    while True:
        chunk = file_obj.read(65536)
        if not chunk:
            break
        digest.update(chunk)
    file_obj.seek(0)
    return digest.hexdigest()


def validate_dms_upload(file_storage, *, required: bool = True) -> tuple[str | None, str | None]:
    if not file_storage or not getattr(file_storage, "filename", None):
        if required:
            return None, "Select a document file to upload."
        return None, None
    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in DMS_ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ext.upper().lstrip(".") for ext in DMS_ALLOWED_EXTENSIONS))
        return None, f"Allowed file types: {allowed}."
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_DMS_UPLOAD_BYTES:
        return None, f"File is too large (maximum {MAX_DMS_UPLOAD_BYTES // (1024 * 1024)} MB)."
    return ext, None


def ensure_document_management_schema(db) -> None:
    """Idempotent schema for enterprise DMS tables."""
    ensure_company_master_schema(db)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS document_folders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folder_name TEXT NOT NULL,
            parent_id INTEGER,
            company_id INTEGER,
            branch_id INTEGER,
            project_id INTEGER,
            description TEXT,
            sort_order INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_by TEXT,
            created_at TEXT,
            modified_by TEXT,
            modified_at TEXT,
            is_deleted INTEGER DEFAULT 0,
            deleted_by TEXT,
            deleted_at TEXT,
            FOREIGN KEY(parent_id) REFERENCES document_folders(id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS documents(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_number TEXT,
            document_name TEXT NOT NULL,
            document_type TEXT,
            category TEXT,
            folder_id INTEGER,
            module_name TEXT,
            reference_id TEXT,
            company_id INTEGER,
            branch_id INTEGER,
            project_id INTEGER,
            uploaded_by TEXT,
            approved_by TEXT,
            version_number INTEGER DEFAULT 1,
            file_size INTEGER DEFAULT 0,
            file_extension TEXT,
            storage_path TEXT,
            hash_value TEXT,
            tags TEXT,
            description TEXT,
            status TEXT DEFAULT 'Active',
            approval_status TEXT DEFAULT 'Draft',
            confidential_flag INTEGER DEFAULT 0,
            archive_flag INTEGER DEFAULT 0,
            expiry_date TEXT,
            ocr_status TEXT DEFAULT 'pending',
            ocr_text TEXT,
            ocr_language TEXT,
            ocr_processed_at TEXT,
            ai_metadata_json TEXT,
            ai_classification TEXT,
            ai_confidence REAL,
            ai_extracted_at TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_by TEXT,
            modified_at TEXT,
            is_deleted INTEGER DEFAULT 0,
            deleted_by TEXT,
            deleted_at TEXT,
            customer_id INTEGER,
            FOREIGN KEY(folder_id) REFERENCES document_folders(id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS document_versions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            version_number INTEGER NOT NULL,
            storage_path TEXT NOT NULL,
            original_filename TEXT,
            file_size INTEGER DEFAULT 0,
            file_extension TEXT,
            hash_value TEXT,
            change_notes TEXT,
            uploaded_by TEXT,
            uploaded_at TEXT,
            ocr_status TEXT,
            ocr_text TEXT,
            ai_metadata_json TEXT,
            FOREIGN KEY(document_id) REFERENCES documents(id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS document_tags(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag_name TEXT NOT NULL UNIQUE,
            color TEXT,
            created_by TEXT,
            created_at TEXT,
            is_active INTEGER DEFAULT 1
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS document_tag_map(
            document_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            created_at TEXT,
            PRIMARY KEY(document_id, tag_id),
            FOREIGN KEY(document_id) REFERENCES documents(id),
            FOREIGN KEY(tag_id) REFERENCES document_tags(id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS document_shares(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            shared_with_user_id INTEGER,
            shared_with_role TEXT,
            permission TEXT DEFAULT 'view',
            expires_at TEXT,
            shared_by TEXT,
            shared_at TEXT,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY(document_id) REFERENCES documents(id)
        )
        """
    )
    for col, ctype in (
        ("company_id", "INTEGER"),
        ("branch_id", "INTEGER"),
        ("project_id", "INTEGER"),
        ("description", "TEXT"),
        ("sort_order", "INTEGER DEFAULT 0"),
        ("is_active", "INTEGER DEFAULT 1"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT"),
        ("modified_by", "TEXT"),
        ("modified_at", "TEXT"),
        ("is_deleted", "INTEGER DEFAULT 0"),
        ("deleted_by", "TEXT"),
        ("deleted_at", "TEXT"),
    ):
        _ensure_column(db, "document_folders", col, ctype)
    for col, ctype in (
        ("document_number", "TEXT"),
        ("document_type", "TEXT"),
        ("category", "TEXT"),
        ("folder_id", "INTEGER"),
        ("module_name", "TEXT"),
        ("reference_id", "TEXT"),
        ("company_id", "INTEGER"),
        ("branch_id", "INTEGER"),
        ("project_id", "INTEGER"),
        ("uploaded_by", "TEXT"),
        ("approved_by", "TEXT"),
        ("version_number", "INTEGER DEFAULT 1"),
        ("file_size", "INTEGER DEFAULT 0"),
        ("file_extension", "TEXT"),
        ("storage_path", "TEXT"),
        ("hash_value", "TEXT"),
        ("tags", "TEXT"),
        ("description", "TEXT"),
        ("status", "TEXT DEFAULT 'Active'"),
        ("approval_status", "TEXT DEFAULT 'Draft'"),
        ("confidential_flag", "INTEGER DEFAULT 0"),
        ("archive_flag", "INTEGER DEFAULT 0"),
        ("expiry_date", "TEXT"),
        ("ocr_status", "TEXT DEFAULT 'pending'"),
        ("ocr_text", "TEXT"),
        ("ocr_language", "TEXT"),
        ("ocr_processed_at", "TEXT"),
        ("ai_metadata_json", "TEXT"),
        ("ai_classification", "TEXT"),
        ("ai_confidence", "REAL"),
        ("ai_extracted_at", "TEXT"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT"),
        ("modified_by", "TEXT"),
        ("modified_at", "TEXT"),
        ("is_deleted", "INTEGER DEFAULT 0"),
        ("deleted_by", "TEXT"),
        ("deleted_at", "TEXT"),
        ("customer_id", "INTEGER"),
    ):
        _ensure_column(db, "documents", col, ctype)
    db.execute("CREATE INDEX IF NOT EXISTS idx_documents_module ON documents(module_name, reference_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_documents_folder ON documents(folder_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(hash_value)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_documents_expiry ON documents(expiry_date)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_doc_versions_doc ON document_versions(document_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_doc_tag_map_doc ON document_tag_map(document_id)")
    try:
        from audit_trail_service import ensure_audit_schema

        ensure_audit_schema(db)
    except Exception:
        pass
    _seed_default_folders(db)


def _seed_default_folders(db) -> None:
    if not _table_exists(db, "document_folders"):
        return
    count = db.execute(
        "SELECT COUNT(*) FROM document_folders WHERE COALESCE(is_deleted,0)=0"
    ).fetchone()[0]
    if count:
        return
    ts = _now_ts()
    for idx, name in enumerate(DEFAULT_FOLDERS):
        db.execute(
            """
            INSERT INTO document_folders(
                folder_name, parent_id, sort_order, is_active, created_at, created_by
            ) VALUES(?, NULL, ?, 1, ?, 'system')
            """,
            (name, idx, ts),
        )


def _next_document_number(db, company_id: int | None = None) -> str:
    prefix = f"DMS-{company_id or 0}-"
    row = db.execute(
        """
        SELECT document_number FROM documents
        WHERE document_number LIKE ? AND COALESCE(is_deleted,0)=0
        ORDER BY id DESC LIMIT 1
        """,
        (f"{prefix}%",),
    ).fetchone()
    seq = 1
    if row and row[0]:
        m = re.search(r"-(\d+)$", str(row[0]))
        if m:
            seq = int(m.group(1)) + 1
    return f"{prefix}{seq:05d}"


def log_document_audit(
    db,
    document_id: int,
    action: str,
    username: str,
    *,
    field_name: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
    remarks: str | None = None,
) -> None:
    try:
        from audit_trail_service import log_audit_event

        log_audit_event(
            db,
            record_table="documents",
            record_id=document_id,
            action=action,
            changed_by=username,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            remarks=remarks,
        )
    except Exception:
        pass


def list_document_audit_trail(db, document_id: int) -> list[dict[str, Any]]:
    try:
        from audit_trail_service import list_audit_trail

        return list_audit_trail(db, "documents", document_id)
    except Exception:
        return []


def find_duplicate_by_hash(db, hash_value: str, *, exclude_id: int | None = None) -> dict[str, Any] | None:
    if not hash_value:
        return None
    clause = "hash_value=? AND COALESCE(is_deleted,0)=0"
    params: list[Any] = [hash_value]
    if exclude_id:
        clause += " AND id<>?"
        params.append(exclude_id)
    row = db.execute(f"SELECT * FROM documents WHERE {clause} LIMIT 1", params).fetchone()
    return dict(row) if row else None


def list_folders(
    db,
    *,
    company_id: int | None = None,
    include_inactive: bool = False,
    include_deleted: bool = False,
) -> list[dict[str, Any]]:
    clauses = ["1=1"]
    params: list[Any] = []
    if not include_deleted:
        clauses.append("COALESCE(is_deleted,0)=0")
    if not include_inactive:
        clauses.append("COALESCE(is_active,1)=1")
    if company_id:
        clauses.append("(company_id IS NULL OR company_id=?)")
        params.append(company_id)
    where = " WHERE " + " AND ".join(clauses)
    rows = db.execute(
        f"SELECT * FROM document_folders{where} ORDER BY sort_order, folder_name",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def folder_tree(db, **kwargs) -> list[dict[str, Any]]:
    folders = list_folders(db, **kwargs)
    by_parent: dict[int | None, list[dict[str, Any]]] = {}
    for folder in folders:
        pid = folder.get("parent_id")
        by_parent.setdefault(pid, []).append(folder)

    def build(parent_id: int | None) -> list[dict[str, Any]]:
        nodes = []
        for item in sorted(by_parent.get(parent_id, []), key=lambda f: (f.get("sort_order") or 0, f.get("folder_name") or "")):
            node = dict(item)
            node["children"] = build(item["id"])
            nodes.append(node)
        return nodes

    return build(None)


def get_folder(db, folder_id: int) -> dict[str, Any] | None:
    row = db.execute(
        "SELECT * FROM document_folders WHERE id=? AND COALESCE(is_deleted,0)=0",
        (folder_id,),
    ).fetchone()
    return dict(row) if row else None


def save_folder(db, payload: dict[str, Any], username: str, folder_id: int | None = None) -> int:
    name = (payload.get("folder_name") or payload.get("name") or "").strip()
    if not name:
        raise ValueError("Folder name is required.")
    parent_id = payload.get("parent_id")
    if parent_id in ("", None):
        parent_id = None
    else:
        parent_id = int(parent_id)
    company_id = payload.get("company_id")
    branch_id = payload.get("branch_id")
    project_id = payload.get("project_id")
    description = (payload.get("description") or "").strip()
    sort_order = int(payload.get("sort_order") or 0)
    ts = _now_ts()
    if folder_id:
        db.execute(
            """
            UPDATE document_folders SET folder_name=?, parent_id=?, company_id=?, branch_id=?,
            project_id=?, description=?, sort_order=?, modified_by=?, modified_at=?
            WHERE id=? AND COALESCE(is_deleted,0)=0
            """,
            (name, parent_id, company_id, branch_id, project_id, description, sort_order, username, ts, folder_id),
        )
        return folder_id
    cur = db.execute(
        """
        INSERT INTO document_folders(
            folder_name, parent_id, company_id, branch_id, project_id, description,
            sort_order, is_active, created_by, created_at
        ) VALUES(?,?,?,?,?,?,?,1,?,?)
        """,
        (name, parent_id, company_id, branch_id, project_id, description, sort_order, username, ts),
    )
    return int(cur.lastrowid)


def soft_delete_folder(db, folder_id: int, username: str) -> None:
    doc_count = db.execute(
        "SELECT COUNT(*) FROM documents WHERE folder_id=? AND COALESCE(is_deleted,0)=0 AND COALESCE(archive_flag,0)=0",
        (folder_id,),
    ).fetchone()[0]
    if doc_count:
        raise ValueError("Folder contains active documents. Move or archive documents first.")
    child_count = db.execute(
        "SELECT COUNT(*) FROM document_folders WHERE parent_id=? AND COALESCE(is_deleted,0)=0",
        (folder_id,),
    ).fetchone()[0]
    if child_count:
        raise ValueError("Folder has sub-folders. Remove sub-folders first.")
    ts = _now_ts()
    db.execute(
        "UPDATE document_folders SET is_deleted=1, deleted_by=?, deleted_at=?, modified_by=?, modified_at=? WHERE id=?",
        (username, ts, username, ts, folder_id),
    )


def list_tags(db) -> list[dict[str, Any]]:
    rows = db.execute(
        "SELECT * FROM document_tags WHERE COALESCE(is_active,1)=1 ORDER BY tag_name"
    ).fetchall()
    return [dict(r) for r in rows]


def save_tag(db, tag_name: str, username: str, *, color: str = "") -> int:
    name = tag_name.strip()
    if not name:
        raise ValueError("Tag name is required.")
    existing = db.execute(
        "SELECT id FROM document_tags WHERE LOWER(tag_name)=LOWER(?)",
        (name,),
    ).fetchone()
    if existing:
        return int(existing[0])
    ts = _now_ts()
    cur = db.execute(
        "INSERT INTO document_tags(tag_name, color, created_by, created_at) VALUES(?,?,?,?)",
        (name, color or None, username, ts),
    )
    return int(cur.lastrowid)


def _sync_document_tags(db, document_id: int, tag_names: list[str], username: str) -> None:
    db.execute("DELETE FROM document_tag_map WHERE document_id=?", (document_id,))
    ts = _now_ts()
    for raw in tag_names:
        name = raw.strip()
        if not name:
            continue
        tag_id = save_tag(db, name, username)
        db.execute(
            "INSERT OR IGNORE INTO document_tag_map(document_id, tag_id, created_at) VALUES(?,?,?)",
            (document_id, tag_id, ts),
        )


def _document_tags_list(db, document_id: int) -> list[str]:
    rows = db.execute(
        """
        SELECT t.tag_name FROM document_tags t
        JOIN document_tag_map m ON m.tag_id=t.id
        WHERE m.document_id=?
        ORDER BY t.tag_name
        """,
        (document_id,),
    ).fetchall()
    return [r[0] for r in rows]


def _parse_tag_input(tags_value: str | list | None) -> list[str]:
    if isinstance(tags_value, list):
        return [str(t).strip() for t in tags_value if str(t).strip()]
    if not tags_value:
        return []
    if isinstance(tags_value, str) and tags_value.strip().startswith("["):
        try:
            parsed = json.loads(tags_value)
            if isinstance(parsed, list):
                return [str(t).strip() for t in parsed if str(t).strip()]
        except json.JSONDecodeError:
            pass
    return [t.strip() for t in str(tags_value).split(",") if t.strip()]


def _store_uploaded_file(
    file_storage,
    dest_root: str,
    document_id: int,
    version_number: int,
) -> tuple[str, int, str]:
    from werkzeug.utils import secure_filename

    original = secure_filename(file_storage.filename or "document")
    ext = os.path.splitext(original)[1].lower()
    subdir = os.path.join(dest_root, str(document_id))
    os.makedirs(subdir, exist_ok=True)
    stored_name = f"v{version_number}_{int(datetime.utcnow().timestamp())}_{original}"
    rel_path = os.path.join(str(document_id), stored_name).replace("\\", "/")
    abs_path = os.path.join(dest_root, str(document_id), stored_name)
    file_storage.save(abs_path)
    scan = virus_scan_file(abs_path)
    if not scan.get("clean", True):
        try:
            os.remove(abs_path)
        except OSError:
            pass
        raise ValueError(scan.get("message") or "File failed virus scan.")
    file_storage.seek(0)
    file_hash = compute_file_hash(file_storage)
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    return rel_path, size, file_hash


def _enrich_document_row(db, row: dict[str, Any]) -> dict[str, Any]:
    doc = dict(row)
    did = int(doc["id"])
    doc["tag_list"] = _document_tags_list(db, did)
    if doc.get("folder_id"):
        folder = get_folder(db, int(doc["folder_id"]))
        doc["folder_name"] = folder.get("folder_name") if folder else None
    days = _days_until(doc.get("expiry_date"))
    doc["days_until_expiry"] = days
    doc["expiry_status"] = _expiry_status_label(days)
    return doc


def _days_until(expiry_str: str | None, today: date | None = None) -> int | None:
    exp = _parse_date(expiry_str)
    if not exp:
        return None
    ref = today or date.today()
    return (exp - ref).days


def _expiry_status_label(days_left: int | None) -> str:
    if days_left is None:
        return "—"
    if days_left < 0:
        return "Expired"
    if days_left <= 30:
        return f"Due in {days_left}d"
    return "Valid"


def list_documents(
    db,
    *,
    search: str = "",
    folder_id: int | None = None,
    module_name: str = "",
    reference_id: str = "",
    category: str = "",
    document_type: str = "",
    status: str = "",
    approval_status: str = "",
    company_id: int | None = None,
    branch_id: int | None = None,
    project_id: int | None = None,
    tag: str = "",
    archive_flag: int | None = None,
    include_archived: bool = False,
    include_deleted: bool = False,
    confidential_only: bool = False,
    expiry_status: str = "",
    date_from: str = "",
    date_to: str = "",
    page: int = 1,
    per_page: int = 25,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> dict[str, Any]:
    clauses, params = _search_clauses(
        search=search,
        folder_id=folder_id,
        module_name=module_name,
        reference_id=reference_id,
        category=category,
        document_type=document_type,
        status=status,
        approval_status=approval_status,
        company_id=company_id,
        branch_id=branch_id,
        project_id=project_id,
        tag=tag,
        archive_flag=archive_flag,
        include_archived=include_archived,
        include_deleted=include_deleted,
        confidential_only=confidential_only,
        expiry_status=expiry_status,
        date_from=date_from,
        date_to=date_to,
    )
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    sort_col = sort_by if sort_by in DOCUMENT_SORT_COLUMNS else "created_at"
    direction = "DESC" if str(sort_dir).lower() == "desc" else "ASC"
    total = db.execute(f"SELECT COUNT(*) FROM documents d{where}", params).fetchone()[0]
    page = max(1, int(page or 1))
    per_page = min(max(1, int(per_page or 25)), 500)
    offset = (page - 1) * per_page
    rows = db.execute(
        f"""
        SELECT d.*, f.folder_name
        FROM documents d
        LEFT JOIN document_folders f ON f.id=d.folder_id
        {where}
        ORDER BY d.{sort_col} {direction}, d.id DESC
        LIMIT ? OFFSET ?
        """,
        params + [per_page, offset],
    ).fetchall()
    items = [_enrich_document_row(db, dict(r)) for r in rows]
    pages = max(1, (total + per_page - 1) // per_page)
    return {"items": items, "total": total, "page": page, "per_page": per_page, "pages": pages}


def _search_clauses(**kwargs) -> tuple[list[str], list[Any]]:
    clauses = ["1=1"]
    params: list[Any] = []
    if not kwargs.get("include_deleted"):
        clauses.append("COALESCE(d.is_deleted,0)=0")
    if kwargs.get("include_archived"):
        pass
    elif kwargs.get("archive_flag") is not None:
        clauses.append("COALESCE(d.archive_flag,0)=?")
        params.append(int(kwargs["archive_flag"]))
    else:
        clauses.append("COALESCE(d.archive_flag,0)=0")
    if kwargs.get("folder_id"):
        clauses.append("d.folder_id=?")
        params.append(kwargs["folder_id"])
    if kwargs.get("module_name"):
        clauses.append("LOWER(COALESCE(d.module_name,''))=?")
        params.append(str(kwargs["module_name"]).lower())
    if kwargs.get("reference_id"):
        clauses.append("d.reference_id=?")
        params.append(str(kwargs["reference_id"]))
    if kwargs.get("category"):
        clauses.append("d.category=?")
        params.append(kwargs["category"])
    if kwargs.get("document_type"):
        clauses.append("d.document_type=?")
        params.append(kwargs["document_type"])
    if kwargs.get("status"):
        clauses.append("d.status=?")
        params.append(kwargs["status"])
    if kwargs.get("approval_status"):
        clauses.append("d.approval_status=?")
        params.append(kwargs["approval_status"])
    if kwargs.get("company_id"):
        clauses.append("(d.company_id IS NULL OR d.company_id=?)")
        params.append(kwargs["company_id"])
    if kwargs.get("branch_id"):
        clauses.append("(d.branch_id IS NULL OR d.branch_id=?)")
        params.append(kwargs["branch_id"])
    if kwargs.get("project_id"):
        clauses.append("(d.project_id IS NULL OR d.project_id=?)")
        params.append(kwargs["project_id"])
    if kwargs.get("confidential_only"):
        clauses.append("COALESCE(d.confidential_flag,0)=1")
    if kwargs.get("date_from"):
        clauses.append("d.created_at>=?")
        params.append(kwargs["date_from"])
    if kwargs.get("date_to"):
        clauses.append("d.created_at<=?")
        params.append(kwargs["date_to"] + " 23:59:59")
    search = (kwargs.get("search") or "").strip()
    if search:
        like = f"%{search.lower()}%"
        clauses.append(
            "("
            "LOWER(COALESCE(d.document_name,'')) LIKE ? OR "
            "LOWER(COALESCE(d.document_number,'')) LIKE ? OR "
            "LOWER(COALESCE(d.description,'')) LIKE ? OR "
            "LOWER(COALESCE(d.tags,'')) LIKE ? OR "
            "LOWER(COALESCE(d.module_name,'')) LIKE ? OR "
            "LOWER(COALESCE(d.ocr_text,'')) LIKE ?"
            ")"
        )
        params.extend([like] * 6)
    tag = (kwargs.get("tag") or "").strip()
    if tag:
        clauses.append(
            "EXISTS (SELECT 1 FROM document_tag_map m JOIN document_tags t ON t.id=m.tag_id "
            "WHERE m.document_id=d.id AND LOWER(t.tag_name)=LOWER(?))"
        )
        params.append(tag)
    expiry_status = (kwargs.get("expiry_status") or "").strip()
    today = _today()
    if expiry_status == "expired":
        clauses.append("d.expiry_date IS NOT NULL AND d.expiry_date != '' AND d.expiry_date < ?")
        params.append(today)
    elif expiry_status == "expiring":
        clauses.append("d.expiry_date IS NOT NULL AND d.expiry_date != '' AND d.expiry_date >= ?")
        params.append(today)
    return clauses, params


def get_document(db, document_id: int, *, include_deleted: bool = False) -> dict[str, Any] | None:
    clause = "d.id=?"
    if not include_deleted:
        clause += " AND COALESCE(d.is_deleted,0)=0"
    row = db.execute(
        f"""
        SELECT d.*, f.folder_name
        FROM documents d
        LEFT JOIN document_folders f ON f.id=d.folder_id
        WHERE {clause}
        """,
        (document_id,),
    ).fetchone()
    if not row:
        return None
    doc = _enrich_document_row(db, dict(row))
    doc["versions"] = list_document_versions(db, document_id)
    doc["shares"] = list_document_shares(db, document_id)
    return doc


def list_document_versions(db, document_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        "SELECT * FROM document_versions WHERE document_id=? ORDER BY version_number DESC",
        (document_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_document_version(db, document_id: int, version_number: int | None = None) -> dict[str, Any] | None:
    if version_number is None:
        row = db.execute(
            "SELECT * FROM documents WHERE id=? AND COALESCE(is_deleted,0)=0",
            (document_id,),
        ).fetchone()
        if not row:
            return None
        version_number = int(row["version_number"] or 1)
    ver = db.execute(
        "SELECT * FROM document_versions WHERE document_id=? AND version_number=?",
        (document_id, version_number),
    ).fetchone()
    return dict(ver) if ver else None


def save_document(
    db,
    payload: dict[str, Any],
    username: str,
    file_storage=None,
    *,
    dest_root: str,
    document_id: int | None = None,
    customer_id: int | None = None,
    allow_duplicate: bool = False,
) -> int:
    name = (payload.get("document_name") or payload.get("title") or "").strip()
    if not name:
        raise ValueError("Document name is required.")
    folder_id = payload.get("folder_id")
    if folder_id in ("", None):
        folder_id = None
    else:
        folder_id = int(folder_id)
    if folder_id and not get_folder(db, folder_id):
        raise ValueError("Select a valid folder.")
    doc_type = (payload.get("document_type") or payload.get("doc_type") or "Other").strip()
    category = (payload.get("category") or doc_type or "Other").strip()
    module_name = (payload.get("module_name") or "enterprise_dms").strip()
    reference_id = str(payload.get("reference_id") or "").strip() or None
    company_id = payload.get("company_id")
    branch_id = payload.get("branch_id")
    project_id = payload.get("project_id")
    description = (payload.get("description") or payload.get("notes") or "").strip()
    expiry_date = (payload.get("expiry_date") or "").strip()[:10] or None
    confidential = 1 if str(payload.get("confidential_flag", "")).lower() in ("1", "true", "on", "yes") else 0
    change_notes = (payload.get("change_notes") or "").strip()
    tag_names = _parse_tag_input(payload.get("tags"))
    ts = _now_ts()

    if document_id:
        existing = get_document(db, document_id)
        if not existing:
            raise ValueError("Document not found.")
        version_number = int(existing.get("version_number") or 1)
        storage_path = existing.get("storage_path")
        file_size = int(existing.get("file_size") or 0)
        file_ext = existing.get("file_extension")
        file_hash = existing.get("hash_value")
        if file_storage and getattr(file_storage, "filename", None):
            ext, err = validate_dms_upload(file_storage, required=True)
            if err:
                raise ValueError(err)
            version_number += 1
            storage_path, file_size, file_hash = _store_uploaded_file(
                file_storage, dest_root, document_id, version_number
            )
            if not allow_duplicate:
                dup = find_duplicate_by_hash(db, file_hash, exclude_id=document_id)
                if dup:
                    raise ValueError(
                        f"Duplicate file detected (matches document {dup.get('document_number') or dup.get('id')})."
                    )
            file_ext = ext
            db.execute(
                """
                INSERT INTO document_versions(
                    document_id, version_number, storage_path, original_filename,
                    file_size, file_extension, hash_value, change_notes, uploaded_by, uploaded_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    document_id,
                    version_number,
                    storage_path,
                    file_storage.filename,
                    file_size,
                    file_ext,
                    file_hash,
                    change_notes or f"Version {version_number}",
                    username,
                    ts,
                ),
            )
        db.execute(
            """
            UPDATE documents SET document_name=?, document_type=?, category=?, folder_id=?,
            module_name=?, reference_id=?, company_id=?, branch_id=?, project_id=?,
            description=?, expiry_date=?, confidential_flag=?, version_number=?,
            file_size=?, file_extension=?, storage_path=?, hash_value=?, tags=?,
            modified_by=?, modified_at=?
            WHERE id=?
            """,
            (
                name,
                doc_type,
                category,
                folder_id,
                module_name,
                reference_id,
                company_id,
                branch_id,
                project_id,
                description,
                expiry_date,
                confidential,
                version_number,
                file_size,
                file_ext,
                storage_path,
                file_hash,
                ", ".join(tag_names),
                username,
                ts,
                document_id,
            ),
        )
        _sync_document_tags(db, document_id, tag_names, username)
        log_document_audit(db, document_id, "update", username, remarks=change_notes or "Document updated")
        return document_id

    if not file_storage or not getattr(file_storage, "filename", None):
        raise ValueError("Upload a document file.")
    ext, err = validate_dms_upload(file_storage, required=True)
    if err:
        raise ValueError(err)
    file_storage.seek(0)
    file_hash = compute_file_hash(file_storage)
    if not allow_duplicate:
        dup = find_duplicate_by_hash(db, file_hash)
        if dup:
            raise ValueError(
                f"Duplicate file detected (matches document {dup.get('document_number') or dup.get('id')})."
            )
    doc_number = _next_document_number(db, int(company_id) if company_id else None)
    cur = db.execute(
        """
        INSERT INTO documents(
            document_number, document_name, document_type, category, folder_id,
            module_name, reference_id, company_id, branch_id, project_id,
            uploaded_by, version_number, status, approval_status, confidential_flag,
            description, expiry_date, tags, created_by, created_at, customer_id
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,1,'Active','Draft',?,?,?,?,?,?,?)
        """,
        (
            doc_number,
            name,
            doc_type,
            category,
            folder_id,
            module_name,
            reference_id,
            company_id,
            branch_id,
            project_id,
            username,
            confidential,
            description,
            expiry_date,
            ", ".join(tag_names),
            username,
            ts,
            customer_id,
        ),
    )
    new_id = int(cur.lastrowid)
    storage_path, file_size, file_hash = _store_uploaded_file(file_storage, dest_root, new_id, 1)
    db.execute(
        """
        UPDATE documents SET storage_path=?, file_size=?, file_extension=?, hash_value=?,
        modified_by=?, modified_at=? WHERE id=?
        """,
        (storage_path, file_size, ext, file_hash, username, ts, new_id),
    )
    db.execute(
        """
        INSERT INTO document_versions(
            document_id, version_number, storage_path, original_filename,
            file_size, file_extension, hash_value, change_notes, uploaded_by, uploaded_at
        ) VALUES(?,1,?,?,?,?,?,?,?,?)
        """,
        (new_id, storage_path, file_storage.filename, file_size, ext, file_hash, "Initial upload", username, ts),
    )
    _sync_document_tags(db, new_id, tag_names, username)
    log_document_audit(db, new_id, "create", username, remarks="Document uploaded")
    return new_id


def rollback_document_version(
    db,
    document_id: int,
    version_number: int,
    username: str,
) -> None:
    doc = get_document(db, document_id)
    if not doc:
        raise ValueError("Document not found.")
    ver = get_document_version(db, document_id, version_number)
    if not ver:
        raise ValueError("Version not found.")
    ts = _now_ts()
    db.execute(
        """
        UPDATE documents SET version_number=?, storage_path=?, file_size=?, file_extension=?,
        hash_value=?, modified_by=?, modified_at=?
        WHERE id=?
        """,
        (
            version_number,
            ver["storage_path"],
            ver.get("file_size"),
            ver.get("file_extension"),
            ver.get("hash_value"),
            username,
            ts,
            document_id,
        ),
    )
    log_document_audit(
        db,
        document_id,
        "rollback",
        username,
        remarks=f"Rolled back to version {version_number}",
    )


def rename_document(db, document_id: int, new_name: str, username: str) -> None:
    name = new_name.strip()
    if not name:
        raise ValueError("Document name is required.")
    if not get_document(db, document_id):
        raise ValueError("Document not found.")
    ts = _now_ts()
    db.execute(
        "UPDATE documents SET document_name=?, modified_by=?, modified_at=? WHERE id=?",
        (name, username, ts, document_id),
    )
    log_document_audit(db, document_id, "rename", username, new_value=name)


def move_document_folder(db, document_id: int, folder_id: int | None, username: str) -> None:
    if folder_id and not get_folder(db, folder_id):
        raise ValueError("Folder not found.")
    if not get_document(db, document_id):
        raise ValueError("Document not found.")
    ts = _now_ts()
    db.execute(
        "UPDATE documents SET folder_id=?, modified_by=?, modified_at=? WHERE id=?",
        (folder_id, username, ts, document_id),
    )
    log_document_audit(db, document_id, "move", username, remarks=f"Moved to folder {folder_id}")


def soft_delete_document(db, document_id: int, username: str) -> None:
    if not get_document(db, document_id):
        raise ValueError("Document not found.")
    ts = _now_ts()
    db.execute(
        "UPDATE documents SET is_deleted=1, deleted_by=?, deleted_at=?, modified_by=?, modified_at=? WHERE id=?",
        (username, ts, username, ts, document_id),
    )
    log_document_audit(db, document_id, "delete", username, remarks="Soft deleted")


def archive_document(db, document_id: int, username: str) -> None:
    if not get_document(db, document_id):
        raise ValueError("Document not found.")
    ts = _now_ts()
    db.execute(
        "UPDATE documents SET archive_flag=1, modified_by=?, modified_at=? WHERE id=?",
        (username, ts, document_id),
    )
    log_document_audit(db, document_id, "archive", username)


def restore_document(db, document_id: int, username: str, *, from_archive: bool = True) -> None:
    row = db.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
    if not row:
        raise ValueError("Document not found.")
    ts = _now_ts()
    if from_archive:
        db.execute(
            "UPDATE documents SET archive_flag=0, modified_by=?, modified_at=? WHERE id=?",
            (username, ts, document_id),
        )
        log_document_audit(db, document_id, "restore", username, remarks="Restored from archive")
    else:
        db.execute(
            """
            UPDATE documents SET is_deleted=0, deleted_by=NULL, deleted_at=NULL,
            modified_by=?, modified_at=? WHERE id=?
            """,
            (username, ts, document_id),
        )
        log_document_audit(db, document_id, "restore", username, remarks="Restored from trash")


def approve_document(db, document_id: int, username: str) -> None:
    if not get_document(db, document_id):
        raise ValueError("Document not found.")
    ts = _now_ts()
    db.execute(
        """
        UPDATE documents SET approval_status='Approved', approved_by=?, status='Active',
        modified_by=?, modified_at=? WHERE id=?
        """,
        (username, username, ts, document_id),
    )
    log_document_audit(db, document_id, "approve", username)


def reject_document(db, document_id: int, username: str, remarks: str = "") -> None:
    if not get_document(db, document_id):
        raise ValueError("Document not found.")
    ts = _now_ts()
    db.execute(
        "UPDATE documents SET approval_status='Rejected', modified_by=?, modified_at=? WHERE id=?",
        (username, ts, document_id),
    )
    log_document_audit(db, document_id, "reject", username, remarks=remarks or "Rejected")


def submit_document_for_approval(db, document_id: int, username: str) -> None:
    if not get_document(db, document_id):
        raise ValueError("Document not found.")
    ts = _now_ts()
    db.execute(
        "UPDATE documents SET approval_status='Pending', modified_by=?, modified_at=? WHERE id=?",
        (username, ts, document_id),
    )
    log_document_audit(db, document_id, "submit", username, remarks="Submitted for approval")


def list_document_shares(db, document_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        "SELECT * FROM document_shares WHERE document_id=? AND COALESCE(is_active,1)=1",
        (document_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def share_document(
    db,
    document_id: int,
    username: str,
    *,
    shared_with_user_id: int | None = None,
    shared_with_role: str = "",
    permission: str = "view",
    expires_at: str | None = None,
) -> int:
    if not get_document(db, document_id):
        raise ValueError("Document not found.")
    if not shared_with_user_id and not shared_with_role:
        raise ValueError("Specify a user or role to share with.")
    ts = _now_ts()
    cur = db.execute(
        """
        INSERT INTO document_shares(
            document_id, shared_with_user_id, shared_with_role, permission,
            expires_at, shared_by, shared_at, is_active
        ) VALUES(?,?,?,?,?,?,?,1)
        """,
        (document_id, shared_with_user_id, shared_with_role or None, permission, expires_at, username, ts),
    )
    log_document_audit(db, document_id, "share", username, remarks=f"Shared ({permission})")
    return int(cur.lastrowid)


def revoke_document_share(db, share_id: int, username: str) -> None:
    row = db.execute("SELECT document_id FROM document_shares WHERE id=?", (share_id,)).fetchone()
    if not row:
        raise ValueError("Share not found.")
    db.execute("UPDATE document_shares SET is_active=0 WHERE id=?", (share_id,))
    log_document_audit(db, int(row[0]), "unshare", username)


def get_document_download_path(
    db,
    document_id: int,
    *,
    dest_root: str,
    version: int | None = None,
) -> tuple[str, str] | None:
    """Return (absolute_path, download_name) for a document version."""
    ver = get_document_version(db, document_id, version)
    if not ver:
        return None
    rel = ver.get("storage_path") or ""
    abs_path = os.path.join(dest_root, rel.replace("/", os.sep))
    if not os.path.isfile(abs_path):
        return None
    name = ver.get("original_filename") or os.path.basename(rel)
    return abs_path, name


def attach_document(
    db,
    module_name: str,
    reference_id: str | int,
    file_storage,
    user: str,
    *,
    dest_root: str,
    **meta,
) -> int:
    """Integration helper — attach a file to any ERP module record."""
    payload = dict(meta)
    payload["module_name"] = module_name
    payload["reference_id"] = str(reference_id)
    payload.setdefault("document_name", getattr(file_storage, "filename", None) or "Attachment")
    return save_document(db, payload, user, file_storage, dest_root=dest_root)


def list_module_documents(
    db,
    module_name: str,
    reference_id: str | int,
    *,
    include_deleted: bool = False,
) -> list[dict[str, Any]]:
    listing = list_documents(
        db,
        module_name=module_name,
        reference_id=str(reference_id),
        include_deleted=include_deleted,
        per_page=500,
    )
    return listing["items"]


def document_report(db, report_key: str, **filters) -> list[dict[str, Any]]:
    key = (report_key or "").lower().strip()
    if key == "register":
        return list_documents(db, per_page=10000, **filters)["items"]
    if key == "expiry":
        return list_documents(db, expiry_status="expiring", per_page=10000, **filters)["items"]
    if key == "expired":
        return list_documents(db, expiry_status="expired", per_page=10000, **filters)["items"]
    if key == "archived":
        return list_documents(db, archive_flag=1, per_page=10000, **filters)["items"]
    if key == "versions":
        rows = db.execute(
            """
            SELECT d.document_number, d.document_name, v.version_number, v.original_filename,
                   v.file_size, v.uploaded_by, v.uploaded_at
            FROM document_versions v
            JOIN documents d ON d.id=v.document_id
            WHERE COALESCE(d.is_deleted,0)=0
            ORDER BY v.uploaded_at DESC
            LIMIT 5000
            """
        ).fetchall()
        return [dict(r) for r in rows]
    if key == "storage":
        row = db.execute(
            """
            SELECT COUNT(*) AS doc_count, COALESCE(SUM(file_size),0) AS total_bytes
            FROM documents WHERE COALESCE(is_deleted,0)=0
            """
        ).fetchone()
        by_ext = db.execute(
            """
            SELECT COALESCE(file_extension,'unknown') AS ext, COUNT(*) AS cnt, SUM(file_size) AS bytes
            FROM documents WHERE COALESCE(is_deleted,0)=0
            GROUP BY COALESCE(file_extension,'unknown')
            ORDER BY bytes DESC
            """
        ).fetchall()
        return [{"summary": dict(row), "by_extension": [dict(r) for r in by_ext]}]
    raise ValueError(f"Unknown report: {report_key}")


def export_documents_csv(db, **filters) -> str:
    rows = list_documents(db, per_page=10000, **filters)["items"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=DOCUMENT_EXPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in DOCUMENT_EXPORT_COLUMNS})
    return buf.getvalue()


def export_documents_excel(db, **filters) -> BytesIO:
    try:
        from openpyxl import Workbook
    except ImportError as exc:
        raise RuntimeError("openpyxl is required for Excel export.") from exc
    rows = list_documents(db, per_page=10000, **filters)["items"]
    wb = Workbook()
    ws = wb.active
    ws.title = "Documents"
    ws.append(list(DOCUMENT_EXPORT_COLUMNS))
    for row in rows:
        ws.append([row.get(c, "") for c in DOCUMENT_EXPORT_COLUMNS])
    out = BytesIO()
    wb.save(out)
    out.seek(0)
    return out


def ai_extract_metadata(db, document_id: int | None = None, *, form: dict | None = None) -> dict[str, Any]:
    """AI metadata extraction — graceful fallback without ai_service."""
    hints: dict[str, Any] = {"source": "fallback", "fields": {}}
    src = form or {}
    if document_id:
        doc = get_document(db, document_id)
        if doc:
            src = doc
    name = (src.get("document_name") or "").lower()
    for cat in DOCUMENT_CATEGORIES:
        if cat.lower() in name:
            hints["fields"]["category"] = cat
            hints["fields"]["document_type"] = cat
            break
    if "contract" in name or "agreement" in name:
        hints["fields"]["category"] = "Contract"
    if src.get("description"):
        hints["fields"]["description_summary"] = str(src["description"])[:200]
    hints["confidence"] = 0.35 if hints["fields"] else 0.1
    hints["message"] = "Rule-based metadata hints (connect ai_service for full extraction)."
    return hints


def ai_classify_document(db, document_id: int) -> dict[str, Any]:
    doc = get_document(db, document_id)
    if not doc:
        return {"ok": False, "error": "Document not found"}
    meta = ai_extract_metadata(db, document_id=document_id)
    classification = meta.get("fields", {}).get("category", "Other")
    confidence = float(meta.get("confidence") or 0.1)
    ts = _now_ts()
    db.execute(
        """
        UPDATE documents SET ai_classification=?, ai_confidence=?, ai_metadata_json=?,
        ai_extracted_at=?, modified_at=? WHERE id=?
        """,
        (classification, confidence, json.dumps(meta), ts, ts, document_id),
    )
    return {"ok": True, "classification": classification, "confidence": confidence, "metadata": meta}


def ai_duplicate_check(db, document_id: int) -> dict[str, Any]:
    doc = get_document(db, document_id)
    if not doc:
        return {"ok": False, "error": "Document not found"}
    hv = doc.get("hash_value")
    dup = find_duplicate_by_hash(db, hv or "", exclude_id=document_id) if hv else None
    return {
        "ok": True,
        "is_duplicate": bool(dup),
        "duplicate_document_id": dup.get("id") if dup else None,
        "duplicate_document_number": dup.get("document_number") if dup else None,
    }


def user_can_document_management(
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
        "restore": "edit",
        "rollback": "edit",
        "rename": "edit",
        "move": "edit",
        "share": "edit",
        "unshare": "edit",
        "submit": "upload",
        "archive": "delete",
    }
    check = action_map.get(action, action)
    try:
        from user_permission_service import (
            empty_permission_actions,
            ensure_user_tab_permissions_schema,
            normalize_permission_actions,
        )

        ensure_user_tab_permissions_schema(db)
        row = db.execute(
            """
            SELECT granted, action_flags FROM user_tab_permissions
            WHERE user_id=? AND granted=1 AND endpoint='document_management'
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
            return bool(actions.get("import") or actions.get("upload"))
        if check == "delete":
            return bool(actions.get("delete") or actions.get("edit"))
        if check == "download":
            return bool(actions.get("download") or actions.get("view"))
        return bool(actions.get(check))
    except Exception:
        return False


def mobile_offline_cache_metadata(db, user_id: int | None, *, limit: int = 100) -> list[dict[str, Any]]:
    listing = list_documents(db, per_page=limit, sort_by="modified_at", sort_dir="desc")
    return [
        {
            "id": d["id"],
            "document_number": d.get("document_number"),
            "document_name": d.get("document_name"),
            "module_name": d.get("module_name"),
            "reference_id": d.get("reference_id"),
            "version_number": d.get("version_number"),
            "file_extension": d.get("file_extension"),
            "file_size": d.get("file_size"),
            "modified_at": d.get("modified_at"),
            "approval_status": d.get("approval_status"),
        }
        for d in listing["items"]
    ]
