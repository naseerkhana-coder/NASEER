"""Subcontractor Master (MODULE-013) — construction subcontractor registry with contacts, trades, compliance."""

from __future__ import annotations

import csv
import io
import json
import re
from io import BytesIO
from typing import Any

from company_master_service import (
    _ensure_column,
    _now_ts,
    _table_exists,
    validate_email,
    validate_gst_number,
    validate_pan_number,
    validate_phone,
)
from store_service import TRADE_CATEGORY_OPTIONS, encode_json_string_list
from vendor_master_service import PAYMENT_TERMS_OPTIONS

SUBCONTRACTOR_STATUSES = ("Active", "Inactive")
APPROVAL_STATUSES = ("Draft", "Pending", "Approved", "Rejected")
ADDRESS_TYPES = ("Office", "Site", "Billing", "Other")
SUBCONTRACTOR_CLASSIFICATIONS = (
    "Labour Contractor",
    "Civil Subcontractor",
    "MEP Subcontractor",
    "Specialty Trade",
    "Equipment Hirer",
    "Other",
)
SUBCONTRACTOR_RATE_TYPES = (
    "Labour Supply",
    "Item Rate Contract",
    "Measurement Based Contract",
    "Lump Sum Contract",
)
SUBCONTRACTOR_SORT_COLUMNS = (
    "subcontractor_code",
    "subcontractor_name",
    "gst_number",
    "status",
    "rating",
    "created_at",
    "classification",
)
SUBCONTRACTOR_EXPORT_COLUMNS = (
    "subcontractor_code",
    "subcontractor_name",
    "legal_name",
    "classification",
    "trade_categories",
    "rate_type",
    "gst_number",
    "pan_number",
    "contact_person",
    "phone",
    "email",
    "mobile",
    "address",
    "city",
    "state",
    "pincode",
    "payment_terms",
    "retention_percent",
    "security_deposit",
    "insurance_policy_no",
    "insurance_expiry",
    "labour_license_no",
    "labour_license_expiry",
    "rating",
    "vendor_code",
    "status",
    "approval_status",
    "is_approved",
    "is_blacklisted",
)
SUBCONTRACTOR_AUDIT_FIELDS = (
    "subcontractor_code",
    "subcontractor_name",
    "legal_name",
    "company_name",
    "classification",
    "trade_categories",
    "rate_type",
    "gst_number",
    "pan_number",
    "contact_person",
    "phone",
    "email",
    "mobile",
    "address",
    "city",
    "state",
    "pincode",
    "payment_terms",
    "payment_mode",
    "retention_percent",
    "security_deposit",
    "insurance_policy_no",
    "insurance_expiry",
    "labour_license_no",
    "labour_license_expiry",
    "rating",
    "vendor_id",
    "status",
    "approval_status",
    "is_approved",
    "is_blacklisted",
    "remarks",
    "joining_date",
    "region",
)
SUBCONTRACTOR_REFERENCE_TABLES = (
    ("workers", "subcontractor_id"),
    ("subcontract_requests", "subcontractor_id"),
    ("subcontract_work_orders", "subcontractor_id"),
    ("subcontractor_bills", "subcontractor_id"),
    ("dpr_manpower", "subcontractor_id"),
)


def validate_labour_license(license_no: str) -> None:
    raw = (license_no or "").strip()
    if not raw:
        return
    if len(raw) < 5 or len(raw) > 50:
        raise ValueError("Labour license number must be 5–50 characters.")
    if not re.match(r"^[A-Za-z0-9/\-]+$", raw):
        raise ValueError("Labour license number contains invalid characters.")


def _column_exists(db, table: str, column: str) -> bool:
    if not _table_exists(db, table):
        return False
    cols = [r[1] for r in db.execute(f"PRAGMA table_info({table})").fetchall()]
    return column in cols


def _clean_name_letters(name: str) -> str:
    return re.sub(r"[^A-Za-z]", "", str(name or ""))


def _subcontractor_prefix_candidates(name: str) -> list[str]:
    letters = _clean_name_letters(name)
    if len(letters) >= 2:
        return [letters[:2].upper()]
    if len(letters) == 1:
        return [(letters + "U")[:2].upper()]
    return ["SU"]


def _subcontractor_prefix_in_use(db, prefix: str, exclude_id: int | None = None) -> bool:
    prefix = (prefix or "").upper()
    rows = db.execute(
        "SELECT id, subcontractor_code FROM subcontractors "
        "WHERE subcontractor_code IS NOT NULL AND TRIM(subcontractor_code) != ''"
    ).fetchall()
    for row in rows:
        rid = int(row[0] if isinstance(row, tuple) else row["id"])
        if exclude_id is not None and rid == exclude_id:
            continue
        code = str(row[1] if isinstance(row, tuple) else row["subcontractor_code"] or "").strip().upper()
        stored_prefix = code[:2] if len(code) >= 2 else code
        if stored_prefix == prefix:
            return True
    return False


def _max_prefix_code_number(db, prefix: str) -> int:
    max_num = 99
    for table, column in (("subcontractors", "subcontractor_code"), ("workers", "worker_code")):
        if not _table_exists(db, table):
            continue
        rows = db.execute(
            f"SELECT {column} AS code FROM {table} WHERE {column} LIKE ?",
            (f"{prefix}%",),
        ).fetchall()
        for row in rows:
            code = str(row[0] if isinstance(row, tuple) else row["code"] or "").strip().upper()
            suffix = code[len(prefix) :]
            if suffix.isdigit():
                max_num = max(max_num, int(suffix))
    return max_num


def generate_subcontractor_master_code(db, name: str, exclude_id: int | None = None) -> str:
    for prefix in _subcontractor_prefix_candidates(name):
        if not _subcontractor_prefix_in_use(db, prefix, exclude_id=exclude_id):
            max_num = _max_prefix_code_number(db, prefix)
            next_num = 100 if max_num < 100 else max_num + 1
            return f"{prefix}{next_num}"
    prefix = _subcontractor_prefix_candidates(name)[0]
    max_num = _max_prefix_code_number(db, prefix)
    return f"{prefix}{(max_num + 1) if max_num >= 100 else 100}"


def trade_categories_list(row: dict | None) -> list[str]:
    if not row:
        return []
    raw = row.get("trade_categories")
    if isinstance(raw, list):
        return [str(v).strip() for v in raw if str(v).strip()]
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(v).strip() for v in parsed if str(v).strip()]
        except (json.JSONDecodeError, TypeError):
            pass
        return [v.strip() for v in str(raw).split(",") if v.strip()]
    trades = row.get("trades") or []
    return [str(t.get("trade_name") or t) for t in trades if str(t.get("trade_name") or t).strip()]


