"""Company Master — country-based registration, branches, directors, documents (Phase A)."""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import date, datetime
from io import BytesIO
from typing import Any

COMPANY_COUNTRIES = (
    "India",
    "Saudi Arabia",
    "UAE",
    "Qatar",
    "Oman",
    "Bahrain",
    "Kuwait",
    "Other",
)
GCC_CONFIGURABLE_COUNTRIES = ("Qatar", "Oman", "Bahrain", "Kuwait", "Other")
COMPANY_STATUSES = ("Active", "Inactive")
COMPANY_TYPES = (
    "Private Limited",
    "Public Limited",
    "LLP",
    "Partnership",
    "Proprietorship",
    "Government",
    "Other",
)
COMPANY_CURRENCIES = ("INR", "USD", "AED", "SAR", "QAR", "OMR", "BHD", "KWD", "EUR", "GBP")
FINANCIAL_YEARS = ("April-March", "January-December")
COMPANY_LANGUAGES = ("en", "hi", "ar")
COMPANY_TIMEZONES = (
    "Asia/Kolkata",
    "Asia/Dubai",
    "Asia/Riyadh",
    "Asia/Qatar",
    "Asia/Muscat",
    "Asia/Bahrain",
    "Asia/Kuwait",
    "UTC",
)
APPROVAL_STATUSES = ("Draft", "Pending", "Approved", "Rejected")
COMPANY_MASTER_SORT_COLUMNS = (
    "company_code",
    "legal_name",
    "company_name",
    "country",
    "status",
    "created_at",
)
COMPANY_EXPORT_COLUMNS = (
    "company_code",
    "company_name",
    "legal_name",
    "company_type",
    "gst_number",
    "pan_number",
    "tan_number",
    "cin_number",
    "country",
    "state_region",
    "district",
    "city",
    "postal_code",
    "phone",
    "email",
    "website",
    "currency",
    "financial_year",
    "timezone",
    "language",
    "status",
    "approval_status",
)
DIRECTOR_TYPES = ("Director", "Partner", "Proprietor", "Shareholder", "Authorized Signatory")
COMPANY_DOC_TYPES = (
    "Trade License",
    "Commercial Registration",
    "VAT Certificate",
    "GST Certificate",
    "PAN Card",
    "TAN Certificate",
    "MSME Certificate",
    "ZATCA Certificate",
    "Emirates ID Copy",
    "MOA/AOA",
    "Bank Guarantee",
    "Insurance",
    "Other",
)
EXPIRY_ALERT_DAYS = (90, 60, 30, 7)
MAX_COMPANY_UPLOAD_BYTES = 10 * 1024 * 1024
COMPANY_ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".xls", ".xlsx"}
COMPANY_LOGO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".svg"}

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
PHONE_RE = re.compile(r"^[\d\s+\-().]{7,20}$")
WEBSITE_RE = re.compile(
    r"^(https?://)?([a-zA-Z0-9\-]+\.)+[a-zA-Z]{2,}(/.*)?$",
    re.I,
)
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$", re.I)
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$", re.I)

INDIA_FIELD_DEFS = [
    ("pan", "PAN", "text", 1),
    ("tan", "TAN", "text", 0),
    ("cin", "CIN / Company Registration", "text", 0),
    ("msme_reg_no", "MSME Registration No.", "text", 0),
    ("msme_category", "MSME Category", "select", 0),
    ("iec_code", "IEC Code (Import/Export)", "text", 0),
    ("pf_establishment_id", "PF Establishment ID", "text", 0),
    ("esi_establishment_id", "ESI Establishment ID", "text", 0),
]

SAUDI_FIELD_DEFS = [
    ("cr_number", "Commercial Registration (CR)", "text", 1),
    ("cr_issue_date", "CR Issue Date", "date", 0),
    ("cr_expiry_date", "CR Expiry Date", "date", 0),
    ("vat_number", "VAT Number", "text", 1),
    ("zatca_fatoora_id", "ZATCA Fatoora ID", "text", 0),
    ("gosi_number", "GOSI Number", "text", 0),
    ("municipality_license", "Municipality License", "text", 0),
]

UAE_FIELD_DEFS = [
    ("trade_license_no", "Trade License No.", "text", 1),
    ("trade_license_authority", "License Authority", "text", 0),
    ("trade_license_expiry", "Trade License Expiry", "date", 0),
    ("vat_trn", "VAT TRN", "text", 1),
    ("chamber_membership_no", "Chamber Membership No.", "text", 0),
]

INDIA_DIRECTOR_FIELDS = [
    ("pan", "PAN", "text", 0),
    ("aadhaar", "Aadhaar", "text", 0),
]
SAUDI_DIRECTOR_FIELDS = [
    ("iqama", "Iqama No.", "text", 0),
    ("passport", "Passport No.", "text", 0),
]
UAE_DIRECTOR_FIELDS = [
    ("emirates_id", "Emirates ID", "text", 0),
    ("passport", "Passport No.", "text", 0),
]

DEFAULT_GCC_FIELD_CONFIG = [
    ("commercial_reg_no", "Commercial Registration No.", "text", 1),
    ("tax_registration_no", "Tax / VAT Registration", "text", 0),
    ("license_authority", "License Authority", "text", 0),
    ("license_expiry", "License Expiry", "date", 0),
]


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


