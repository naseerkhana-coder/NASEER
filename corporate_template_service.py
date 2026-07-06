"""Corporate report template master — branding, letterhead, footer, print layout."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime
from typing import Any

DEFAULT_PRIMARY = "#E30613"
DEFAULT_SECONDARY = "#232323"
DEFAULT_BACKGROUND = "#FFFFFF"
DEFAULT_FONT = "Arial, Helvetica, sans-serif"
DEFAULT_HEADER_LINE1 = "MAXEK PRIVATE LIMITED"
DEFAULT_HEADER_LINE2 = "MAXEK CONSTRUCTION SYSTEM"
DEFAULT_COMPANY_LOGO = "maxek-logo.jpg"

FONT_OPTIONS = (
    "Arial, Helvetica, sans-serif",
    "Georgia, serif",
    "Times New Roman, Times, serif",
    "Verdana, Geneva, sans-serif",
)

PDF_ORIENTATIONS = ("portrait", "landscape")

TEMPLATE_ASSET_FIELDS = (
    "company_logo_path",
    "watermark_logo_path",
    "company_seal_path",
    "signatory_image_path",
)

MAX_TEMPLATE_UPLOAD_BYTES = 5 * 1024 * 1024
TEMPLATE_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}


def _table_exists(db, table: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _ensure_column(db, table: str, column: str, col_type: str) -> None:
    if not _table_exists(db, table):
        return
    try:
        cols = [row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in cols:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
    except Exception:
        pass


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def validate_template_upload(file_storage, required: bool = False) -> tuple[str | None, str | None]:
    if not file_storage or not file_storage.filename:
        if required:
            return None, "Select an image file to upload."
        return None, None
    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in TEMPLATE_ALLOWED_EXTENSIONS:
        return None, "Allowed image types: PNG, JPG, JPEG, GIF, WEBP, SVG."
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_TEMPLATE_UPLOAD_BYTES:
        return None, "Image is too large (maximum 5 MB)."
    return ext, None


def ensure_corporate_template_schema(db) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS corporate_report_templates(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_name TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            is_default INTEGER DEFAULT 0,
            company_logo_path TEXT,
            watermark_logo_path TEXT,
            company_seal_path TEXT,
            signatory_image_path TEXT,
            letterhead_html TEXT,
            footer_html TEXT,
            primary_color TEXT DEFAULT '#E30613',
            secondary_color TEXT DEFAULT '#232323',
            background_color TEXT DEFAULT '#FFFFFF',
            font_family TEXT DEFAULT 'Arial, Helvetica, sans-serif',
            pdf_orientation TEXT DEFAULT 'portrait',
            footer_address TEXT,
            footer_phone TEXT,
            footer_email TEXT,
            footer_website TEXT,
            header_title_line1 TEXT DEFAULT 'MAXEK PRIVATE LIMITED',
            header_title_line2 TEXT DEFAULT 'MAXEK CONSTRUCTION SYSTEM',
            created_by TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_corp_templates_default "
        "ON corporate_report_templates(is_default, is_active)"
    )
    for col, ctype in (
        ("template_name", "TEXT NOT NULL"),
        ("is_active", "INTEGER DEFAULT 1"),
        ("is_default", "INTEGER DEFAULT 0"),
        ("company_logo_path", "TEXT"),
        ("watermark_logo_path", "TEXT"),
        ("company_seal_path", "TEXT"),
        ("signatory_image_path", "TEXT"),
        ("letterhead_html", "TEXT"),
        ("footer_html", "TEXT"),
        ("primary_color", "TEXT DEFAULT '#E30613'"),
        ("secondary_color", "TEXT DEFAULT '#232323'"),
        ("background_color", "TEXT DEFAULT '#FFFFFF'"),
        ("font_family", "TEXT DEFAULT 'Arial, Helvetica, sans-serif'"),
        ("pdf_orientation", "TEXT DEFAULT 'portrait'"),
        ("footer_address", "TEXT"),
        ("footer_phone", "TEXT"),
        ("footer_email", "TEXT"),
        ("footer_website", "TEXT"),
        ("header_title_line1", "TEXT DEFAULT 'MAXEK PRIVATE LIMITED'"),
        ("header_title_line2", "TEXT DEFAULT 'MAXEK CONSTRUCTION SYSTEM'"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT"),
        ("updated_at", "TEXT"),
    ):
        _ensure_column(db, "corporate_report_templates", col, ctype)
    _seed_default_template(db)


def _seed_default_template(db) -> None:
    if not _table_exists(db, "corporate_report_templates"):
        return
    row = db.execute(
        "SELECT id FROM corporate_report_templates WHERE is_default=1 LIMIT 1"
    ).fetchone()
    if row:
        return
    ts = _now_ts()
    db.execute(
        """
        INSERT INTO corporate_report_templates(
            template_name, is_active, is_default,
            primary_color, secondary_color, background_color, font_family,
            pdf_orientation, header_title_line1, header_title_line2,
            footer_address, footer_phone, footer_email, footer_website,
            created_by, created_at, updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "MAXEK Standard",
            1,
            1,
            DEFAULT_PRIMARY,
            DEFAULT_SECONDARY,
            DEFAULT_BACKGROUND,
            DEFAULT_FONT,
            "portrait",
            DEFAULT_HEADER_LINE1,
            DEFAULT_HEADER_LINE2,
            "MAXEK Private Limited, Corporate Office",
            "+91-XXXXXXXXXX",
            "info@maxek.com",
            "www.maxek.com",
            "system",
            ts,
            ts,
        ),
    )