def ensure_subcontractor_master_permission(db) -> None:
    if not _table_exists(db, "permissions"):
        return
    screen = "subcontractor_master"
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
        ) VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "SET-SUBCONTRACTOR-MASTER",
            "Subcontractor Master",
            "Settings",
            "Settings",
            screen,
            "",
            "Access to Subcontractor Master",
            "Active",
            "system",
            now,
        ),
    )


def ensure_subcontractor_master_schema(db) -> None:
    """Extend subcontractors and child tables for MODULE-013 (idempotent)."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS subcontractors(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subcontractor_name TEXT,
            company_name TEXT,
            mobile TEXT,
            email TEXT,
            address TEXT,
            work_type TEXT,
            payment_mode TEXT,
            working_hours REAL,
            gst_number TEXT,
            id_proof TEXT,
            status TEXT
        )
        """
    )
    for col, ctype in (
        ("subcontractor_code", "TEXT"),
        ("legal_name", "TEXT"),
        ("classification", "TEXT"),
        ("trade_categories", "TEXT"),
        ("rate_type", "TEXT DEFAULT 'Labour Supply'"),
        ("vendor_id", "INTEGER"),
        ("pan_number", "TEXT"),
        ("contact_person", "TEXT"),
        ("phone", "TEXT"),
        ("city", "TEXT"),
        ("state", "TEXT"),
        ("pincode", "TEXT"),
        ("payment_terms", "TEXT"),
        ("retention_percent", "REAL DEFAULT 0"),
        ("security_deposit", "REAL DEFAULT 0"),
        ("insurance_policy_no", "TEXT"),
        ("insurance_expiry", "TEXT"),
        ("labour_license_no", "TEXT"),
        ("labour_license_expiry", "TEXT"),
        ("rating", "REAL"),
        ("approval_status", "TEXT DEFAULT 'Draft'"),
        ("approved_by", "TEXT"),
        ("approved_at", "TEXT"),
        ("created_by", "TEXT"),
        ("modified_by", "TEXT"),
        ("created_at", "TEXT"),
        ("modified_at", "TEXT"),
        ("is_deleted", "INTEGER DEFAULT 0"),
        ("deleted_by", "TEXT"),
        ("deleted_at", "TEXT"),
        ("customer_id", "INTEGER"),
        ("company_id", "INTEGER"),
        ("is_approved", "INTEGER DEFAULT 0"),
        ("is_blacklisted", "INTEGER DEFAULT 0"),
        ("remarks", "TEXT"),
        ("website", "TEXT"),
        ("joining_date", "TEXT"),
        ("region", "TEXT"),
        ("contact_number", "TEXT"),
        ("bank_account", "TEXT"),
        ("bank_name", "TEXT"),
        ("ifsc_code", "TEXT"),
        ("branch_name", "TEXT"),
    ):
        _ensure_column(db, "subcontractors", col, ctype)

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS subcontractor_contacts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subcontractor_id INTEGER NOT NULL,
            contact_name TEXT,
            designation TEXT,
            phone TEXT,
            email TEXT,
            is_primary INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(subcontractor_id) REFERENCES subcontractors(id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS subcontractor_addresses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subcontractor_id INTEGER NOT NULL,
            address_type TEXT DEFAULT 'Office',
            address_line1 TEXT,
            address_line2 TEXT,
            city TEXT,
            state TEXT,
            pincode TEXT,
            country TEXT DEFAULT 'India',
            is_primary INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(subcontractor_id) REFERENCES subcontractors(id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS subcontractor_bank_accounts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subcontractor_id INTEGER NOT NULL,
            account_holder TEXT,
            bank_name TEXT,
            account_number TEXT,
            ifsc_code TEXT,
            branch_name TEXT,
            is_primary INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(subcontractor_id) REFERENCES subcontractors(id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS subcontractor_trades(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subcontractor_id INTEGER NOT NULL,
            trade_name TEXT NOT NULL,
            is_primary INTEGER DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY(subcontractor_id) REFERENCES subcontractors(id)
        )
        """
    )
    _migrate_legacy_subcontractors(db)
    try:
        from audit_trail_service import ensure_audit_schema

        ensure_audit_schema(db)
    except Exception:
        pass
    ensure_subcontractor_master_permission(db)


def _migrate_legacy_subcontractors(db) -> None:
    if not _table_exists(db, "subcontractors"):
        return
    db.execute(
        "UPDATE subcontractors SET status='Active' WHERE status IS NULL OR TRIM(status)=''"
    )
    db.execute(
        "UPDATE subcontractors SET approval_status='Approved' "
        "WHERE approval_status IS NULL OR TRIM(approval_status)=''"
    )
    db.execute(
        "UPDATE subcontractors SET is_approved=1 WHERE approval_status='Approved' AND COALESCE(is_approved,0)=0"
    )
    now = _now_ts()
    rows = db.execute(
        """
        SELECT id, subcontractor_name, contact_person, phone, email, mobile, contact_number,
               address, city, state, pincode, bank_account, bank_name, ifsc_code, branch_name
        FROM subcontractors WHERE COALESCE(is_deleted,0)=0
        """
    ).fetchall()
    for row in rows:
        sid = int(row[0])
        has_contact = db.execute(
            "SELECT 1 FROM subcontractor_contacts WHERE subcontractor_id=? LIMIT 1", (sid,)
        ).fetchone()
        cp = row[2] or row[1]
        ph = row[3] or row[5] or row[6]
        em = row[4]
        if not has_contact and (cp or ph or em):
            db.execute(
                """
                INSERT INTO subcontractor_contacts(
                    subcontractor_id, contact_name, phone, email, is_primary, created_at, modified_at
                ) VALUES(?,?,?,?,1,?,?)
                """,
                (sid, cp or "", ph or "", em or "", now, now),
            )
        has_addr = db.execute(
            "SELECT 1 FROM subcontractor_addresses WHERE subcontractor_id=? LIMIT 1", (sid,)
        ).fetchone()
        if not has_addr and (row[7] or row[8] or row[9] or row[10]):
            db.execute(
                """
                INSERT INTO subcontractor_addresses(
                    subcontractor_id, address_type, address_line1, city, state, pincode,
                    is_primary, created_at, modified_at
                ) VALUES(?,?,?,?,?,?,1,?,?)
                """,
                (sid, "Office", row[7] or "", row[8] or "", row[9] or "", row[10] or "", now, now),
            )
        if row[11] or row[12] or row[13]:
            has_bank = db.execute(
                "SELECT 1 FROM subcontractor_bank_accounts WHERE subcontractor_id=? LIMIT 1", (sid,)
            ).fetchone()
            if not has_bank:
                db.execute(
                    """
                    INSERT INTO subcontractor_bank_accounts(
                        subcontractor_id, account_holder, bank_name, account_number, ifsc_code,
                        branch_name, is_primary, created_at, modified_at
                    ) VALUES(?,?,?,?,?,?,1,?,?)
                    """,
                    (sid, cp or "", row[12] or "", row[11] or "", row[13] or "", row[14] or "", now, now),
                )


def validate_subcontractor_uniqueness(
    db,
    *,
    subcontractor_code: str,
    gst_number: str = "",
    subcontractor_id: int | None = None,
) -> None:
    code = (subcontractor_code or "").strip().upper()
    gst = (gst_number or "").strip().upper()
    if not code:
        raise ValueError("Subcontractor code is required.")
    dup_code = db.execute(
        """
        SELECT id FROM subcontractors WHERE UPPER(TRIM(subcontractor_code))=?
        AND COALESCE(is_deleted,0)=0 AND (? IS NULL OR id!=?)
        """,
        (code, subcontractor_id, subcontractor_id),
    ).fetchone()
    if dup_code:
        raise ValueError(f"Subcontractor code '{code}' already exists.")
    if gst:
        dup_gst = db.execute(
            """
            SELECT id, subcontractor_code FROM subcontractors
            WHERE UPPER(TRIM(gst_number))=? AND COALESCE(is_deleted,0)=0
            AND (? IS NULL OR id!=?)
            """,
            (gst, subcontractor_id, subcontractor_id),
        ).fetchone()
        if dup_gst:
            sc = dup_gst[1] if isinstance(dup_gst, tuple) else dup_gst["subcontractor_code"]
            raise ValueError(f"GST '{gst}' is already registered to subcontractor {sc}.")


def subcontractor_has_transactions(db, subcontractor_id: int) -> bool:
    for table, column in SUBCONTRACTOR_REFERENCE_TABLES:
        if not _table_exists(db, table):
            continue
        if not _column_exists(db, table, column):
            continue
        hit = db.execute(
            f"SELECT 1 FROM {table} WHERE {column}=? LIMIT 1", (subcontractor_id,)
        ).fetchone()
        if hit:
            return True
    return False


def log_subcontractor_audit(
    db,
    subcontractor_id: int,
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
            record_table="subcontractors",
            record_id=subcontractor_id,
            action=action,
            changed_by=username,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            remarks=remarks,
        )
    except Exception:
        pass


def log_subcontractor_field_changes(
    db,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    username: str,
) -> None:
    if not before or not after:
        return
    sid = int(after.get("id") or before.get("id") or 0)
    if not sid:
        return
    for field in SUBCONTRACTOR_AUDIT_FIELDS:
        old_val = before.get(field)
        new_val = after.get(field)
        if str(old_val or "") != str(new_val or ""):
            log_subcontractor_audit(
                db,
                sid,
                "update",
                username,
                field_name=field,
                old_value=str(old_val or ""),
                new_value=str(new_val or ""),
            )


def list_subcontractor_audit_trail(db, subcontractor_id: int, limit: int = 100) -> list[dict[str, Any]]:
    try:
        from audit_trail_service import list_audit_trail

        return list_audit_trail(db, "subcontractors", subcontractor_id, limit=limit)
    except Exception:
        return []


def _parse_trade_categories(form) -> list[str]:
    if hasattr(form, "getlist"):
        selected = form.getlist("trade_categories[]") or form.getlist("trade_categories")
    else:
        raw = form.get("trade_categories") or form.get("trade_categories[]") or []
        selected = raw if isinstance(raw, list) else [raw] if raw else []
    cleaned = [str(v).strip() for v in selected if str(v).strip()]
    valid = [v for v in cleaned if v in TRADE_CATEGORY_OPTIONS]
    return valid or cleaned


def _parse_child_rows(form, prefix: str, fields: tuple[str, ...]) -> list[dict[str, str]]:
    lists: dict[str, list[str]] = {}
    getlist = getattr(form, "getlist", None)
    for field in fields:
        key = f"{prefix}_{field}[]"
        if getlist:
            lists[field] = getlist(key) or getlist(f"{prefix}_{field}")
        else:
            val = form.get(key) or form.get(f"{prefix}_{field}")
            lists[field] = val if isinstance(val, list) else ([val] if val else [])
    count = max((len(v) for v in lists.values()), default=0)
    rows: list[dict[str, str]] = []
    for idx in range(count):
        row = {f: (lists[f][idx] if idx < len(lists[f]) else "").strip() for f in fields}
        if any(row.values()):
            rows.append(row)
    return rows


def _parse_subcontractor_form(form) -> dict[str, Any]:
    code = (form.get("subcontractor_code") or "").strip().upper()
    name = (form.get("subcontractor_name") or "").strip()
    gst = (form.get("gst_number") or form.get("gstin") or "").strip().upper()
    pan = (form.get("pan_number") or form.get("pan") or "").strip().upper()
    status = (form.get("status") or "Active").strip()
    rate_type = (form.get("rate_type") or "Labour Supply").strip()
    classification = (form.get("classification") or "").strip()
    payment_terms = (form.get("payment_terms") or "").strip()
    trade_categories = _parse_trade_categories(form)
    retention_raw = (form.get("retention_percent") or "0").strip()
    deposit_raw = (form.get("security_deposit") or "0").strip()
    rating_raw = (form.get("rating") or "").strip()
    vendor_id_raw = form.get("vendor_id")
    vendor_id = int(vendor_id_raw) if vendor_id_raw and str(vendor_id_raw).isdigit() else None
    try:
        retention_percent = float(retention_raw) if retention_raw else 0.0
    except ValueError:
        retention_percent = 0.0
    try:
        security_deposit = float(deposit_raw) if deposit_raw else 0.0
    except ValueError:
        security_deposit = 0.0
    try:
        rating = float(rating_raw) if rating_raw else None
    except ValueError:
        rating = None
    if rating is not None and (rating < 0 or rating > 5):
        raise ValueError("Rating must be between 0 and 5.")
    if retention_percent < 0 or retention_percent > 100:
        raise ValueError("Retention percent must be between 0 and 100.")
    is_approved = 1 if str(form.get("is_approved", "")).lower() in ("1", "on", "true", "yes") else 0
    is_blacklisted = 1 if str(form.get("is_blacklisted", "")).lower() in ("1", "on", "true", "yes") else 0
    company_id_raw = form.get("company_id")
    company_id = int(company_id_raw) if company_id_raw and str(company_id_raw).isdigit() else None
    return {
        "subcontractor_code": code,
        "subcontractor_name": name,
        "legal_name": (form.get("legal_name") or form.get("company_name") or "").strip(),
        "company_name": (form.get("company_name") or form.get("legal_name") or "").strip(),
        "classification": classification,
        "trade_categories": encode_json_string_list(trade_categories),
        "trade_categories_list": trade_categories,
        "rate_type": rate_type if rate_type in SUBCONTRACTOR_RATE_TYPES else "Labour Supply",
        "gst_number": gst,
        "pan_number": pan,
        "contact_person": (form.get("contact_person") or "").strip(),
        "phone": (form.get("phone") or form.get("contact_number") or "").strip(),
        "mobile": (form.get("mobile") or "").strip(),
        "email": (form.get("email") or "").strip(),
        "address": (form.get("address") or "").strip(),
        "city": (form.get("city") or "").strip(),
        "state": (form.get("state") or "").strip(),
        "pincode": (form.get("pincode") or "").strip(),
        "payment_terms": payment_terms,
        "payment_mode": (form.get("payment_mode") or "").strip(),
        "working_hours": form.get("working_hours"),
        "retention_percent": retention_percent,
        "security_deposit": security_deposit,
        "insurance_policy_no": (form.get("insurance_policy_no") or "").strip(),
        "insurance_expiry": (form.get("insurance_expiry") or "").strip(),
        "labour_license_no": (form.get("labour_license_no") or "").strip(),
        "labour_license_expiry": (form.get("labour_license_expiry") or "").strip(),
        "rating": rating,
        "vendor_id": vendor_id,
        "status": status,
        "is_approved": is_approved,
        "is_blacklisted": is_blacklisted,
        "remarks": (form.get("remarks") or "").strip(),
        "website": (form.get("website") or "").strip(),
        "joining_date": (form.get("joining_date") or "").strip(),
        "region": (form.get("region") or "").strip(),
        "contact_number": (form.get("contact_number") or form.get("phone") or "").strip(),
        "company_id": company_id,
    }


def _save_subcontractor_children(db, subcontractor_id: int, form, trade_list: list[str]) -> None:
    now = _now_ts()
    db.execute("DELETE FROM subcontractor_contacts WHERE subcontractor_id=?", (subcontractor_id,))
    db.execute("DELETE FROM subcontractor_addresses WHERE subcontractor_id=?", (subcontractor_id,))
    db.execute("DELETE FROM subcontractor_bank_accounts WHERE subcontractor_id=?", (subcontractor_id,))
    db.execute("DELETE FROM subcontractor_trades WHERE subcontractor_id=?", (subcontractor_id,))

    contacts = _parse_child_rows(
        form, "contact", ("name", "designation", "phone", "email", "primary")
    )
    if not contacts:
        cp = (form.get("contact_person") or "").strip()
        ph = (form.get("phone") or form.get("contact_number") or "").strip()
        em = (form.get("email") or "").strip()
        if cp or ph or em:
            contacts = [{"name": cp, "designation": "", "phone": ph, "email": em, "primary": "1"}]
    for idx, c in enumerate(contacts):
        is_primary = 1 if c.get("primary") in ("1", "on", "true") or idx == 0 else 0
        db.execute(
            """
            INSERT INTO subcontractor_contacts(
                subcontractor_id, contact_name, designation, phone, email, is_primary, created_at, modified_at
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                subcontractor_id,
                c.get("name", ""),
                c.get("designation", ""),
                c.get("phone", ""),
                c.get("email", ""),
                is_primary,
                now,
                now,
            ),
        )

    addresses = _parse_child_rows(
        form,
        "addr",
        ("type", "line1", "line2", "city", "state", "pincode", "country", "primary"),
    )
    if not addresses:
        line1 = (form.get("address") or "").strip()
        if line1 or (form.get("city") or "").strip():
            addresses = [
                {
                    "type": "Office",
                    "line1": line1,
                    "line2": "",
                    "city": (form.get("city") or "").strip(),
                    "state": (form.get("state") or "").strip(),
                    "pincode": (form.get("pincode") or "").strip(),
                    "country": "India",
                    "primary": "1",
                }
            ]
    for idx, a in enumerate(addresses):
        addr_type = a.get("type") or "Office"
        if addr_type not in ADDRESS_TYPES:
            addr_type = "Other"
        is_primary = 1 if a.get("primary") in ("1", "on", "true") or idx == 0 else 0
        db.execute(
            """
            INSERT INTO subcontractor_addresses(
                subcontractor_id, address_type, address_line1, address_line2, city, state, pincode,
                country, is_primary, created_at, modified_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                subcontractor_id,
                addr_type,
                a.get("line1", ""),
                a.get("line2", ""),
                a.get("city", ""),
                a.get("state", ""),
                a.get("pincode", ""),
                a.get("country") or "India",
                is_primary,
                now,
                now,
            ),
        )

    banks = _parse_child_rows(
        form,
        "bank",
        ("holder", "bank_name", "account_number", "ifsc", "branch", "primary"),
    )
    if not banks:
        acct = (form.get("bank_account") or "").strip()
        bname = (form.get("bank_name") or "").strip()
        ifsc = (form.get("ifsc_code") or "").strip().upper()
        branch = (form.get("branch_name") or "").strip()
        if acct or bname or ifsc:
            banks = [
                {
                    "holder": (form.get("contact_person") or form.get("subcontractor_name") or "").strip(),
                    "bank_name": bname,
                    "account_number": acct,
                    "ifsc": ifsc,
                    "branch": branch,
                    "primary": "1",
                }
            ]
    for idx, b in enumerate(banks):
        acct_no = b.get("account_number", "")
        is_primary = 1 if b.get("primary") in ("1", "on", "true") or idx == 0 else 0
        db.execute(
            """
            INSERT INTO subcontractor_bank_accounts(
                subcontractor_id, account_holder, bank_name, account_number, ifsc_code, branch_name,
                is_primary, created_at, modified_at
            ) VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (
                subcontractor_id,
                b.get("holder", ""),
                b.get("bank_name", ""),
                acct_no,
                (b.get("ifsc") or "").upper(),
                b.get("branch", ""),
                is_primary,
                now,
                now,
            ),
        )
        if is_primary:
            db.execute(
                """
                UPDATE subcontractors SET bank_account=?, bank_name=?, ifsc_code=?, branch_name=?
                WHERE id=?
                """,
                (acct_no, b.get("bank_name", ""), (b.get("ifsc") or "").upper(), b.get("branch", ""), subcontractor_id),
            )

    for idx, trade in enumerate(trade_list):
        if not trade:
            continue
        db.execute(
            """
            INSERT INTO subcontractor_trades(subcontractor_id, trade_name, is_primary, created_at)
            VALUES(?,?,?,?)
            """,
            (subcontractor_id, trade, 1 if idx == 0 else 0, now),
        )


def _sync_primary_fields_from_children(db, subcontractor_id: int) -> None:
    contact = db.execute(
        "SELECT contact_name, phone, email FROM subcontractor_contacts WHERE subcontractor_id=? "
        "ORDER BY is_primary DESC, id LIMIT 1",
        (subcontractor_id,),
    ).fetchone()
    addr = db.execute(
        "SELECT address_line1, city, state, pincode FROM subcontractor_addresses WHERE subcontractor_id=? "
        "ORDER BY is_primary DESC, id LIMIT 1",
        (subcontractor_id,),
    ).fetchone()
    sets: list[str] = []
    params: list[Any] = []
    if contact:
        sets.extend(["contact_person=?", "phone=?", "email=?"])
        params.extend([contact[0], contact[1], contact[2]])
    if addr:
        sets.extend(["address=?", "city=?", "state=?", "pincode=?"])
        params.extend([addr[0], addr[1], addr[2], addr[3]])
    if sets:
        params.append(subcontractor_id)
        db.execute(f"UPDATE subcontractors SET {', '.join(sets)} WHERE id=?", params)


def save_subcontractor_master(
    db,
    form,
    username: str,
    subcontractor_id: int | None = None,
    *,
    customer_id: int | None = None,
) -> int:
    data = _parse_subcontractor_form(form)
    if not data["subcontractor_name"]:
        raise ValueError("Subcontractor name is required.")
    if not data["trade_categories_list"]:
        raise ValueError("At least one trade category is required.")
    if not subcontractor_id and not data["subcontractor_code"]:
        data["subcontractor_code"] = generate_subcontractor_master_code(db, data["subcontractor_name"])
    if data["status"] not in SUBCONTRACTOR_STATUSES:
        raise ValueError("Select a valid status.")
    if data["classification"] and data["classification"] not in SUBCONTRACTOR_CLASSIFICATIONS:
        raise ValueError("Select a valid classification.")
    if data["payment_terms"] and data["payment_terms"] not in PAYMENT_TERMS_OPTIONS:
        raise ValueError("Select a valid payment term.")
    if data["email"]:
        validate_email(data["email"])
    if data["phone"]:
        validate_phone(data["phone"])
    if data["mobile"]:
        validate_phone(data["mobile"])
    if data["gst_number"]:
        validate_gst_number(data["gst_number"])
    if data["pan_number"]:
        validate_pan_number(data["pan_number"])
    validate_labour_license(data["labour_license_no"])
    validate_subcontractor_uniqueness(
        db,
        subcontractor_code=data["subcontractor_code"],
        gst_number=data["gst_number"],
        subcontractor_id=subcontractor_id,
    )
    if data["vendor_id"]:
        dup_vendor = db.execute(
            """
            SELECT id, subcontractor_name FROM subcontractors
            WHERE vendor_id=? AND COALESCE(is_deleted,0)=0 AND (? IS NULL OR id!=?)
            """,
            (data["vendor_id"], subcontractor_id, subcontractor_id),
        ).fetchone()
        if dup_vendor:
            raise ValueError("Selected vendor is already linked to another subcontractor.")
    if data["is_blacklisted"] and data["status"] == "Active" and not subcontractor_id:
        data["status"] = "Inactive"

    wh_raw = data.get("working_hours")
    try:
        working_hours = float(wh_raw) if wh_raw not in (None, "") else None
    except (TypeError, ValueError):
        working_hours = None

    now = _now_ts()
    core = (
        data["subcontractor_code"],
        data["subcontractor_name"],
        data["legal_name"],
        data["company_name"],
        data["classification"],
        data["trade_categories"],
        data["rate_type"],
        data["gst_number"],
        data["pan_number"],
        data["contact_person"],
        data["phone"],
        data["mobile"],
        data["email"],
        data["address"],
        data["city"],
        data["state"],
        data["pincode"],
        data["payment_terms"],
        data["payment_mode"],
        working_hours,
        data["retention_percent"],
        data["security_deposit"],
        data["insurance_policy_no"],
        data["insurance_expiry"],
        data["labour_license_no"],
        data["labour_license_expiry"],
        data["rating"],
        data["vendor_id"],
        data["status"],
        data["is_approved"],
        data["is_blacklisted"],
        data["remarks"],
        data["website"],
        data["joining_date"],
        data["region"],
        data["contact_number"],
        data["company_id"],
    )
    if subcontractor_id:
        existing = get_subcontractor_master(db, subcontractor_id, include_deleted=True)
        if not existing:
            raise ValueError("Subcontractor not found.")
        db.execute(
            """
            UPDATE subcontractors SET subcontractor_code=?, subcontractor_name=?, legal_name=?, company_name=?,
            classification=?, trade_categories=?, rate_type=?, gst_number=?, pan_number=?, contact_person=?,
            phone=?, mobile=?, email=?, address=?, city=?, state=?, pincode=?, payment_terms=?, payment_mode=?,
            working_hours=?, retention_percent=?, security_deposit=?, insurance_policy_no=?, insurance_expiry=?,
            labour_license_no=?, labour_license_expiry=?, rating=?, vendor_id=?, status=?, is_approved=?,
            is_blacklisted=?, remarks=?, website=?, joining_date=?, region=?, contact_number=?, company_id=?,
            modified_by=?, modified_at=? WHERE id=?
            """,
            (*core, username, now, subcontractor_id),
        )
        if customer_id is not None:
            db.execute("UPDATE subcontractors SET customer_id=? WHERE id=?", (customer_id, subcontractor_id))
        _save_subcontractor_children(db, subcontractor_id, form, data["trade_categories_list"])
        _sync_primary_fields_from_children(db, subcontractor_id)
        log_subcontractor_field_changes(
            db, existing, get_subcontractor_master(db, subcontractor_id, include_deleted=True), username
        )
        return subcontractor_id

    approval_status = (form.get("approval_status") or "Draft").strip()
    if approval_status not in APPROVAL_STATUSES:
        approval_status = "Draft"
    cur = db.execute(
        """
        INSERT INTO subcontractors(
            subcontractor_code, subcontractor_name, legal_name, company_name, classification, trade_categories,
            rate_type, gst_number, pan_number, contact_person, phone, mobile, email, address, city, state, pincode,
            payment_terms, payment_mode, working_hours, retention_percent, security_deposit, insurance_policy_no,
            insurance_expiry, labour_license_no, labour_license_expiry, rating, vendor_id, status, is_approved,
            is_blacklisted, remarks, website, joining_date, region, contact_number, company_id, approval_status,
            created_by, created_at, modified_by, modified_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (*core, approval_status, username, now, username, now),
    )
    new_id = int(cur.lastrowid)
    if customer_id is not None:
        db.execute("UPDATE subcontractors SET customer_id=? WHERE id=?", (customer_id, new_id))
    _save_subcontractor_children(db, new_id, form, data["trade_categories_list"])
    _sync_primary_fields_from_children(db, new_id)
    log_subcontractor_audit(
        db, new_id, "create", username, remarks=f"Created subcontractor {data['subcontractor_code']}"
    )
    return new_id


def _load_subcontractor_children(db, subcontractor_id: int) -> dict[str, list[dict[str, Any]]]:
    contacts = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM subcontractor_contacts WHERE subcontractor_id=? ORDER BY is_primary DESC, id",
            (subcontractor_id,),
        ).fetchall()
    ]
    addresses = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM subcontractor_addresses WHERE subcontractor_id=? ORDER BY is_primary DESC, id",
            (subcontractor_id,),
        ).fetchall()
    ]
    banks = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM subcontractor_bank_accounts WHERE subcontractor_id=? ORDER BY is_primary DESC, id",
            (subcontractor_id,),
        ).fetchall()
    ]
    trades = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM subcontractor_trades WHERE subcontractor_id=? ORDER BY is_primary DESC, id",
            (subcontractor_id,),
        ).fetchall()
    ]
    return {"contacts": contacts, "addresses": addresses, "bank_accounts": banks, "trades": trades}


def get_subcontractor_master(
    db, subcontractor_id: int, *, include_deleted: bool = False
) -> dict[str, Any] | None:
    if _table_exists(db, "vendors"):
        sql = (
            "SELECT s.*, v.code AS vendor_code FROM subcontractors s "
            "LEFT JOIN vendors v ON s.vendor_id=v.id WHERE s.id=?"
        )
    else:
        sql = "SELECT s.*, NULL AS vendor_code FROM subcontractors s WHERE s.id=?"
    if not include_deleted:
        sql += " AND COALESCE(s.is_deleted,0)=0"
    row = db.execute(sql, (subcontractor_id,)).fetchone()
    if not row:
        return None
    data = dict(row)
    data["trade_categories_list"] = trade_categories_list(data)
    children = _load_subcontractor_children(db, subcontractor_id)
    data.update(children)
    try:
        from document_management_service import list_module_documents

        data["documents"] = list_module_documents(db, "subcontractor_master", subcontractor_id)
    except Exception:
        data["documents"] = []
    return data


def list_subcontractors_master(
    db,
    *,
    search: str = "",
    status: str = "",
    classification: str = "",
    trade_category: str = "",
    approval_status: str = "",
    is_blacklisted: bool | None = None,
    is_approved: bool | None = None,
    include_deleted: bool = False,
    page: int = 1,
    per_page: int = 25,
    sort_by: str = "subcontractor_name",
    sort_dir: str = "asc",
) -> dict[str, Any]:
    if not _table_exists(db, "subcontractors"):
        return {"items": [], "total": 0, "page": 1, "per_page": per_page, "pages": 0}
    if _table_exists(db, "vendors"):
        sql = "SELECT s.*, v.code AS vendor_code FROM subcontractors s LEFT JOIN vendors v ON s.vendor_id=v.id WHERE 1=1"
    else:
        sql = "SELECT s.*, NULL AS vendor_code FROM subcontractors s WHERE 1=1"
    count_sql = "SELECT COUNT(*) FROM subcontractors s WHERE 1=1"
    params: list[Any] = []
    if not include_deleted:
        sql += " AND COALESCE(s.is_deleted,0)=0"
        count_sql += " AND COALESCE(s.is_deleted,0)=0"
    if status:
        sql += " AND s.status=?"
        count_sql += " AND s.status=?"
        params.append(status)
    if classification:
        sql += " AND s.classification=?"
        count_sql += " AND s.classification=?"
        params.append(classification)
    if approval_status:
        sql += " AND s.approval_status=?"
        count_sql += " AND s.approval_status=?"
        params.append(approval_status)
    if trade_category:
        sql += " AND (s.trade_categories LIKE ? OR EXISTS (SELECT 1 FROM subcontractor_trades t WHERE t.subcontractor_id=s.id AND t.trade_name=?))"
        count_sql += " AND (s.trade_categories LIKE ? OR EXISTS (SELECT 1 FROM subcontractor_trades t WHERE t.subcontractor_id=s.id AND t.trade_name=?))"
        params.extend([f'%"{trade_category}"%', trade_category])
    if is_blacklisted is True:
        sql += " AND COALESCE(s.is_blacklisted,0)=1"
        count_sql += " AND COALESCE(s.is_blacklisted,0)=1"
    elif is_blacklisted is False:
        sql += " AND COALESCE(s.is_blacklisted,0)=0"
        count_sql += " AND COALESCE(s.is_blacklisted,0)=0"
    if is_approved is True:
        sql += " AND COALESCE(s.is_approved,0)=1"
        count_sql += " AND COALESCE(s.is_approved,0)=1"
    elif is_approved is False:
        sql += " AND COALESCE(s.is_approved,0)=0"
        count_sql += " AND COALESCE(s.is_approved,0)=0"
    if search:
        clause = (
            " AND (s.subcontractor_name LIKE ? OR s.subcontractor_code LIKE ? OR s.gst_number LIKE ? "
            "OR s.pan_number LIKE ? OR s.contact_person LIKE ? OR s.phone LIKE ? OR s.email LIKE ? OR s.city LIKE ?)"
        )
        sql += clause
        count_sql += clause
        like = f"%{search}%"
        params.extend([like] * 8)
    sort_col = sort_by if sort_by in SUBCONTRACTOR_SORT_COLUMNS else "subcontractor_name"
    direction = "DESC" if str(sort_dir).lower() == "desc" else "ASC"
    sql += f" ORDER BY s.{sort_col} {direction}, s.id DESC"
    per_page = max(1, min(int(per_page or 25), 10000))
    page = max(1, int(page or 1))
    offset = (page - 1) * per_page
    sql += " LIMIT ? OFFSET ?"
    total = int(db.execute(count_sql, params).fetchone()[0])
    rows = db.execute(sql, [*params, per_page, offset]).fetchall()
    items = []
    for r in rows:
        item = dict(r)
        item["trade_categories_list"] = trade_categories_list(item)
        items.append(item)
    pages = (total + per_page - 1) // per_page if total else 0
    return {"items": items, "total": total, "page": page, "per_page": per_page, "pages": pages}


def soft_delete_subcontractor_master(db, subcontractor_id: int, username: str) -> None:
    if not subcontractor_id:
        raise ValueError("Invalid subcontractor.")
    row = get_subcontractor_master(db, subcontractor_id, include_deleted=True)
    if not row:
        raise ValueError("Subcontractor not found.")
    if row.get("is_deleted"):
        return
    if subcontractor_has_transactions(db, subcontractor_id):
        raise ValueError(
            "Subcontractor cannot be deleted because work orders, workers, bills, or projects reference it. "
            "Deactivate instead."
        )
    now = _now_ts()
    db.execute(
        """
        UPDATE subcontractors SET is_deleted=1, deleted_by=?, deleted_at=?, modified_by=?, modified_at=?,
        status='Inactive' WHERE id=?
        """,
        (username, now, username, now, subcontractor_id),
    )
    log_subcontractor_audit(
        db,
        subcontractor_id,
        "soft_delete",
        username,
        remarks=f"Soft-deleted subcontractor {row.get('subcontractor_code')}",
    )


def activate_subcontractor_master(db, subcontractor_id: int, username: str) -> None:
    if not get_subcontractor_master(db, subcontractor_id):
        raise ValueError("Subcontractor not found.")
    row = db.execute("SELECT is_blacklisted FROM subcontractors WHERE id=?", (subcontractor_id,)).fetchone()
    if row and int(row[0] or 0):
        raise ValueError("Blacklisted subcontractors cannot be activated until blacklist is cleared.")
    now = _now_ts()
    db.execute(
        "UPDATE subcontractors SET status='Active', modified_by=?, modified_at=? WHERE id=?",
        (username, now, subcontractor_id),
    )
    log_subcontractor_audit(
        db,
        subcontractor_id,
        "activate",
        username,
        field_name="status",
        old_value="Inactive",
        new_value="Active",
    )


def deactivate_subcontractor_master(db, subcontractor_id: int, username: str) -> None:
    if not get_subcontractor_master(db, subcontractor_id):
        raise ValueError("Subcontractor not found.")
    now = _now_ts()
    db.execute(
        "UPDATE subcontractors SET status='Inactive', modified_by=?, modified_at=? WHERE id=?",
        (username, now, subcontractor_id),
    )
    log_subcontractor_audit(
        db,
        subcontractor_id,
        "deactivate",
        username,
        field_name="status",
        old_value="Active",
        new_value="Inactive",
    )


def approve_subcontractor_master(db, subcontractor_id: int, username: str) -> None:
    if not get_subcontractor_master(db, subcontractor_id):
        raise ValueError("Subcontractor not found.")
    now = _now_ts()
    db.execute(
        """
        UPDATE subcontractors SET approval_status='Approved', is_approved=1, approved_by=?, approved_at=?,
        modified_by=?, modified_at=? WHERE id=?
        """,
        (username, now, username, now, subcontractor_id),
    )
    log_subcontractor_audit(db, subcontractor_id, "approve", username, remarks="Subcontractor approved")


def reject_subcontractor_master(db, subcontractor_id: int, username: str, remarks: str = "") -> None:
    if not get_subcontractor_master(db, subcontractor_id):
        raise ValueError("Subcontractor not found.")
    now = _now_ts()
    db.execute(
        "UPDATE subcontractors SET approval_status='Rejected', is_approved=0, modified_by=?, modified_at=? WHERE id=?",
        (username, now, subcontractor_id),
    )
    log_subcontractor_audit(db, subcontractor_id, "reject", username, remarks=remarks or "Subcontractor rejected")


def user_can_subcontractor_master(
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
    action_map = {"deactivate": "edit", "activate": "edit"}
    check = action_map.get(action, action)
    try:
        from user_permission_service import empty_permission_actions, ensure_user_tab_permissions_schema, normalize_permission_actions

        ensure_user_tab_permissions_schema(db)
        row = db.execute(
            """
            SELECT granted, action_flags FROM user_tab_permissions
            WHERE user_id=? AND granted=1 AND endpoint='subcontractor_master'
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
        if check == "delete":
            return bool(actions.get("delete") or actions.get("edit"))
        return bool(actions.get(check))
    except Exception:
        return False


def subcontractors_for_export(db, *, include_deleted: bool = False, **filters) -> list[dict[str, Any]]:
    listing = list_subcontractors_master(db, include_deleted=include_deleted, per_page=10000, **filters)
    rows: list[dict[str, Any]] = []
    for item in listing["items"]:
        row = {col: item.get(col, "") for col in SUBCONTRACTOR_EXPORT_COLUMNS}
        row["trade_categories"] = ", ".join(item.get("trade_categories_list") or [])
        rows.append(row)
    return rows


def export_subcontractors_excel(db, **filters) -> BytesIO:
    from openpyxl import Workbook

    rows = subcontractors_for_export(db, **filters)
    wb = Workbook()
    ws = wb.active
    ws.title = "Subcontractors"
    headers = list(SUBCONTRACTOR_EXPORT_COLUMNS)
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h, "") for h in headers])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def export_subcontractors_csv(db, **filters) -> str:
    rows = subcontractors_for_export(db, **filters)
    si = io.StringIO()
    writer = csv.writer(si)
    headers = list(SUBCONTRACTOR_EXPORT_COLUMNS)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row.get(h, "") for h in headers])
    return si.getvalue()