def _parse_date(value: str | None) -> date | None:
    if not value or not str(value).strip():
        return None
    try:
        return datetime.strptime(str(value).strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _days_until(expiry_str: str | None, today: date | None = None) -> int | None:
    exp = _parse_date(expiry_str)
    if not exp:
        return None
    ref = today or date.today()
    return (exp - ref).days


def _expiry_bucket(days_left: int | None) -> str | None:
    if days_left is None:
        return None
    if days_left < 0:
        return "overdue"
    for threshold in EXPIRY_ALERT_DAYS:
        if days_left <= threshold:
            return str(threshold)
    return None


def _next_company_code(db) -> str:
    year = datetime.now().strftime("%Y")
    base = f"CO-{year}-"
    if not _table_exists(db, "companies"):
        return f"{base}0001"
    row = db.execute(
        "SELECT company_code FROM companies WHERE company_code LIKE ? ORDER BY id DESC LIMIT 1",
        (f"{base}%",),
    ).fetchone()
    seq = 1
    if row and row[0]:
        m = re.search(r"-(\d+)$", str(row[0]))
        if m:
            seq = int(m.group(1)) + 1
    return f"{base}{seq:04d}"


def _json_load(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _json_dump(data: dict[str, Any] | None) -> str:
    return json.dumps(data or {}, ensure_ascii=False)


def country_field_defs(country: str, db=None) -> list[dict[str, Any]]:
    country = (country or "").strip()
    if country == "India":
        return [_field_def_to_dict(f) for f in INDIA_FIELD_DEFS]
    if country == "Saudi Arabia":
        return [_field_def_to_dict(f) for f in SAUDI_FIELD_DEFS]
    if country == "UAE":
        return [_field_def_to_dict(f) for f in UAE_FIELD_DEFS]
    if country in GCC_CONFIGURABLE_COUNTRIES and db is not None:
        return list_country_field_config(db, country)
    return [_field_def_to_dict(f) for f in DEFAULT_GCC_FIELD_CONFIG]


def director_field_defs(country: str) -> list[dict[str, Any]]:
    country = (country or "").strip()
    if country == "India":
        return [_field_def_to_dict(f) for f in INDIA_DIRECTOR_FIELDS]
    if country == "Saudi Arabia":
        return [_field_def_to_dict(f) for f in SAUDI_DIRECTOR_FIELDS]
    if country == "UAE":
        return [_field_def_to_dict(f) for f in UAE_DIRECTOR_FIELDS]
    return [
        {"field_key": "national_id", "field_label": "National ID", "field_type": "text", "is_required": 0},
        {"field_key": "passport", "field_label": "Passport No.", "field_type": "text", "is_required": 0},
    ]


def _field_def_to_dict(defn: tuple) -> dict[str, Any]:
    key, label, ftype, required = defn
    opts = []
    if key == "msme_category":
        opts = ["Micro", "Small", "Medium"]
    return {
        "field_key": key,
        "field_label": label,
        "field_type": ftype,
        "is_required": required,
        "options": opts,
    }


def _parse_country_fields(form, country: str, db=None) -> dict[str, str]:
    data: dict[str, str] = {}
    for field in country_field_defs(country, db):
        key = field["field_key"]
        val = (form.get(f"cf_{key}") or "").strip()
        if val:
            data[key] = val
    return data


def _parse_director_id_fields(form, country: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for field in director_field_defs(country):
        key = field["field_key"]
        val = (form.get(f"dp_{key}") or "").strip()
        if val:
            data[key] = val
    return data


def ensure_company_master_schema(db) -> None:
    """Idempotent company master schema (Phase A)."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS companies(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_code TEXT UNIQUE NOT NULL,
            legal_name TEXT NOT NULL,
            trade_name TEXT,
            country TEXT NOT NULL,
            status TEXT DEFAULT 'Active',
            address_line1 TEXT,
            address_line2 TEXT,
            city TEXT,
            state_region TEXT,
            postal_code TEXT,
            phone TEXT,
            email TEXT,
            website TEXT,
            country_fields_json TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT
        )
    """)
    for col, ctype in (
        ("company_code", "TEXT"), ("legal_name", "TEXT"), ("trade_name", "TEXT"),
        ("company_name", "TEXT"), ("company_type", "TEXT"),
        ("country", "TEXT"), ("status", "TEXT DEFAULT 'Active'"),
        ("address_line1", "TEXT"), ("address_line2", "TEXT"), ("city", "TEXT"),
        ("state_region", "TEXT"), ("district", "TEXT"), ("postal_code", "TEXT"),
        ("phone", "TEXT"), ("email", "TEXT"), ("website", "TEXT"),
        ("gst_number", "TEXT"), ("pan_number", "TEXT"), ("tan_number", "TEXT"),
        ("cin_number", "TEXT"), ("currency", "TEXT DEFAULT 'INR'"),
        ("financial_year", "TEXT DEFAULT 'April-March'"),
        ("timezone", "TEXT DEFAULT 'Asia/Kolkata'"),
        ("language", "TEXT DEFAULT 'en'"),
        ("company_logo", "TEXT"), ("approval_status", "TEXT DEFAULT 'Approved'"),
        ("country_fields_json", "TEXT"),
        ("created_by", "TEXT"), ("created_at", "TEXT"),
        ("modified_by", "TEXT"), ("modified_at", "TEXT"),
        ("approved_by", "TEXT"), ("approved_at", "TEXT"),
        ("is_deleted", "INTEGER DEFAULT 0"),
        ("deleted_by", "TEXT"), ("deleted_at", "TEXT"),
        ("bank_name", "TEXT"), ("bank_branch_name", "TEXT"), ("bank_branch_address", "TEXT"),
        ("bank_account_name", "TEXT"), ("bank_account_number", "TEXT"),
        ("bank_ifsc", "TEXT"), ("bank_swift", "TEXT"), ("bank_micr", "TEXT"), ("bank_upi", "TEXT"),
    ):
        _ensure_column(db, "companies", col, ctype)

    try:
        from audit_trail_service import ensure_audit_schema

        ensure_audit_schema(db)
    except Exception:
        pass

    db.execute("""
        CREATE TABLE IF NOT EXISTS company_branches(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            branch_code TEXT,
            branch_name TEXT NOT NULL,
            country TEXT NOT NULL,
            address_line1 TEXT,
            address_line2 TEXT,
            city TEXT,
            state_region TEXT,
            postal_code TEXT,
            phone TEXT,
            email TEXT,
            tax_registration TEXT,
            country_fields_json TEXT,
            is_head_office INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Active',
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(company_id) REFERENCES companies(id)
        )
    """)
    for col, ctype in (
        ("company_id", "INTEGER"), ("branch_code", "TEXT"), ("branch_name", "TEXT"),
        ("country", "TEXT"), ("address_line1", "TEXT"), ("address_line2", "TEXT"),
        ("city", "TEXT"), ("state_region", "TEXT"), ("postal_code", "TEXT"),
        ("phone", "TEXT"), ("email", "TEXT"), ("tax_registration", "TEXT"),
        ("country_fields_json", "TEXT"), ("is_head_office", "INTEGER DEFAULT 0"),
        ("status", "TEXT DEFAULT 'Active'"), ("created_by", "TEXT"),
        ("created_at", "TEXT"), ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "company_branches", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS company_gst_registrations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            branch_id INTEGER,
            state_code TEXT,
            state_name TEXT,
            gstin TEXT NOT NULL,
            registration_date TEXT,
            status TEXT DEFAULT 'Active',
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(company_id) REFERENCES companies(id),
            FOREIGN KEY(branch_id) REFERENCES company_branches(id)
        )
    """)
    for col, ctype in (
        ("company_id", "INTEGER"), ("branch_id", "INTEGER"), ("state_code", "TEXT"),
        ("state_name", "TEXT"), ("gstin", "TEXT"), ("registration_date", "TEXT"),
        ("status", "TEXT DEFAULT 'Active'"), ("created_at", "TEXT"), ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "company_gst_registrations", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS company_directors_partners(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            person_type TEXT DEFAULT 'Director',
            full_name TEXT NOT NULL,
            designation TEXT,
            nationality TEXT,
            country TEXT,
            id_fields_json TEXT,
            address TEXT,
            phone TEXT,
            email TEXT,
            share_percentage REAL,
            is_active INTEGER DEFAULT 1,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(company_id) REFERENCES companies(id)
        )
    """)
    for col, ctype in (
        ("company_id", "INTEGER"), ("person_type", "TEXT"), ("full_name", "TEXT"),
        ("designation", "TEXT"), ("nationality", "TEXT"), ("country", "TEXT"),
        ("id_fields_json", "TEXT"), ("address", "TEXT"), ("phone", "TEXT"),
        ("email", "TEXT"), ("share_percentage", "REAL"), ("is_active", "INTEGER DEFAULT 1"),
        ("created_by", "TEXT"), ("created_at", "TEXT"), ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "company_directors_partners", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS company_documents(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            branch_id INTEGER,
            director_id INTEGER,
            doc_type TEXT,
            doc_number TEXT,
            issue_date TEXT,
            expiry_date TEXT,
            alert_flag INTEGER DEFAULT 0,
            attachment TEXT,
            remarks TEXT,
            is_active INTEGER DEFAULT 1,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(company_id) REFERENCES companies(id),
            FOREIGN KEY(branch_id) REFERENCES company_branches(id),
            FOREIGN KEY(director_id) REFERENCES company_directors_partners(id)
        )
    """)
    for col, ctype in (
        ("company_id", "INTEGER"), ("branch_id", "INTEGER"), ("director_id", "INTEGER"),
        ("doc_type", "TEXT"), ("doc_number", "TEXT"), ("issue_date", "TEXT"),
        ("expiry_date", "TEXT"), ("alert_flag", "INTEGER DEFAULT 0"), ("attachment", "TEXT"),
        ("remarks", "TEXT"), ("is_active", "INTEGER DEFAULT 1"), ("created_by", "TEXT"),
        ("created_at", "TEXT"), ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "company_documents", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS company_country_field_config(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country TEXT NOT NULL,
            field_key TEXT NOT NULL,
            field_label TEXT NOT NULL,
            field_type TEXT DEFAULT 'text',
            is_required INTEGER DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            options_json TEXT,
            UNIQUE(country, field_key)
        )
    """)
    for col, ctype in (
        ("country", "TEXT"), ("field_key", "TEXT"), ("field_label", "TEXT"),
        ("field_type", "TEXT DEFAULT 'text'"), ("is_required", "INTEGER DEFAULT 0"),
        ("sort_order", "INTEGER DEFAULT 0"), ("options_json", "TEXT"),
    ):
        _ensure_column(db, "company_country_field_config", col, ctype)

    seed_country_field_config(db)


def seed_country_field_config(db) -> None:
    """Default configurable fields for GCC + Other countries."""
    for country in GCC_CONFIGURABLE_COUNTRIES:
        for idx, (key, label, ftype, required) in enumerate(DEFAULT_GCC_FIELD_CONFIG):
            existing = db.execute(
                "SELECT id FROM company_country_field_config WHERE country=? AND field_key=?",
                (country, key),
            ).fetchone()
            if existing:
                continue
            db.execute(
                "INSERT INTO company_country_field_config("
                "country, field_key, field_label, field_type, is_required, sort_order, options_json"
                ") VALUES(?,?,?,?,?,?,?)",
                (country, key, label, ftype, required, idx, "[]"),
            )


def list_country_field_config(db, country: str) -> list[dict[str, Any]]:
    if not _table_exists(db, "company_country_field_config"):
        return []
    rows = db.execute(
        "SELECT * FROM company_country_field_config WHERE country=? ORDER BY sort_order, field_label",
        (country,),
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        try:
            item["options"] = json.loads(item.get("options_json") or "[]")
        except json.JSONDecodeError:
            item["options"] = []
        result.append(item)
    return result


def list_companies(
    db,
    search: str = "",
    country: str = "",
    status: str = "",
    include_deleted: bool = False,
    page: int = 1,
    per_page: int = 25,
    sort_by: str = "legal_name",
    sort_dir: str = "asc",
) -> dict[str, Any]:
    """Paginated company list with search, filter, and sort."""
    if not _table_exists(db, "companies"):
        return {"items": [], "total": 0, "page": 1, "per_page": per_page, "pages": 0}
    sql = "SELECT * FROM companies WHERE 1=1"
    count_sql = "SELECT COUNT(*) FROM companies WHERE 1=1"
    params: list[Any] = []
    if not include_deleted:
        sql += " AND COALESCE(is_deleted, 0)=0"
        count_sql += " AND COALESCE(is_deleted, 0)=0"
    if search:
        clause = (
            " AND (legal_name LIKE ? OR company_name LIKE ? OR trade_name LIKE ? "
            "OR company_code LIKE ? OR gst_number LIKE ? OR pan_number LIKE ?)"
        )
        sql += clause
        count_sql += clause
        like = f"%{search}%"
        params.extend([like, like, like, like, like, like])
    if country:
        sql += " AND country=?"
        count_sql += " AND country=?"
        params.append(country)
    if status:
        sql += " AND status=?"
        count_sql += " AND status=?"
        params.append(status)
    sort_col = sort_by if sort_by in COMPANY_MASTER_SORT_COLUMNS else "legal_name"
    direction = "DESC" if str(sort_dir).lower() == "desc" else "ASC"
    sql += f" ORDER BY {sort_col} {direction}, id DESC"
    per_page = max(1, min(int(per_page or 25), 200))
    page = max(1, int(page or 1))
    offset = (page - 1) * per_page
    sql += " LIMIT ? OFFSET ?"
    total = int(db.execute(count_sql, params).fetchone()[0])
    rows = db.execute(sql, [*params, per_page, offset]).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["country_fields"] = _json_load(item.get("country_fields_json"))
        if not item.get("company_name"):
            item["company_name"] = item.get("trade_name") or item.get("legal_name") or ""
        result.append(item)
    pages = (total + per_page - 1) // per_page if total else 0
    return {
        "items": result,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }


def get_company(db, company_id: int, *, include_deleted: bool = False) -> dict[str, Any] | None:
    if not company_id or not _table_exists(db, "companies"):
        return None
    sql = "SELECT * FROM companies WHERE id=?"
    if not include_deleted:
        sql += " AND COALESCE(is_deleted, 0)=0"
    row = db.execute(sql, (company_id,)).fetchone()
    if not row:
        return None
    item = dict(row)
    item["country_fields"] = _json_load(item.get("country_fields_json"))
    if not item.get("company_name"):
        item["company_name"] = item.get("trade_name") or item.get("legal_name") or ""
    return item


def save_company(db, form, username: str, company_id: int | None = None) -> int:
    legal_name = (form.get("legal_name") or "").strip()
    if not legal_name:
        raise ValueError("Legal name is required.")
    country = (form.get("country") or "India").strip()
    if country not in COMPANY_COUNTRIES:
        raise ValueError("Select a valid country.")
    company_name = (form.get("company_name") or form.get("trade_name") or "").strip()
    if not company_name:
        raise ValueError("Company name is required.")
    trade_name = company_name
    company_type = (form.get("company_type") or "").strip()
    if company_type and company_type not in COMPANY_TYPES:
        raise ValueError("Select a valid company type.")
    status = (form.get("status") or "Active").strip()
    if status not in COMPANY_STATUSES:
        raise ValueError("Select a valid status.")
    email = (form.get("email") or "").strip()
    phone = (form.get("phone") or "").strip()
    website = (form.get("website") or "").strip()
    validate_company_contact(email=email, phone=phone, website=website)
    country_fields = _parse_country_fields(form, country, db)
    gst_number = (form.get("gst_number") or country_fields.get("gst") or "").strip().upper()
    pan_number = (form.get("pan_number") or country_fields.get("pan") or "").strip().upper()
    tan_number = (form.get("tan_number") or country_fields.get("tan") or "").strip().upper()
    cin_number = (form.get("cin_number") or country_fields.get("cin") or "").strip().upper()
    if country == "India":
        if pan_number:
            country_fields["pan"] = pan_number
        if tan_number:
            country_fields["tan"] = tan_number
        if cin_number:
            country_fields["cin"] = cin_number
    if gst_number:
        validate_gst_number(gst_number)
    if pan_number:
        validate_pan_number(pan_number)
    currency = (form.get("currency") or "INR").strip()
    if currency not in COMPANY_CURRENCIES:
        raise ValueError("Select a valid currency.")
    financial_year = (form.get("financial_year") or "April-March").strip()
    if financial_year not in FINANCIAL_YEARS:
        raise ValueError("Select a valid financial year.")
    timezone = (form.get("timezone") or "Asia/Kolkata").strip()
    if timezone not in COMPANY_TIMEZONES:
        raise ValueError("Select a valid timezone.")
    language = (form.get("language") or "en").strip()
    if language not in COMPANY_LANGUAGES:
        raise ValueError("Select a valid language.")
    company_logo = (form.get("company_logo") or "").strip()
    now = _now_ts()
    bank_values = (
        (form.get("bank_name") or "").strip(),
        (form.get("bank_branch_name") or "").strip(),
        (form.get("bank_branch_address") or "").strip(),
        (form.get("bank_account_name") or "").strip(),
        (form.get("bank_account_number") or "").strip(),
        (form.get("bank_ifsc") or "").strip().upper(),
        (form.get("bank_swift") or "").strip().upper(),
        (form.get("bank_micr") or "").strip(),
        (form.get("bank_upi") or "").strip(),
    )
    core_values = (
        legal_name,
        trade_name,
        company_name,
        company_type,
        country,
        status,
        (form.get("address_line1") or "").strip(),
        (form.get("address_line2") or "").strip(),
        (form.get("city") or "").strip(),
        (form.get("state_region") or "").strip(),
        (form.get("district") or "").strip(),
        (form.get("postal_code") or "").strip(),
        phone,
        email,
        website,
        gst_number,
        pan_number,
        tan_number,
        cin_number,
        currency,
        financial_year,
        timezone,
        language,
        company_logo,
        _json_dump(country_fields),
        *bank_values,
    )
    if company_id:
        existing = get_company(db, company_id, include_deleted=True)
        if not existing:
            raise ValueError("Company not found.")
        validate_company_uniqueness(
            db,
            company_code=existing.get("company_code"),
            gst_number=gst_number,
            legal_name=legal_name,
            company_id=company_id,
        )
        db.execute(
            "UPDATE companies SET legal_name=?, trade_name=?, company_name=?, company_type=?, "
            "country=?, status=?, address_line1=?, address_line2=?, city=?, state_region=?, "
            "district=?, postal_code=?, phone=?, email=?, website=?, gst_number=?, pan_number=?, "
            "tan_number=?, cin_number=?, currency=?, financial_year=?, timezone=?, language=?, "
            "company_logo=?, country_fields_json=?, "
            "bank_name=?, bank_branch_name=?, bank_branch_address=?, bank_account_name=?, "
            "bank_account_number=?, bank_ifsc=?, bank_swift=?, bank_micr=?, bank_upi=?, "
            "modified_by=?, modified_at=? WHERE id=?",
            (*core_values, username, now, company_id),
        )
        log_company_field_changes(db, existing, get_company(db, company_id, include_deleted=True), username)
        return company_id
    manual_code = (form.get("company_code") or "").strip().upper()
    code = manual_code or _next_company_code(db)
    validate_company_uniqueness(
        db,
        company_code=code,
        gst_number=gst_number,
        legal_name=legal_name,
    )
    approval_status = (form.get("approval_status") or "Draft").strip()
    if approval_status not in APPROVAL_STATUSES:
        approval_status = "Draft"
    cur = db.execute(
        "INSERT INTO companies(company_code, legal_name, trade_name, company_name, company_type, "
        "country, status, address_line1, address_line2, city, state_region, district, postal_code, "
        "phone, email, website, gst_number, pan_number, tan_number, cin_number, currency, "
        "financial_year, timezone, language, company_logo, country_fields_json, "
        "bank_name, bank_branch_name, bank_branch_address, bank_account_name, bank_account_number, "
        "bank_ifsc, bank_swift, bank_micr, bank_upi, approval_status, created_by, created_at, "
        "modified_by, modified_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (code, *core_values, approval_status, username, now, username, now),
    )
    new_id = int(cur.lastrowid)
    log_company_audit(db, new_id, "create", username, remarks=f"Created company {code}")
    return new_id


def delete_company(db, company_id: int, username: str = "") -> None:
    """Soft-delete a company record."""
    soft_delete_company(db, company_id, username)


def soft_delete_company(db, company_id: int, username: str) -> None:
    if not company_id:
        raise ValueError("Invalid company.")
    row = get_company(db, company_id, include_deleted=True)
    if not row:
        raise ValueError("Company not found.")
    if row.get("is_deleted"):
        return
    now = _now_ts()
    db.execute(
        "UPDATE companies SET is_deleted=1, deleted_by=?, deleted_at=?, modified_by=?, modified_at=? "
        "WHERE id=?",
        (username, now, username, now, company_id),
    )
    log_company_audit(
        db,
        company_id,
        "soft_delete",
        username,
        remarks=f"Soft-deleted company {row.get('company_code')}",
    )


def hard_delete_company(db, company_id: int) -> None:
    """Permanently remove company and child records (Super Admin only)."""
    if not company_id:
        raise ValueError("Invalid company.")
    for table in (
        "company_documents",
        "company_gst_registrations",
        "company_directors_partners",
        "company_branches",
    ):
        if _table_exists(db, table):
            db.execute(f"DELETE FROM {table} WHERE company_id=?", (company_id,))
    db.execute("DELETE FROM companies WHERE id=?", (company_id,))


def list_branches(db, company_id: int) -> list[dict[str, Any]]:
    if not _table_exists(db, "company_branches"):
        return []
    rows = db.execute(
        "SELECT * FROM company_branches WHERE company_id=? ORDER BY is_head_office DESC, branch_name",
        (company_id,),
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["country_fields"] = _json_load(item.get("country_fields_json"))
        result.append(item)
    return result


def get_branch(db, branch_id: int) -> dict[str, Any] | None:
    row = db.execute("SELECT * FROM company_branches WHERE id=?", (branch_id,)).fetchone()
    if not row:
        return None
    item = dict(row)
    item["country_fields"] = _json_load(item.get("country_fields_json"))
    return item


def save_branch(
    db,
    form,
    username: str,
    branch_id: int | None = None,
    *,
    customer_id: int | None = None,
) -> int:
    from branch_master_service import save_branch_master

    return save_branch_master(db, form, username, branch_id, customer_id=customer_id)


def delete_branch(db, branch_id: int, username: str = "") -> None:
    from branch_master_service import soft_delete_branch_master

    soft_delete_branch_master(db, branch_id, username or "system")


def list_gst_registrations(db, company_id: int) -> list[dict[str, Any]]:
    if not _table_exists(db, "company_gst_registrations"):
        return []
    rows = db.execute(
        "SELECT * FROM company_gst_registrations WHERE company_id=? ORDER BY state_name, gstin",
        (company_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def save_gst_registration(db, form, company_id: int, record_id: int | None = None) -> int:
    gstin = (form.get("gstin") or "").strip().upper()
    if not gstin:
        raise ValueError("GSTIN is required.")
    now = _now_ts()
    branch_id = form.get("gst_branch_id") or None
    branch_id = int(branch_id) if branch_id else None
    values = (
        company_id,
        branch_id,
        (form.get("state_code") or "").strip(),
        (form.get("state_name") or "").strip(),
        gstin,
        (form.get("registration_date") or "").strip(),
        (form.get("gst_status") or "Active").strip(),
        now,
    )
    if record_id:
        db.execute(
            "UPDATE company_gst_registrations SET company_id=?, branch_id=?, state_code=?, "
            "state_name=?, gstin=?, registration_date=?, status=?, modified_at=? WHERE id=?",
            (*values, record_id),
        )
        return record_id
    cur = db.execute(
        "INSERT INTO company_gst_registrations(company_id, branch_id, state_code, state_name, "
        "gstin, registration_date, status, created_at, modified_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (*values, now),
    )
    return int(cur.lastrowid)


def delete_gst_registration(db, record_id: int) -> None:
    db.execute("DELETE FROM company_gst_registrations WHERE id=?", (record_id,))


def list_directors(db, company_id: int) -> list[dict[str, Any]]:
    if not _table_exists(db, "company_directors_partners"):
        return []
    rows = db.execute(
        "SELECT * FROM company_directors_partners WHERE company_id=? ORDER BY full_name",
        (company_id,),
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["id_fields"] = _json_load(item.get("id_fields_json"))
        result.append(item)
    return result


def get_director(db, director_id: int) -> dict[str, Any] | None:
    row = db.execute(
        "SELECT * FROM company_directors_partners WHERE id=?", (director_id,)
    ).fetchone()
    if not row:
        return None
    item = dict(row)
    item["id_fields"] = _json_load(item.get("id_fields_json"))
    return item


def save_director(db, form, username: str, director_id: int | None = None) -> int:
    company_id = int(form.get("company_id") or 0)
    if not company_id:
        raise ValueError("Company is required.")
    full_name = (form.get("director_full_name") or form.get("full_name") or "").strip()
    if not full_name:
        raise ValueError("Director / partner name is required.")
    country = (form.get("director_country") or form.get("country") or "India").strip()
    id_fields = _parse_director_id_fields(form, country)
    share_raw = (form.get("share_percentage") or "").strip()
    share_pct = float(share_raw) if share_raw else None
    now = _now_ts()
    values = (
        company_id,
        (form.get("person_type") or "Director").strip(),
        full_name,
        (form.get("designation") or "").strip(),
        (form.get("nationality") or "").strip(),
        country,
        _json_dump(id_fields),
        (form.get("director_address") or form.get("address") or "").strip(),
        (form.get("director_phone") or form.get("phone") or "").strip(),
        (form.get("director_email") or form.get("email") or "").strip(),
        share_pct,
        1 if form.get("director_active") == "on" else 0,
        now,
    )
    if director_id:
        db.execute(
            "UPDATE company_directors_partners SET company_id=?, person_type=?, full_name=?, "
            "designation=?, nationality=?, country=?, id_fields_json=?, address=?, phone=?, "
            "email=?, share_percentage=?, is_active=?, modified_at=? WHERE id=?",
            (*values, director_id),
        )
        return director_id
    cur = db.execute(
        "INSERT INTO company_directors_partners(company_id, person_type, full_name, designation, "
        "nationality, country, id_fields_json, address, phone, email, share_percentage, is_active, "
        "created_by, created_at, modified_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (*values, username, now),
    )
    return int(cur.lastrowid)


def delete_director(db, director_id: int) -> None:
    if _table_exists(db, "company_documents"):
        db.execute(
            "UPDATE company_documents SET director_id=NULL WHERE director_id=?", (director_id,)
        )
    db.execute("DELETE FROM company_directors_partners WHERE id=?", (director_id,))


def list_company_documents(db, company_id: int) -> list[dict[str, Any]]:
    if not _table_exists(db, "company_documents"):
        return []
    today = date.today()
    rows = db.execute(
        "SELECT d.*, b.branch_name FROM company_documents d "
        "LEFT JOIN company_branches b ON d.branch_id = b.id "
        "WHERE d.company_id=? AND d.is_active=1 ORDER BY d.expiry_date ASC, d.id DESC",
        (company_id,),
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        days = _days_until(item.get("expiry_date"), today)
        item["days_left"] = days
        item["alert_bucket"] = _expiry_bucket(days)
        result.append(item)
    return result


def get_company_document(db, doc_id: int) -> dict[str, Any] | None:
    row = db.execute("SELECT * FROM company_documents WHERE id=?", (doc_id,)).fetchone()
    return dict(row) if row else None


def save_company_document(
    db,
    form,
    username: str,
    attachment: str | None,
    doc_id: int | None = None,
) -> int:
    company_id = int(form.get("company_id") or 0)
    if not company_id:
        raise ValueError("Company is required.")
    doc_type = (form.get("doc_type") or "Other").strip()
    expiry_date = (form.get("expiry_date") or "").strip()
    days = _days_until(expiry_date)
    alert_flag = 1 if _expiry_bucket(days) else 0
    branch_id = form.get("doc_branch_id") or None
    branch_id = int(branch_id) if branch_id else None
    director_id = form.get("doc_director_id") or None
    director_id = int(director_id) if director_id else None
    now = _now_ts()
    values = (
        company_id,
        branch_id,
        director_id,
        doc_type,
        (form.get("doc_number") or "").strip(),
        (form.get("issue_date") or "").strip(),
        expiry_date,
        alert_flag,
        (form.get("remarks") or "").strip(),
        now,
    )
    if doc_id:
        existing = get_company_document(db, doc_id)
        attach = attachment if attachment is not None else (existing or {}).get("attachment")
        db.execute(
            "UPDATE company_documents SET company_id=?, branch_id=?, director_id=?, doc_type=?, "
            "doc_number=?, issue_date=?, expiry_date=?, alert_flag=?, remarks=?, attachment=?, "
            "modified_at=? WHERE id=?",
            (*values, attach or "", doc_id),
        )
        return doc_id
    if not attachment:
        attachment = ""
    cur = db.execute(
        "INSERT INTO company_documents(company_id, branch_id, director_id, doc_type, doc_number, "
        "issue_date, expiry_date, alert_flag, remarks, attachment, is_active, created_by, "
        "created_at, modified_at) VALUES(?,?,?,?,?,?,?,?,?,?,1,?,?,?)",
        (*values, attachment, username, now),
    )
    return int(cur.lastrowid)


def delete_company_document(db, doc_id: int) -> None:
    db.execute("UPDATE company_documents SET is_active=0 WHERE id=?", (doc_id,))


def collect_company_expiry_alerts(db) -> dict[str, Any]:
    """Company documents with expiry buckets (90/60/30/7 + overdue)."""
    buckets: dict[str, list[dict]] = {str(d): [] for d in EXPIRY_ALERT_DAYS}
    overdue: list[dict] = []
    if not _table_exists(db, "company_documents"):
        return {
            "expiring": buckets,
            "expiring_overdue": overdue,
            "total_alerts": 0,
            "alert_days": EXPIRY_ALERT_DAYS,
        }
    today = date.today()
    rows = db.execute(
        "SELECT d.id, d.doc_type, d.doc_number, d.expiry_date, d.company_id, "
        "c.legal_name AS company_name, c.company_code "
        "FROM company_documents d "
        "JOIN companies c ON d.company_id = c.id "
        "WHERE d.is_active=1 AND COALESCE(c.is_deleted,0)=0 AND d.expiry_date IS NOT NULL AND d.expiry_date != ''"
    ).fetchall()
    for row in rows:
        item = dict(row)
        item["title"] = f"{item.get('doc_type')} — {item.get('company_name')}"
        item["source"] = "company_doc"
        days = _days_until(item.get("expiry_date"), today)
        bucket = _expiry_bucket(days)
        item["days_left"] = days
        if bucket == "overdue":
            overdue.append(item)
        elif bucket:
            buckets[bucket].append(item)
    total = len(overdue) + sum(len(buckets[str(d)]) for d in EXPIRY_ALERT_DAYS)
    return {
        "expiring": buckets,
        "expiring_overdue": overdue,
        "total_alerts": total,
        "alert_days": EXPIRY_ALERT_DAYS,
    }


def sync_company_expiry_notifications(db, notify_fn) -> int:
    """Create in-app notifications for admins when company documents are expiring."""
    alerts = collect_company_expiry_alerts(db)
    if alerts["total_alerts"] == 0:
        return 0
    admin_rows = db.execute(
        "SELECT id FROM users WHERE status='Active' AND ("
        "LOWER(COALESCE(role,'')) IN ('admin','administrator') OR "
        "LOWER(COALESCE(workflow_role,''))='administrator'"
        ")"
    ).fetchall()
    admin_ids = [row[0] for row in admin_rows]
    if not admin_ids:
        return 0
    created = 0
    all_items = list(alerts["expiring_overdue"])
    for threshold in EXPIRY_ALERT_DAYS:
        all_items.extend(alerts["expiring"].get(str(threshold), []))
    seen: set[int] = set()
    for item in all_items:
        doc_id = item.get("id")
        if not doc_id or doc_id in seen:
            continue
        seen.add(doc_id)
        days = item.get("days_left")
        if days is not None and days < 0:
            msg = (
                f"Company document expired: {item.get('doc_type')} "
                f"({item.get('company_name')}) — {item.get('expiry_date')}"
            )
        else:
            msg = (
                f"Company document expiring in {days} days: {item.get('doc_type')} "
                f"({item.get('company_name')}) — {item.get('expiry_date')}"
            )
        for uid in admin_ids:
            existing = db.execute(
                "SELECT id FROM notifications WHERE user_id=? AND record_table='company_documents' "
                "AND record_id=? AND is_read=0",
                (uid, doc_id),
            ).fetchone()
            if existing:
                continue
            notify_fn(
                db,
                uid,
                msg,
                "company_doc_expiry",
                "company_master",
                doc_id,
                "company_documents",
            )
            created += 1
    return created


# ---------------------------------------------------------------------------
# MODULE-001 — validation, permissions, audit, import/export
# ---------------------------------------------------------------------------

COMPANY_AUDIT_FIELDS = (
    "company_code",
    "company_name",
    "legal_name",
    "company_type",
    "country",
    "status",
    "address_line1",
    "address_line2",
    "city",
    "state_region",
    "district",
    "postal_code",
    "phone",
    "email",
    "website",
    "gst_number",
    "pan_number",
    "tan_number",
    "cin_number",
    "currency",
    "financial_year",
    "timezone",
    "language",
    "approval_status",
)


def validate_email(value: str) -> None:
    text = (value or "").strip()
    if text and not EMAIL_RE.match(text):
        raise ValueError("Enter a valid email address.")


def validate_phone(value: str) -> None:
    text = (value or "").strip()
    if text and not PHONE_RE.match(text):
        raise ValueError("Enter a valid phone number (7–20 digits/symbols).")


def validate_website(value: str) -> None:
    text = (value or "").strip()
    if not text:
        return
    if not WEBSITE_RE.match(text):
        raise ValueError("Enter a valid website URL (e.g. https://example.com).")


def validate_company_contact(*, email: str = "", phone: str = "", website: str = "") -> None:
    validate_email(email)
    validate_phone(phone)
    validate_website(website)


def validate_gst_number(value: str) -> None:
    text = (value or "").strip().upper()
    if text and not GSTIN_RE.match(text):
        raise ValueError("Enter a valid 15-character GST number.")


def validate_pan_number(value: str) -> None:
    text = (value or "").strip().upper()
    if text and not PAN_RE.match(text):
        raise ValueError("Enter a valid PAN (AAAAA9999A).")


def validate_company_uniqueness(
    db,
    *,
    company_code: str | None = None,
    gst_number: str | None = None,
    legal_name: str | None = None,
    company_id: int | None = None,
) -> None:
    if company_code:
        row = db.execute(
            "SELECT id FROM companies WHERE company_code=? AND COALESCE(is_deleted,0)=0",
            (company_code.strip().upper(),),
        ).fetchone()
        if row and (not company_id or int(row[0]) != int(company_id)):
            raise ValueError(f"Company code '{company_code}' already exists.")
    gst = (gst_number or "").strip().upper()
    if gst:
        row = db.execute(
            "SELECT id, company_code FROM companies WHERE UPPER(gst_number)=? AND COALESCE(is_deleted,0)=0",
            (gst,),
        ).fetchone()
        if row and (not company_id or int(row[0]) != int(company_id)):
            raise ValueError(f"GST number '{gst}' is already registered to {row[1]}.")
    name = (legal_name or "").strip()
    if name:
        row = db.execute(
            "SELECT id, company_code FROM companies WHERE legal_name=? AND COALESCE(is_deleted,0)=0",
            (name,),
        ).fetchone()
        if row and (not company_id or int(row[0]) != int(company_id)):
            raise ValueError(f"A company with legal name '{name}' already exists ({row[1]}).")


def log_company_audit(
    db,
    company_id: int,
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
            record_table="companies",
            record_id=company_id,
            action=action,
            changed_by=username,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            remarks=remarks,
        )
    except Exception:
        pass


def log_company_field_changes(
    db,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    username: str,
) -> None:
    if not before or not after:
        return
    company_id = int(after.get("id") or before.get("id") or 0)
    if not company_id:
        return
    for field in COMPANY_AUDIT_FIELDS:
        old_val = before.get(field)
        new_val = after.get(field)
        if str(old_val or "") != str(new_val or ""):
            log_company_audit(
                db,
                company_id,
                "update",
                username,
                field_name=field,
                old_value=str(old_val or ""),
                new_value=str(new_val or ""),
            )


def list_company_audit_trail(db, company_id: int, limit: int = 100) -> list[dict[str, Any]]:
    try:
        from audit_trail_service import list_audit_trail

        return list_audit_trail(db, "companies", company_id, limit=limit)
    except Exception:
        return []


def approve_company(db, company_id: int, username: str) -> None:
    row = get_company(db, company_id)
    if not row:
        raise ValueError("Company not found.")
    now = _now_ts()
    db.execute(
        "UPDATE companies SET approval_status='Approved', approved_by=?, approved_at=?, "
        "modified_by=?, modified_at=? WHERE id=?",
        (username, now, username, now, company_id),
    )
    log_company_audit(db, company_id, "approve", username, remarks="Company approved")


def reject_company(db, company_id: int, username: str, remarks: str = "") -> None:
    row = get_company(db, company_id)
    if not row:
        raise ValueError("Company not found.")
    now = _now_ts()
    db.execute(
        "UPDATE companies SET approval_status='Rejected', modified_by=?, modified_at=? WHERE id=?",
        (username, now, company_id),
    )
    log_company_audit(db, company_id, "reject", username, remarks=remarks or "Company rejected")


def user_can_company_master(
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
    try:
        from user_permission_service import (
            empty_permission_actions,
            ensure_user_tab_permissions_schema,
            normalize_permission_actions,
        )
        import json as _json

        ensure_user_tab_permissions_schema(db)
        row = db.execute(
            """
            SELECT granted, action_flags FROM user_tab_permissions
            WHERE user_id=? AND granted=1 AND endpoint='company_master'
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        if not row:
            return False
        raw_flags = row["action_flags"] if hasattr(row, "keys") else row[1]
        actions = normalize_permission_actions(
            _json.loads(raw_flags) if raw_flags else empty_permission_actions()
        )
        if action == "import":
            return bool(actions.get("import") or actions.get("create"))
        return bool(actions.get(action))
    except Exception:
        return False


def companies_for_export(db, *, include_deleted: bool = False) -> list[dict[str, Any]]:
    result = list_companies(db, include_deleted=include_deleted, per_page=10000)
    rows = []
    for item in result["items"]:
        rows.append({col: item.get(col, "") for col in COMPANY_EXPORT_COLUMNS})
    return rows


def export_companies_excel(db, *, include_deleted: bool = False) -> BytesIO:
    from openpyxl import Workbook

    rows = companies_for_export(db, include_deleted=include_deleted)
    wb = Workbook()
    ws = wb.active
    ws.title = "Companies"
    headers = list(COMPANY_EXPORT_COLUMNS)
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h, "") for h in headers])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def export_companies_csv(db, *, include_deleted: bool = False) -> str:
    rows = companies_for_export(db, include_deleted=include_deleted)
    si = io.StringIO()
    writer = csv.writer(si)
    headers = list(COMPANY_EXPORT_COLUMNS)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row.get(h, "") for h in headers])
    return si.getvalue()


def export_companies_pdf(db, *, include_deleted: bool = False) -> BytesIO:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas

    rows = companies_for_export(db, include_deleted=include_deleted)
    buf = BytesIO()
    page_size = landscape(A4)
    c = canvas.Canvas(buf, pagesize=page_size)
    width, height = page_size
    y = height - 40
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, "MAXEK ERP — Company Master Export")
    y -= 24
    c.setFont("Helvetica", 9)
    for row in rows[:200]:
        line = f"{row.get('company_code')} | {row.get('company_name')} | {row.get('legal_name')} | {row.get('country')} | {row.get('status')}"
        if y < 40:
            c.showPage()
            y = height - 40
            c.setFont("Helvetica", 9)
        c.drawString(40, y, line[:120])
        y -= 14
    c.save()
    buf.seek(0)
    return buf


def company_import_template() -> BytesIO:
    from bulk_import_service import build_xlsx_template

    return build_xlsx_template(
        [
            "Company Code",
            "Company Name",
            "Legal Name",
            "Company Type",
            "GST Number",
            "PAN Number",
            "TAN Number",
            "CIN Number",
            "Country",
            "State",
            "District",
            "City",
            "PIN Code",
            "Phone",
            "Email",
            "Website",
            "Currency",
            "Financial Year",
            "Timezone",
            "Language",
            "Status",
        ],
        [
            "CO-2026-0001",
            "Sample Construction Pvt Ltd",
            "Sample Construction Private Limited",
            "Private Limited",
            "",
            "",
            "",
            "",
            "India",
            "Maharashtra",
            "Mumbai",
            "Mumbai",
            "400001",
            "+91 9876543210",
            "info@sample.com",
            "https://sample.com",
            "INR",
            "April-March",
            "Asia/Kolkata",
            "en",
            "Active",
        ],
    )