def _row_to_dict(row) -> dict[str, Any]:
    return dict(row) if row else {}


def list_templates(db) -> list[dict[str, Any]]:
    if not _table_exists(db, "corporate_report_templates"):
        return []
    rows = db.execute(
        "SELECT * FROM corporate_report_templates ORDER BY is_default DESC, template_name"
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_template(db, template_id: int) -> dict[str, Any] | None:
    if not template_id or not _table_exists(db, "corporate_report_templates"):
        return None
    row = db.execute(
        "SELECT * FROM corporate_report_templates WHERE id=?",
        (template_id,),
    ).fetchone()
    return _row_to_dict(row) if row else None


def get_active_template(db, template_id: int | None = None) -> dict[str, Any]:
    if template_id:
        found = get_template(db, template_id)
        if found and found.get("is_active"):
            return found
    if not _table_exists(db, "corporate_report_templates"):
        return _fallback_template()
    row = db.execute(
        "SELECT * FROM corporate_report_templates WHERE is_default=1 AND is_active=1 LIMIT 1"
    ).fetchone()
    if row:
        return _row_to_dict(row)
    row = db.execute(
        "SELECT * FROM corporate_report_templates WHERE is_active=1 ORDER BY id LIMIT 1"
    ).fetchone()
    return _row_to_dict(row) if row else _fallback_template()


def _fallback_template() -> dict[str, Any]:
    return {
        "id": None,
        "template_name": "MAXEK Standard (built-in)",
        "is_active": 1,
        "is_default": 1,
        "primary_color": DEFAULT_PRIMARY,
        "secondary_color": DEFAULT_SECONDARY,
        "background_color": DEFAULT_BACKGROUND,
        "font_family": DEFAULT_FONT,
        "pdf_orientation": "portrait",
        "header_title_line1": DEFAULT_HEADER_LINE1,
        "header_title_line2": DEFAULT_HEADER_LINE2,
        "footer_address": "MAXEK Private Limited, Corporate Office",
        "footer_phone": "+91-XXXXXXXXXX",
        "footer_email": "info@maxek.com",
        "footer_website": "www.maxek.com",
        "company_logo_path": DEFAULT_COMPANY_LOGO,
        "watermark_logo_path": None,
        "company_seal_path": None,
        "signatory_image_path": None,
        "letterhead_html": "",
        "footer_html": "",
    }


def _clear_other_defaults(db, except_id: int | None = None) -> None:
    if except_id:
        db.execute(
            "UPDATE corporate_report_templates SET is_default=0 WHERE id!=?",
            (except_id,),
        )
    else:
        db.execute("UPDATE corporate_report_templates SET is_default=0")


def save_template(
    db,
    form,
    username: str,
    stored_assets: dict[str, str | None],
    template_id: int | None = None,
) -> int:
    name = (form.get("template_name") or "").strip()
    if not name:
        raise ValueError("Template name is required.")
    orientation = (form.get("pdf_orientation") or "portrait").strip().lower()
    if orientation not in PDF_ORIENTATIONS:
        orientation = "portrait"
    font = (form.get("font_family") or DEFAULT_FONT).strip()
    if font not in FONT_OPTIONS:
        font = DEFAULT_FONT
    is_active = 1 if form.get("is_active") == "1" else 0
    is_default = 1 if form.get("is_default") == "1" else 0
    now = _now_ts()

    existing = get_template(db, template_id) if template_id else None
    values = {
        "template_name": name,
        "is_active": is_active,
        "is_default": is_default,
        "letterhead_html": (form.get("letterhead_html") or "").strip(),
        "footer_html": (form.get("footer_html") or "").strip(),
        "primary_color": (form.get("primary_color") or DEFAULT_PRIMARY).strip(),
        "secondary_color": (form.get("secondary_color") or DEFAULT_SECONDARY).strip(),
        "background_color": (form.get("background_color") or DEFAULT_BACKGROUND).strip(),
        "font_family": font,
        "pdf_orientation": orientation,
        "footer_address": (form.get("footer_address") or "").strip(),
        "footer_phone": (form.get("footer_phone") or "").strip(),
        "footer_email": (form.get("footer_email") or "").strip(),
        "footer_website": (form.get("footer_website") or "").strip(),
        "header_title_line1": (form.get("header_title_line1") or DEFAULT_HEADER_LINE1).strip(),
        "header_title_line2": (form.get("header_title_line2") or DEFAULT_HEADER_LINE2).strip(),
        "updated_at": now,
    }
    for field in TEMPLATE_ASSET_FIELDS:
        if stored_assets.get(field):
            values[field] = stored_assets[field]
        elif existing:
            values[field] = existing.get(field)

    if is_default:
        _clear_other_defaults(db, template_id)

    if template_id and existing:
        db.execute(
            """
            UPDATE corporate_report_templates SET
                template_name=?, is_active=?, is_default=?,
                company_logo_path=?, watermark_logo_path=?, company_seal_path=?,
                signatory_image_path=?, letterhead_html=?, footer_html=?,
                primary_color=?, secondary_color=?, background_color=?,
                font_family=?, pdf_orientation=?,
                footer_address=?, footer_phone=?, footer_email=?, footer_website=?,
                header_title_line1=?, header_title_line2=?, updated_at=?
            WHERE id=?
            """,
            (
                values["template_name"],
                values["is_active"],
                values["is_default"],
                values.get("company_logo_path"),
                values.get("watermark_logo_path"),
                values.get("company_seal_path"),
                values.get("signatory_image_path"),
                values["letterhead_html"],
                values["footer_html"],
                values["primary_color"],
                values["secondary_color"],
                values["background_color"],
                values["font_family"],
                values["pdf_orientation"],
                values["footer_address"],
                values["footer_phone"],
                values["footer_email"],
                values["footer_website"],
                values["header_title_line1"],
                values["header_title_line2"],
                values["updated_at"],
                template_id,
            ),
        )
        return template_id

    cur = db.execute(
        """
        INSERT INTO corporate_report_templates(
            template_name, is_active, is_default,
            company_logo_path, watermark_logo_path, company_seal_path, signatory_image_path,
            letterhead_html, footer_html,
            primary_color, secondary_color, background_color,
            font_family, pdf_orientation,
            footer_address, footer_phone, footer_email, footer_website,
            header_title_line1, header_title_line2,
            created_by, created_at, updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            values["template_name"],
            values["is_active"],
            values["is_default"],
            values.get("company_logo_path"),
            values.get("watermark_logo_path"),
            values.get("company_seal_path"),
            values.get("signatory_image_path"),
            values["letterhead_html"],
            values["footer_html"],
            values["primary_color"],
            values["secondary_color"],
            values["background_color"],
            values["font_family"],
            values["pdf_orientation"],
            values["footer_address"],
            values["footer_phone"],
            values["footer_email"],
            values["footer_website"],
            values["header_title_line1"],
            values["header_title_line2"],
            username,
            now,
            now,
        ),
    )
    new_id = int(cur.lastrowid)
    if is_default:
        _clear_other_defaults(db, new_id)
    return new_id


def delete_template(db, template_id: int) -> None:
    if not template_id:
        raise ValueError("Invalid template.")
    row = get_template(db, template_id)
    if not row:
        raise ValueError("Template not found.")
    if row.get("is_default"):
        raise ValueError("Cannot delete the default template. Set another template as default first.")
    db.execute("DELETE FROM corporate_report_templates WHERE id=?", (template_id,))


def set_default_template(db, template_id: int) -> None:
    if not template_id:
        raise ValueError("Invalid template.")
    _clear_other_defaults(db)
    db.execute(
        "UPDATE corporate_report_templates SET is_default=1, is_active=1 WHERE id=?",
        (template_id,),
    )


def _first_active_company(db) -> dict[str, Any] | None:
    if not _table_exists(db, "companies"):
        return None
    row = db.execute(
        "SELECT * FROM companies WHERE status='Active' ORDER BY id LIMIT 1"
    ).fetchone()
    return dict(row) if row else None


def _company_address(company: dict[str, Any] | None) -> str:
    if not company:
        return ""
    parts = [
        company.get("address_line1") or "",
        company.get("address_line2") or "",
        company.get("city") or "",
        company.get("state_region") or "",
        company.get("postal_code") or "",
    ]
    return ", ".join(p for p in parts if p)


def build_print_context(
    db,
    *,
    template_id: int | None = None,
    report_slug: str = "",
    document_type: str = "",
    document_number: str = "",
    project_name: str = "",
    project_id: str = "",
    prepared_by: str = "",
    report_date: str | None = None,
    verification_token: str | None = None,
    back_url: str = "",
    export_url: str = "",
    email_subject: str = "",
    page_orientation: str | None = None,
) -> dict[str, Any]:
    """Merge active corporate template with company master and report metadata."""
    template = get_active_template(db, template_id)
    company = _first_active_company(db)
    token = verification_token or hashlib.sha256(
        f"{report_slug}:{document_number}:{report_date or _today()}".encode()
    ).hexdigest()[:16]
    doc_hash = hashlib.sha256(
        f"{report_slug}:{document_number}:{token}".encode()
    ).hexdigest()[:12]

    footer_address = template.get("footer_address") or _company_address(company)
    footer_phone = template.get("footer_phone") or (company.get("phone") if company else "")
    footer_email = template.get("footer_email") or (company.get("email") if company else "")
    footer_website = template.get("footer_website") or (company.get("website") if company else "")

    orientation = page_orientation or template.get("pdf_orientation") or "portrait"

    return {
        "template": template,
        "report_slug": report_slug,
        "document_type": document_type,
        "document_number": document_number,
        "project_name": project_name,
        "project_id": project_id,
        "prepared_by": prepared_by,
        "report_date": report_date or _today(),
        "generated_at": _now_ts(),
        "primary_color": template.get("primary_color") or DEFAULT_PRIMARY,
        "secondary_color": template.get("secondary_color") or DEFAULT_SECONDARY,
        "background_color": template.get("background_color") or DEFAULT_BACKGROUND,
        "font_family": template.get("font_family") or DEFAULT_FONT,
        "header_title_line1": template.get("header_title_line1") or DEFAULT_HEADER_LINE1,
        "header_title_line2": template.get("header_title_line2") or DEFAULT_HEADER_LINE2,
        "footer_address": footer_address,
        "footer_phone": footer_phone,
        "footer_email": footer_email,
        "footer_website": footer_website,
        "letterhead_html": template.get("letterhead_html") or "",
        "footer_html": template.get("footer_html") or "",
        "company_logo_path": template.get("company_logo_path") or DEFAULT_COMPANY_LOGO,
        "watermark_logo_path": template.get("watermark_logo_path"),
        "company_seal_path": template.get("company_seal_path"),
        "signatory_image_path": template.get("signatory_image_path"),
        "page_orientation": orientation,
        "verification_token": token,
        "verification_code": doc_hash.upper(),
        "back_url": back_url,
        "export_url": export_url,
        "email_subject": email_subject or f"MAXEK — {document_type}",
        "company": company,
    }