def export_subcontractors_pdf(db, *, report_title: str = "Subcontractor Master Report", **filters) -> BytesIO:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas

    rows = subcontractors_for_export(db, **filters)
    buf = BytesIO()
    page_size = landscape(A4)
    c = canvas.Canvas(buf, pagesize=page_size)
    _, height = page_size
    y = height - 40
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, f"MAXEK ERP — {report_title}")
    y -= 24
    c.setFont("Helvetica", 9)
    for row in rows[:250]:
        line = (
            f"{row.get('subcontractor_code')} | {row.get('subcontractor_name')} | "
            f"{row.get('gst_number') or '—'} | {row.get('status')} | Retention: {row.get('retention_percent') or 0}%"
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


def subcontractor_report(db, report_key: str, **filters) -> list[dict[str, Any]]:
    key = (report_key or "directory").lower().strip()
    if key == "active":
        filters["status"] = "Active"
    elif key == "inactive":
        filters["status"] = "Inactive"
    elif key == "directory":
        filters["status"] = filters.get("status") or "Active"
    listing = list_subcontractors_master(db, per_page=5000, **filters)
    items = listing["items"]
    if key == "trade_wise":
        trade = filters.get("trade_category") or ""
        if trade:
            items = [i for i in items if trade in (i.get("trade_categories_list") or [])]
        enriched: list[dict[str, Any]] = []
        for item in items:
            for t in item.get("trade_categories_list") or ["Unspecified"]:
                row = dict(item)
                row["report_trade"] = t
                enriched.append(row)
        return enriched
    if key == "project_wise" and _table_exists(db, "subcontract_work_orders"):
        rows = db.execute(
            """
            SELECT s.*, w.project_id, p.project_code, p.project_name, COUNT(w.id) AS work_order_count
            FROM subcontractors s
            INNER JOIN subcontract_work_orders w ON w.subcontractor_id=s.id
            LEFT JOIN projects p ON p.id=w.project_id
            WHERE COALESCE(s.is_deleted,0)=0
            GROUP BY s.id, w.project_id
            ORDER BY p.project_name, s.subcontractor_name
            """
        ).fetchall()
        return [dict(r) for r in rows]
    if key == "retention_summary":
        return sorted(items, key=lambda x: float(x.get("retention_percent") or 0), reverse=True)
    if key == "security_deposit_summary":
        return sorted(items, key=lambda x: float(x.get("security_deposit") or 0), reverse=True)
    return items


def subcontractor_import_template() -> BytesIO:
    from bulk_import_service import build_xlsx_template

    return build_xlsx_template(
        list(SUBCONTRACTOR_EXPORT_COLUMNS),
        [
            "SC101",
            "Sample Civil Contractors",
            "Sample Civil Contractors Pvt Ltd",
            "Civil Subcontractor",
            "Concrete,Brick Work",
            "Labour Supply",
            "22AAAAA0000A1Z5",
            "AAAAA0000A",
            "Site Manager",
            "9876543210",
            "sub@example.com",
            "9876543210",
            "Plot 5 Site Area",
            "Pune",
            "Maharashtra",
            "411001",
            "Net 30",
            "5",
            "100000",
            "POL-12345",
            "2027-12-31",
            "LL-MAH-001",
            "2026-12-31",
            "4",
            "",
            "Active",
            "Approved",
            "1",
            "0",
        ],
    )


def ai_validate_subcontractor(
    db,
    subcontractor_id: int | None = None,
    form: dict | None = None,
) -> dict[str, Any]:
    data = dict(form or {})
    if subcontractor_id and not form:
        row = get_subcontractor_master(db, subcontractor_id)
        if row:
            data = dict(row)
    issues: list[str] = []
    suggestions: list[str] = []
    duplicates: list[str] = []
    missing: list[str] = []
    code = (data.get("subcontractor_code") or "").strip()
    name = (data.get("subcontractor_name") or "").strip()
    gst = (data.get("gst_number") or data.get("gstin") or "").strip().upper()
    trades = data.get("trade_categories_list") or trade_categories_list(data)
    if not name:
        issues.append("Subcontractor name is required.")
        missing.append("subcontractor_name")
    if not trades:
        issues.append("At least one trade category is required.")
        missing.append("trade_categories")
    if code or gst:
        try:
            validate_subcontractor_uniqueness(
                db,
                subcontractor_code=code or "TEMP",
                gst_number=gst,
                subcontractor_id=subcontractor_id,
            )
        except ValueError as exc:
            duplicates.append(str(exc))
    if gst:
        try:
            validate_gst_number(gst)
        except ValueError as exc:
            issues.append(str(exc))
    elif name:
        suggestions.append("Add GST number for statutory compliance and duplicate detection.")
    pan = (data.get("pan_number") or data.get("pan") or "").strip()
    if pan:
        try:
            validate_pan_number(pan)
        except ValueError as exc:
            issues.append(str(exc))
    ll = (data.get("labour_license_no") or "").strip()
    if ll:
        try:
            validate_labour_license(ll)
        except ValueError as exc:
            issues.append(str(exc))
    else:
        suggestions.append("Labour license is recommended for on-site subcontract labour.")
    ins_exp = (data.get("insurance_expiry") or "").strip()
    ll_exp = (data.get("labour_license_expiry") or "").strip()
    today = _now_ts()[:10]
    if ins_exp and ins_exp < today:
        issues.append(f"Insurance expired on {ins_exp}.")
    if ll_exp and ll_exp < today:
        issues.append(f"Labour license expired on {ll_exp}.")
    if ins_exp and ins_exp >= today:
        suggestions.append(f"Insurance valid until {ins_exp}.")
    if not (data.get("phone") or data.get("contact_number") or "").strip():
        missing.append("phone")
        suggestions.append("Add contact phone for site coordination.")
    if subcontractor_id:
        similar = db.execute(
            """
            SELECT subcontractor_code, subcontractor_name, gst_number FROM subcontractors
            WHERE COALESCE(is_deleted,0)=0 AND id!=? AND (
                UPPER(subcontractor_name)=UPPER(?) OR
                (gst_number IS NOT NULL AND gst_number!='' AND UPPER(gst_number)=?)
            )
            LIMIT 5
            """,
            (subcontractor_id, name, gst),
        ).fetchall()
    elif name:
        similar = db.execute(
            """
            SELECT subcontractor_code, subcontractor_name, gst_number FROM subcontractors
            WHERE COALESCE(is_deleted,0)=0 AND (
                UPPER(subcontractor_name)=UPPER(?) OR
                (gst_number IS NOT NULL AND TRIM(gst_number)!='' AND UPPER(gst_number)=?)
            )
            LIMIT 5
            """,
            (name, gst),
        ).fetchall()
    else:
        similar = []
    for sim in similar:
        sc = sim[0] if isinstance(sim, tuple) else sim["subcontractor_code"]
        sn = sim[1] if isinstance(sim, tuple) else sim["subcontractor_name"]
        duplicates.append(f"Possible duplicate: {sc} — {sn}")
    result = {
        "ok": not issues and not duplicates,
        "issues": issues,
        "duplicates": duplicates,
        "suggestions": suggestions,
        "missing": missing,
    }
    try:
        from ai_service import chat_completion_json

        ai = chat_completion_json(
            "Validate ERP subcontractor records. Return JSON with keys: issues, suggestions.",
            json.dumps({"subcontractor": data, "rule_findings": result}, ensure_ascii=False),
            max_tokens=400,
        )
        for key in ("issues", "suggestions"):
            extra = ai.get(key) or []
            if isinstance(extra, list):
                result[key].extend(str(x) for x in extra if x)
        result["ok"] = not result["issues"] and not result["duplicates"]
        result["ai_enriched"] = True
    except Exception:
        result["ai_enriched"] = False
    return result


def list_vendors_for_subcontractor_form(db) -> list[dict[str, Any]]:
    if not _table_exists(db, "vendors"):
        return []
    rows = db.execute(
        """
        SELECT id, code, name, gstin, vendor_type, vendor_types, status
        FROM vendors WHERE COALESCE(is_deleted,0)=0 AND status='Active'
        ORDER BY name
        """
    ).fetchall()
    return [dict(r) for r in rows]
