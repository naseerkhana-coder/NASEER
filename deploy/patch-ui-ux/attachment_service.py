"""Universal attachment storage for all ERP modules."""

from __future__ import annotations

import mimetypes
import os
import uuid
from datetime import datetime
from typing import Any

ALLOWED_EXTENSIONS = frozenset(
    {
        ".pdf",
        ".xls",
        ".xlsx",
        ".csv",
        ".doc",
        ".docx",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".dwg",
        ".dxf",
        ".tif",
        ".tiff",
    }
)
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024


def _table_exists(db, table: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def ensure_attachment_schema(db) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS erp_attachments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id TEXT NOT NULL,
            record_table TEXT NOT NULL,
            record_id INTEGER NOT NULL,
            original_filename TEXT NOT NULL,
            stored_filename TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            mime_type TEXT,
            file_size INTEGER DEFAULT 0,
            uploaded_by TEXT,
            uploaded_at TEXT,
            replaced_by_id INTEGER,
            is_active INTEGER DEFAULT 1,
            deleted_by TEXT,
            deleted_at TEXT
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_erp_attachments_record "
        "ON erp_attachments(record_table, record_id, is_active)"
    )


def _validate_file(file_storage) -> tuple[str, int]:
    if not file_storage or not file_storage.filename:
        raise ValueError("No file selected")
    filename = os.path.basename(file_storage.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"File type {ext} is not allowed")
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_ATTACHMENT_BYTES:
        raise ValueError("File exceeds maximum upload size (25 MB)")
    return filename, size


def save_attachment(
    db,
    uploads_root: str,
    file_storage,
    *,
    module_id: str,
    record_table: str,
    record_id: int,
    uploaded_by: str,
    replace_id: int | None = None,
) -> dict[str, Any]:
    ensure_attachment_schema(db)
    original, size = _validate_file(file_storage)
    subdir = os.path.join(uploads_root, "erp_attachments", record_table)
    os.makedirs(subdir, exist_ok=True)
    stored = f"{uuid.uuid4().hex}{os.path.splitext(original)[1].lower()}"
    path = os.path.join(subdir, stored)
    file_storage.save(path)
    mime = file_storage.mimetype or mimetypes.guess_type(original)[0] or "application/octet-stream"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = db.execute(
        """
        INSERT INTO erp_attachments(
            module_id, record_table, record_id, original_filename, stored_filename,
            stored_path, mime_type, file_size, uploaded_by, uploaded_at, is_active
        ) VALUES(?,?,?,?,?,?,?,?,?,?,1)
        """,
        (
            module_id,
            record_table,
            int(record_id),
            original,
            stored,
            path,
            mime,
            size,
            uploaded_by,
            now,
        ),
    )
    new_id = cur.lastrowid
    if replace_id:
        db.execute(
            """
            UPDATE erp_attachments SET is_active=0, replaced_by_id=?, deleted_at=?, deleted_by=?
            WHERE id=? AND record_table=? AND record_id=?
            """,
            (new_id, now, uploaded_by, replace_id, record_table, record_id),
        )
    db.commit()
    return get_attachment(db, new_id)


def list_attachments(db, record_table: str, record_id: int, active_only: bool = True) -> list[dict[str, Any]]:
    ensure_attachment_schema(db)
    sql = (
        "SELECT * FROM erp_attachments WHERE record_table=? AND record_id=?"
    )
    params: list[Any] = [record_table, int(record_id)]
    if active_only:
        sql += " AND is_active=1"
    sql += " ORDER BY uploaded_at DESC, id DESC"
    rows = db.execute(sql, tuple(params)).fetchall()
    return [dict(r) for r in rows]


def get_attachment(db, attachment_id: int) -> dict[str, Any] | None:
    ensure_attachment_schema(db)
    row = db.execute("SELECT * FROM erp_attachments WHERE id=?", (attachment_id,)).fetchone()
    return dict(row) if row else None


def delete_attachment(
    db,
    attachment_id: int,
    *,
    deleted_by: str,
    hard: bool = False,
) -> bool:
    ensure_attachment_schema(db)
    row = get_attachment(db, attachment_id)
    if not row:
        return False
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if hard:
        if row.get("stored_path") and os.path.isfile(row["stored_path"]):
            try:
                os.remove(row["stored_path"])
            except OSError:
                pass
        db.execute("DELETE FROM erp_attachments WHERE id=?", (attachment_id,))
    else:
        db.execute(
            "UPDATE erp_attachments SET is_active=0, deleted_by=?, deleted_at=? WHERE id=?",
            (deleted_by, now, attachment_id),
        )
    db.commit()
    return True
