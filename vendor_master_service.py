"""Vendor / Supplier Master (MODULE-012) — procurement vendor registry with contacts, addresses, banks."""

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
from store_service import (
    TRADE_CATEGORY_OPTIONS,
    VENDOR_TYPE_OPTIONS,
    encode_json_string_list,
    ensure_store_schema,
    generate_vendor_code,
    vendor_types_list,
)

VENDOR_STATUSES = ("Active", "Inactive")
APPROVAL_STATUSES = ("Draft", "Pending", "Approved", "Rejected")
ADDRESS_TYPES = ("Billing", "Office", "Site", "Warehouse", "Other")
PAYMENT_TERMS_OPTIONS = (
    "Immediate",
    "Net 7",
    "Net 15",
    "Net 30",
    "Net 45",
    "Net 60",
    "Advance",
    "Milestone",
    "Custom",
)
VENDOR_SORT_COLUMNS = (
    "code",
    "name",
    "gstin",
    "status",
    "rating",
    "created_at",
    "vendor_type",
)
VENDOR_EXPORT_COLUMNS = (
    "vendor_code",
    "vendor_name",
    "vendor_types",
    "trade_categories",
    "gstin",
    "pan",
    "msme_number",
    "cin_number",
    "contact_person",
    "phone",
    "email",
    "address",
    "city",
    "state",
    "pincode",
    "payment_terms",
    "credit_limit",
    "rating",
    "website",
    "status",
    "approval_status",
    "is_approved",
    "is_blacklisted",
)
VENDOR_AUDIT_FIELDS = (
    "code",
    "name",
    "gstin",
    "pan",
    "msme_number",
    "cin_number",
    "contact_person",
    "phone",
    "email",
    "address",
    "city",
    "state",
    "pincode",
    "vendor_type",
    "vendor_types",
    "trade_categories",
    "payment_terms",
    "credit_limit",
    "rating",
    "website",
    "status",
    "approval_status",
    "is_approved",
    "is_blacklisted",
    "remarks",
)
VENDOR_REFERENCE_TABLES = (
    ("purchase_orders", "vendor_id"),
    ("po_quotations", "vendor_id"),
    ("store_receipts", "vendor_id"),
    ("materials", "preferred_vendor_id"),
    ("subcontractors", "vendor_id"),
)


def ensure_vendor_master_schema(db) -> None:
    """Extend vendors and child tables for MODULE-012 (idempotent)."""
    ensure_store_schema(db)
    for col, ctype in (
        ("status", "TEXT DEFAULT 'Active'"),
        ("approval_status", "TEXT DEFAULT 'Draft'"),
        ("approved_by", "TEXT"),
        ("approved_at", "TEXT"),
        ("created_by", "TEXT"),
        ("modified_by", "TEXT"),
        ("is_deleted", "INTEGER DEFAULT 0"),
        ("deleted_by", "TEXT"),
        ("deleted_at", "TEXT"),
        ("customer_id", "INTEGER"),
        ("company_id", "INTEGER"),
        ("msme_number", "TEXT"),
        ("cin_number", "TEXT"),
        ("payment_terms", "TEXT"),
        ("credit_limit", "REAL DEFAULT 0"),
        ("rating", "REAL"),
        ("website", "TEXT"),
        ("remarks", "TEXT"),
        ("is_approved", "INTEGER DEFAULT 0"),
        ("is_blacklisted", "INTEGER DEFAULT 0"),
        ("classification", "TEXT"),
    ):
        _ensure_column(db, "vendors", col, ctype)

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS vendor_contacts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_id INTEGER NOT NULL,
            contact_name TEXT,
            designation TEXT,
            phone TEXT,
            email TEXT,
            is_primary INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(vendor_id) REFERENCES vendors(id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS vendor_addresses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_id INTEGER NOT NULL,
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
            FOREIGN KEY(vendor_id) REFERENCES vendors(id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS vendor_bank_accounts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_id INTEGER NOT NULL,
            account_holder TEXT,
            bank_name TEXT,
            account_number TEXT,
            ifsc_code TEXT,
            branch_name TEXT,
            is_primary INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(vendor_id) REFERENCES vendors(id)
        )
        """
    )
    _migrate_legacy_vendors(db)
    try:
        from audit_trail_service import ensure_audit_schema

        ensure_audit_schema(db)
    except Exception:
        pass


def _migrate_legacy_vendors(db) -> None:
    if not _table_exists(db, "vendors"):
        return
    db.execute(
        "UPDATE vendors SET status='Active' WHERE status IS NULL OR TRIM(status)=''"
    )
    db.execute(
        "UPDATE vendors SET status='Inactive' WHERE COALESCE(is_active,1)=0 AND status='Active'"
    )
    db.execute(
        "UPDATE vendors SET is_active=1 WHERE status='Active' AND COALESCE(is_active,1)=0"
    )
    db.execute(
        "UPDATE vendors SET approval_status='Approved' "
        "WHERE approval_status IS NULL OR TRIM(approval_status)=''"
    )
    db.execute(
        "UPDATE vendors SET is_approved=1 WHERE approval_status='Approved' AND COALESCE(is_approved,0)=0"
    )
    rows = db.execute(
        "SELECT id, contact_person, phone, email, address, city, state, pincode "
        "FROM vendors WHERE COALESCE(is_deleted,0)=0"
    ).fetchall()
    now = _now_ts()
    for row in rows:
        vid = int(row[0])
        has_contact = db.execute(
            "SELECT 1 FROM vendor_contacts WHERE vendor_id=? LIMIT 1", (vid,)
        ).fetchone()
        if not has_contact and (row[1] or row[2] or row[3]):
            db.execute(
                """
                INSERT INTO vendor_contacts(vendor_id, contact_name, phone, email, is_primary, created_at, modified_at)
                VALUES(?,?,?,?,1,?,?)
                """,
                (vid, row[1] or "", row[2] or "", row[3] or "", now, now),
            )
        has_addr = db.execute(
            "SELECT 1 FROM vendor_addresses WHERE vendor_id=? LIMIT 1", (vid,)
        ).fetchone()
        if not has_addr and (row[4] or row[5] or row[6] or row[7]):
            db.execute(
                """
                INSERT INTO vendor_addresses(
                    vendor_id, address_type, address_line1, city, state, pincode, is_primary, created_at, modified_at
                ) VALUES(?,?,?,?,?,?,1,?,?)
                """,
                (vid, "Office", row[4] or "", row[5] or "", row[6] or "", row[7] or "", now, now),
            )
        bank_row = db.execute(
            "SELECT bank_account, bank_name, ifsc_code, branch_name FROM vendors WHERE id=?", (vid,)
        ).fetchone()
        if bank_row:
            has_bank = db.execute(
                "SELECT 1 FROM vendor_bank_accounts WHERE vendor_id=? LIMIT 1", (vid,)
            ).fetchone()
            if not has_bank and (bank_row[0] or bank_row[1] or bank_row[2]):
                db.execute(
                    """
                    INSERT INTO vendor_bank_accounts(
                        vendor_id, account_holder, bank_name, account_number, ifsc_code, branch_name,
                        is_primary, created_at, modified_at
                    ) VALUES(?,?,?,?,?,?,1,?,?)
                    """,
                    (
                        vid,
                        row[1] or "",
                        bank_row[1] or "",
                        bank_row[0] or "",
                        bank_row[2] or "",
                        bank_row[3] or "",
                        now,
                        now,
                    ),
                )


def validate_vendor_uniqueness(
    db,
    *,
    vendor_code: str,
    gstin: str = "",
    vendor_id: int | None = None,
) -> None:
    code = (vendor_code or "").strip().upper()
    gst = (gstin or "").strip().upper()
    if not code:
        raise ValueError("Vendor code is required.")
    dup_code = db.execute(
        """
        SELECT id FROM vendors WHERE UPPER(TRIM(code))=? AND COALESCE(is_deleted,0)=0
        AND (? IS NULL OR id!=?)
        """,
        (code, vendor_id, vendor_id),
    ).fetchone()
    if dup_code:
        raise ValueError(f"Vendor code '{code}' already exists.")
    if gst:
        dup_gst = db.execute(
            """
            SELECT id, code FROM vendors WHERE UPPER(TRIM(gstin))=? AND COALESCE(is_deleted,0)=0
            AND (? IS NULL OR id!=?)
            """,
            (gst, vendor_id, vendor_id),
        ).fetchone()
        if dup_gst:
            raise ValueError(f"GSTIN '{gst}' is already registered to vendor {dup_gst[1]}.")


def vendor_has_transactions(db, vendor_id: int) -> bool:
    for table, column in VENDOR_REFERENCE_TABLES:
        if not _table_exists(db, table):
            continue
        if not _column_exists(db, table, column):
            continue
        hit = db.execute(
            f"SELECT 1 FROM {table} WHERE {column}=? LIMIT 1", (vendor_id,)
        ).fetchone()
        if hit:
            return True
    return False


def _column_exists(db, table: str, column: str) -> bool:
    if not _table_exists(db, table):
        return False
    cols = [r[1] for r in db.execute(f"PRAGMA table_info({table})").fetchall()]
    return column in cols


def log_vendor_audit(
    db,
    vendor_id: int,
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
            record_table="vendors",
            record_id=vendor_id,
            action=action,
            changed_by=username,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            remarks=remarks,
        )
    except Exception:
        pass


def log_vendor_field_changes(
    db,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    username: str,
) -> None:
    if not before or not after:
        return
    vid = int(after.get("id") or before.get("id") or 0)
    if not vid:
        return
    for field in VENDOR_AUDIT_FIELDS:
        old_val = before.get(field)
        new_val = after.get(field)
        if str(old_val or "") != str(new_val or ""):
            log_vendor_audit(
                db,
                vid,
                "update",
                username,
                field_name=field,
                old_value=str(old_val or ""),
                new_value=str(new_val or ""),
            )


def list_vendor_audit_trail(db, vendor_id: int, limit: int = 100) -> list[dict[str, Any]]:
    try:
        from audit_trail_service import list_audit_trail

        return list_audit_trail(db, "vendors", vendor_id, limit=limit)
    except Exception:
        return []


def _parse_vendor_types(form) -> list[str]:
    if hasattr(form, "getlist"):
        selected = form.getlist("vendor_types[]") or form.getlist("vendor_types")
    else:
        raw = form.get("vendor_types") or form.get("vendor_types[]") or []
        selected = raw if isinstance(raw, list) else [raw] if raw else []
    cleaned = [str(v).strip() for v in selected if str(v).strip() in VENDOR_TYPE_OPTIONS]
    if not cleaned and form.get("vendor_type"):
        vt = str(form.get("vendor_type")).strip()
        if vt in VENDOR_TYPE_OPTIONS:
            cleaned = [vt]
    return cleaned or ["Supplier"]


def _parse_trade_categories(form) -> list[str]:
    if hasattr(form, "getlist"):
        selected = form.getlist("trade_categories[]") or form.getlist("trade_categories")
    else:
        raw = form.get("trade_categories") or form.get("trade_categories[]") or []
        selected = raw if isinstance(raw, list) else [raw] if raw else []
    return [str(v).strip() for v in selected if str(v).strip() in TRADE_CATEGORY_OPTIONS]


def _parse_vendor_form(form) -> dict[str, Any]:
    code = (form.get("vendor_code") or form.get("code") or "").strip().upper()
    name = (form.get("vendor_name") or form.get("name") or "").strip()
    gstin = (form.get("gstin") or form.get("gst_number") or "").strip().upper()
    pan = (form.get("pan") or form.get("pan_number") or "").strip().upper()
    status = (form.get("status") or "Active").strip()
    payment_terms = (form.get("payment_terms") or "").strip()
    credit_raw = (form.get("credit_limit") or "0").strip()
    rating_raw = (form.get("rating") or "").strip()
    vendor_types = _parse_vendor_types(form)
    trade_categories = _parse_trade_categories(form)
    try:
        credit_limit = float(credit_raw) if credit_raw else 0.0
    except ValueError:
        credit_limit = 0.0
    try:
        rating = float(rating_raw) if rating_raw else None
    except ValueError:
        rating = None
    if rating is not None and (rating < 0 or rating > 5):
        raise ValueError("Rating must be between 0 and 5.")
    is_approved = 1 if str(form.get("is_approved", "")).lower() in ("1", "on", "true", "yes") else 0
    is_blacklisted = 1 if str(form.get("is_blacklisted", "")).lower() in ("1", "on", "true", "yes") else 0
    company_id_raw = form.get("company_id")
    company_id = int(company_id_raw) if company_id_raw and str(company_id_raw).isdigit() else None
    return {
        "code": code,
        "name": name,
        "gstin": gstin,
        "pan": pan,
        "msme_number": (form.get("msme_number") or "").strip(),
        "cin_number": (form.get("cin_number") or "").strip(),
        "contact_person": (form.get("contact_person") or "").strip(),
        "phone": (form.get("phone") or "").strip(),
        "email": (form.get("email") or "").strip(),
        "address": (form.get("address") or "").strip(),
        "city": (form.get("city") or "").strip(),
        "state": (form.get("state") or "").strip(),
        "pincode": (form.get("pincode") or "").strip(),
        "website": (form.get("website") or "").strip(),
        "remarks": (form.get("remarks") or "").strip(),
        "payment_terms": payment_terms,
        "credit_limit": credit_limit,
        "rating": rating,
        "status": status,
        "vendor_type": vendor_types[0],
        "vendor_types": encode_json_string_list(vendor_types),
        "trade_categories": encode_json_string_list(trade_categories),
        "classification": vendor_types[0],
        "is_approved": is_approved,
        "is_blacklisted": is_blacklisted,
        "company_id": company_id,
        "is_active": 1 if status == "Active" else 0,
    }


def _parse_child_rows(form, prefix: str, fields: tuple[str, ...]) -> list[dict[str, str]]:
    lists = {}
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


def _save_vendor_children(db, vendor_id: int, form) -> None:
    now = _now_ts()
    db.execute("DELETE FROM vendor_contacts WHERE vendor_id=?", (vendor_id,))
    db.execute("DELETE FROM vendor_addresses WHERE vendor_id=?", (vendor_id,))
    db.execute("DELETE FROM vendor_bank_accounts WHERE vendor_id=?", (vendor_id,))

    contacts = _parse_child_rows(
        form, "contact", ("name", "designation", "phone", "email", "primary")
    )
    if not contacts:
        cp = (form.get("contact_person") or "").strip()
        ph = (form.get("phone") or "").strip()
        em = (form.get("email") or "").strip()
        if cp or ph or em:
            contacts = [{"name": cp, "designation": "", "phone": ph, "email": em, "primary": "1"}]
    for idx, c in enumerate(contacts):
        is_primary = 1 if c.get("primary") in ("1", "on", "true") or idx == 0 else 0
        db.execute(
            """
            INSERT INTO vendor_contacts(
                vendor_id, contact_name, designation, phone, email, is_primary, created_at, modified_at
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                vendor_id,
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
            INSERT INTO vendor_addresses(
                vendor_id, address_type, address_line1, address_line2, city, state, pincode, country,
                is_primary, created_at, modified_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                vendor_id,
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
                    "holder": (form.get("contact_person") or form.get("name") or "").strip(),
                    "bank_name": bname,
                    "account_number": acct,
                    "ifsc": ifsc,
                    "branch": branch,
                    "primary": "1",
                }
            ]
    seen_accounts: set[str] = set()
    for idx, b in enumerate(banks):
        acct_no = b.get("account_number", "")
        if acct_no:
            key = f"{acct_no}|{b.get('ifsc', '').upper()}"
            if key in seen_accounts:
                continue
            seen_accounts.add(key)
        is_primary = 1 if b.get("primary") in ("1", "on", "true") or idx == 0 else 0
        db.execute(
            """
            INSERT INTO vendor_bank_accounts(
                vendor_id, account_holder, bank_name, account_number, ifsc_code, branch_name,
                is_primary, created_at, modified_at
            ) VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (
                vendor_id,
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
                "UPDATE vendors SET bank_account=?, bank_name=?, ifsc_code=?, branch_name=? WHERE id=?",
                (acct_no, b.get("bank_name", ""), (b.get("ifsc") or "").upper(), b.get("branch", ""), vendor_id),
            )


def _sync_primary_fields_from_children(db, vendor_id: int) -> None:
    contact = db.execute(
        "SELECT contact_name, phone, email FROM vendor_contacts WHERE vendor_id=? "
        "ORDER BY is_primary DESC, id LIMIT 1",
        (vendor_id,),
    ).fetchone()
    addr = db.execute(
        "SELECT address_line1, city, state, pincode FROM vendor_addresses WHERE vendor_id=? "
        "ORDER BY is_primary DESC, id LIMIT 1",
        (vendor_id,),
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
        params.append(vendor_id)
        db.execute(f"UPDATE vendors SET {', '.join(sets)} WHERE id=?", params)


def save_vendor_master(
    db,
    form,
    username: str,
    vendor_id: int | None = None,
    *,
    customer_id: int | None = None,
) -> int:
    data = _parse_vendor_form(form)
    if not data["name"]:
        raise ValueError("Vendor name is required.")
    if not vendor_id and not data["code"]:
        data["code"] = generate_vendor_code(db)
    if data["status"] not in VENDOR_STATUSES:
        raise ValueError("Select a valid status.")
    if data["payment_terms"] and data["payment_terms"] not in PAYMENT_TERMS_OPTIONS:
        raise ValueError("Select a valid payment term.")
    if data["email"]:
        validate_email(data["email"])
    if data["phone"]:
        validate_phone(data["phone"])
    if data["gstin"]:
        validate_gst_number(data["gstin"])
    if data["pan"]:
        validate_pan_number(data["pan"])
    validate_vendor_uniqueness(db, vendor_code=data["code"], gstin=data["gstin"], vendor_id=vendor_id)
    if data["is_blacklisted"] and data["status"] == "Active" and not vendor_id:
        data["status"] = "Inactive"
        data["is_active"] = 0

    now = _now_ts()
    core = (
        data["code"],
        data["name"],
        data["gstin"],
        data["pan"],
        data["contact_person"],
        data["phone"],
        data["email"],
        data["address"],
        data["city"],
        data["state"],
        data["pincode"],
        data["is_active"],
        data["vendor_type"],
        data["vendor_types"],
        data["trade_categories"],
        data["msme_number"],
        data["cin_number"],
        data["payment_terms"],
        data["credit_limit"],
        data["rating"],
        data["website"],
        data["remarks"],
        data["status"],
        data["classification"],
        data["is_approved"],
        data["is_blacklisted"],
        data["company_id"],
    )
    if vendor_id:
        existing = get_vendor_master(db, vendor_id, include_deleted=True)
        if not existing:
            raise ValueError("Vendor not found.")
        db.execute(
            """
            UPDATE vendors SET code=?, name=?, gstin=?, pan=?, contact_person=?, phone=?, email=?,
            address=?, city=?, state=?, pincode=?, is_active=?, vendor_type=?, vendor_types=?,
            trade_categories=?, msme_number=?, cin_number=?, payment_terms=?, credit_limit=?, rating=?,
            website=?, remarks=?, status=?, classification=?, is_approved=?, is_blacklisted=?, company_id=?,
            modified_by=?, modified_at=? WHERE id=?
            """,
            (*core, username, now, vendor_id),
        )
        if customer_id is not None:
            db.execute("UPDATE vendors SET customer_id=? WHERE id=?", (customer_id, vendor_id))
        _save_vendor_children(db, vendor_id, form)
        _sync_primary_fields_from_children(db, vendor_id)
        log_vendor_field_changes(db, existing, get_vendor_master(db, vendor_id, include_deleted=True), username)
        return vendor_id

    approval_status = (form.get("approval_status") or "Draft").strip()
    if approval_status not in APPROVAL_STATUSES:
        approval_status = "Draft"
    cur = db.execute(
        """
        INSERT INTO vendors(
            code, name, gstin, pan, contact_person, phone, email, address, city, state, pincode,
            is_active, vendor_type, vendor_types, trade_categories, msme_number, cin_number,
            payment_terms, credit_limit, rating, website, remarks, status, classification,
            is_approved, is_blacklisted, company_id, approval_status, created_by, created_at,
            modified_by, modified_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (*core, approval_status, username, now, username, now),
    )
    new_id = int(cur.lastrowid)
    if customer_id is not None:
        db.execute("UPDATE vendors SET customer_id=? WHERE id=?", (customer_id, new_id))
    _save_vendor_children(db, new_id, form)
    _sync_primary_fields_from_children(db, new_id)
    log_vendor_audit(db, new_id, "create", username, remarks=f"Created vendor {data['code']}")
    return new_id


def _vendor_row_to_dict(row) -> dict[str, Any]:
    data = dict(row)
    data["vendor_code"] = data.get("code")
    data["vendor_name"] = data.get("name")
    data["vendor_types_list"] = vendor_types_list(data)
    return data


def _load_vendor_children(db, vendor_id: int) -> dict[str, list[dict[str, Any]]]:
    contacts = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM vendor_contacts WHERE vendor_id=? ORDER BY is_primary DESC, id",
            (vendor_id,),
        ).fetchall()
    ]
    addresses = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM vendor_addresses WHERE vendor_id=? ORDER BY is_primary DESC, id",
            (vendor_id,),
        ).fetchall()
    ]
    banks = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM vendor_bank_accounts WHERE vendor_id=? ORDER BY is_primary DESC, id",
            (vendor_id,),
        ).fetchall()
    ]
    return {"contacts": contacts, "addresses": addresses, "bank_accounts": banks}


def get_vendor_master(db, vendor_id: int, *, include_deleted: bool = False) -> dict[str, Any] | None:
    sql = "SELECT * FROM vendors WHERE id=?"
    if not include_deleted:
        sql += " AND COALESCE(is_deleted,0)=0"
    row = db.execute(sql, (vendor_id,)).fetchone()
    if not row:
        return None
    data = _vendor_row_to_dict(row)
    children = _load_vendor_children(db, vendor_id)
    data.update(children)
    try:
        from document_management_service import list_module_documents

        data["documents"] = list_module_documents(db, "vendor_master", vendor_id)
    except Exception:
        data["documents"] = []
    return data


def list_vendors_master(
    db,
    *,
    search: str = "",
    status: str = "",
    vendor_type: str = "",
    approval_status: str = "",
    is_blacklisted: bool | None = None,
    is_approved: bool | None = None,
    include_deleted: bool = False,
    page: int = 1,
    per_page: int = 25,
    sort_by: str = "name",
    sort_dir: str = "asc",
) -> dict[str, Any]:
    if not _table_exists(db, "vendors"):
        return {"items": [], "total": 0, "page": 1, "per_page": per_page, "pages": 0}
    sql = "SELECT * FROM vendors WHERE 1=1"
    count_sql = "SELECT COUNT(*) FROM vendors WHERE 1=1"
    params: list[Any] = []
    if not include_deleted:
        sql += " AND COALESCE(is_deleted,0)=0"
        count_sql += " AND COALESCE(is_deleted,0)=0"
    if status:
        sql += " AND status=?"
        count_sql += " AND status=?"
        params.append(status)
    if vendor_type:
        sql += " AND (vendor_type=? OR vendor_types LIKE ?)"
        count_sql += " AND (vendor_type=? OR vendor_types LIKE ?)"
        params.extend([vendor_type, f'%"{vendor_type}"%'])
    if approval_status:
        sql += " AND approval_status=?"
        count_sql += " AND approval_status=?"
        params.append(approval_status)
    if is_blacklisted is True:
        sql += " AND COALESCE(is_blacklisted,0)=1"
        count_sql += " AND COALESCE(is_blacklisted,0)=1"
    elif is_blacklisted is False:
        sql += " AND COALESCE(is_blacklisted,0)=0"
        count_sql += " AND COALESCE(is_blacklisted,0)=0"
    if is_approved is True:
        sql += " AND COALESCE(is_approved,0)=1"
        count_sql += " AND COALESCE(is_approved,0)=1"
    elif is_approved is False:
        sql += " AND COALESCE(is_approved,0)=0"
        count_sql += " AND COALESCE(is_approved,0)=0"
    if search:
        clause = (
            " AND (name LIKE ? OR code LIKE ? OR gstin LIKE ? OR pan LIKE ? "
            "OR contact_person LIKE ? OR phone LIKE ? OR email LIKE ? OR city LIKE ?)"
        )
        sql += clause
        count_sql += clause
        like = f"%{search}%"
        params.extend([like] * 8)
    sort_col = sort_by if sort_by in VENDOR_SORT_COLUMNS else "name"
    direction = "DESC" if str(sort_dir).lower() == "desc" else "ASC"
    sql += f" ORDER BY {sort_col} {direction}, id DESC"
    per_page = max(1, min(int(per_page or 25), 10000))
    page = max(1, int(page or 1))
    offset = (page - 1) * per_page
    sql += " LIMIT ? OFFSET ?"
    total = int(db.execute(count_sql, params).fetchone()[0])
    rows = db.execute(sql, [*params, per_page, offset]).fetchall()
    items = [_vendor_row_to_dict(r) for r in rows]
    pages = (total + per_page - 1) // per_page if total else 0
    return {"items": items, "total": total, "page": page, "per_page": per_page, "pages": pages}


def soft_delete_vendor_master(db, vendor_id: int, username: str) -> None:
    if not vendor_id:
        raise ValueError("Invalid vendor.")
    row = get_vendor_master(db, vendor_id, include_deleted=True)
    if not row:
        raise ValueError("Vendor not found.")
    if row.get("is_deleted"):
        return
    if vendor_has_transactions(db, vendor_id):
        raise ValueError("Vendor cannot be deleted because purchase or store transactions exist. Deactivate instead.")
    now = _now_ts()
    db.execute(
        """
        UPDATE vendors SET is_deleted=1, deleted_by=?, deleted_at=?, modified_by=?, modified_at=?,
        status='Inactive', is_active=0 WHERE id=?
        """,
        (username, now, username, now, vendor_id),
    )
    log_vendor_audit(db, vendor_id, "soft_delete", username, remarks=f"Soft-deleted vendor {row.get('code')}")


def activate_vendor_master(db, vendor_id: int, username: str) -> None:
    if not get_vendor_master(db, vendor_id):
        raise ValueError("Vendor not found.")
    row = db.execute("SELECT is_blacklisted FROM vendors WHERE id=?", (vendor_id,)).fetchone()
    if row and int(row[0] or 0):
        raise ValueError("Blacklisted vendors cannot be activated until blacklist is cleared.")
    now = _now_ts()
    db.execute(
        "UPDATE vendors SET status='Active', is_active=1, modified_by=?, modified_at=? WHERE id=?",
        (username, now, vendor_id),
    )
    log_vendor_audit(
        db, vendor_id, "activate", username, field_name="status", old_value="Inactive", new_value="Active"
    )


def deactivate_vendor_master(db, vendor_id: int, username: str) -> None:
    if not get_vendor_master(db, vendor_id):
        raise ValueError("Vendor not found.")
    now = _now_ts()
    db.execute(
        "UPDATE vendors SET status='Inactive', is_active=0, modified_by=?, modified_at=? WHERE id=?",
        (username, now, vendor_id),
    )
    log_vendor_audit(
        db, vendor_id, "deactivate", username, field_name="status", old_value="Active", new_value="Inactive"
    )


def approve_vendor_master(db, vendor_id: int, username: str) -> None:
    if not get_vendor_master(db, vendor_id):
        raise ValueError("Vendor not found.")
    now = _now_ts()
    db.execute(
        """
        UPDATE vendors SET approval_status='Approved', is_approved=1, approved_by=?, approved_at=?,
        modified_by=?, modified_at=? WHERE id=?
        """,
        (username, now, username, now, vendor_id),
    )
    log_vendor_audit(db, vendor_id, "approve", username, remarks="Vendor approved")


def reject_vendor_master(db, vendor_id: int, username: str, remarks: str = "") -> None:
    if not get_vendor_master(db, vendor_id):
        raise ValueError("Vendor not found.")
    now = _now_ts()
    db.execute(
        "UPDATE vendors SET approval_status='Rejected', is_approved=0, modified_by=?, modified_at=? WHERE id=?",
        (username, now, vendor_id),
    )
    log_vendor_audit(db, vendor_id, "reject", username, remarks=remarks or "Vendor rejected")


def user_can_vendor_master(
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
        from user_permission_service import (
            empty_permission_actions,
            ensure_user_tab_permissions_schema,
            normalize_permission_actions,
        )

        ensure_user_tab_permissions_schema(db)
        row = db.execute(
            """
            SELECT granted, action_flags FROM user_tab_permissions
            WHERE user_id=? AND granted=1 AND endpoint='vendor_master'
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


def vendors_for_export(db, *, include_deleted: bool = False, **filters) -> list[dict[str, Any]]:
    listing = list_vendors_master(db, include_deleted=include_deleted, per_page=10000, **filters)
    rows: list[dict[str, Any]] = []
    for item in listing["items"]:
        row = {col: item.get(col.replace("vendor_", "") if col.startswith("vendor_") else col, "") for col in VENDOR_EXPORT_COLUMNS}
        row["vendor_code"] = item.get("code") or item.get("vendor_code")
        row["vendor_name"] = item.get("name") or item.get("vendor_name")
        row["vendor_types"] = ", ".join(item.get("vendor_types_list") or [])
        try:
            tc = json.loads(item.get("trade_categories") or "[]")
            row["trade_categories"] = ", ".join(tc) if isinstance(tc, list) else str(tc)
        except (json.JSONDecodeError, TypeError):
            row["trade_categories"] = item.get("trade_categories") or ""
        rows.append({col: row.get(col, "") for col in VENDOR_EXPORT_COLUMNS})
    return rows


def export_vendors_excel(db, **filters) -> BytesIO:
    from openpyxl import Workbook

    rows = vendors_for_export(db, **filters)
    wb = Workbook()
    ws = wb.active
    ws.title = "Vendors"
    headers = list(VENDOR_EXPORT_COLUMNS)
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h, "") for h in headers])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def export_vendors_csv(db, **filters) -> str:
    rows = vendors_for_export(db, **filters)
    si = io.StringIO()
    writer = csv.writer(si)
    headers = list(VENDOR_EXPORT_COLUMNS)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row.get(h, "") for h in headers])
    return si.getvalue()


def export_vendors_pdf(db, *, report_title: str = "Vendor Master Report", **filters) -> BytesIO:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas

    rows = vendors_for_export(db, **filters)
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
            f"{row.get('vendor_code')} | {row.get('vendor_name')} | {row.get('gstin') or '—'} | "
            f"{row.get('status')} | Rating: {row.get('rating') or '—'}"
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


def vendor_report(db, report_key: str, **filters) -> list[dict[str, Any]]:
    key = (report_key or "list").lower().strip()
    if key == "active":
        filters["status"] = "Active"
    elif key == "inactive":
        filters["status"] = "Inactive"
    elif key in ("directory", "contact"):
        filters["status"] = "Active"
    elif key == "rating":
        listing = list_vendors_master(db, per_page=5000, **filters)
        return sorted(
            listing["items"],
            key=lambda x: float(x.get("rating") or 0),
            reverse=True,
        )
    listing = list_vendors_master(db, per_page=5000, **filters)
    if key == "contact":
        enriched = []
        for item in listing["items"]:
            children = _load_vendor_children(db, int(item["id"]))
            item = dict(item)
            item["contacts"] = children["contacts"]
            enriched.append(item)
        return enriched
    return listing["items"]


def vendor_import_template() -> BytesIO:
    from bulk_import_service import build_xlsx_template

    return build_xlsx_template(
        list(VENDOR_EXPORT_COLUMNS),
        [
            "VEN101",
            "Sample Supplier Pvt Ltd",
            "Supplier",
            "Civil",
            "22AAAAA0000A1Z5",
            "AAAAA0000A",
            "UDYAM-XX-00-0000000",
            "",
            "Contact Person",
            "9876543210",
            "vendor@example.com",
            "123 Industrial Area",
            "Mumbai",
            "Maharashtra",
            "400001",
            "Net 30",
            "500000",
            "4",
            "https://example.com",
            "Active",
            "Approved",
            "1",
            "0",
        ],
    )


def ai_validate_vendor(
    db,
    vendor_id: int | None = None,
    form: dict | None = None,
) -> dict[str, Any]:
    data = dict(form or {})
    if vendor_id and not form:
        row = get_vendor_master(db, vendor_id)
        if row:
            data = dict(row)
    issues: list[str] = []
    suggestions: list[str] = []
    duplicates: list[str] = []
    missing: list[str] = []
    code = (data.get("vendor_code") or data.get("code") or "").strip()
    name = (data.get("vendor_name") or data.get("name") or "").strip()
    gstin = (data.get("gstin") or "").strip().upper()
    if not name:
        issues.append("Vendor name is required.")
        missing.append("name")
    if not code and not vendor_id:
        suggestions.append("Vendor code will be auto-generated if left blank.")
    else:
        try:
            validate_vendor_uniqueness(db, vendor_code=code or "TEMP", gstin=gstin, vendor_id=vendor_id)
        except ValueError as exc:
            duplicates.append(str(exc))
    if gstin:
        try:
            validate_gst_number(gstin)
        except ValueError as exc:
            issues.append(str(exc))
    elif name:
        suggestions.append("Add GSTIN for statutory compliance and duplicate detection.")
    pan = (data.get("pan") or "").strip()
    if pan:
        try:
            validate_pan_number(pan)
        except ValueError as exc:
            issues.append(str(exc))
    else:
        suggestions.append("PAN is recommended for TDS and payment processing.")
    if not (data.get("phone") or "").strip():
        missing.append("phone")
        suggestions.append("Add at least one contact phone number.")
    if not (data.get("email") or "").strip():
        suggestions.append("Add vendor email for PO and payment communication.")
    if not (data.get("payment_terms") or "").strip():
        suggestions.append("Define payment terms for procurement workflows.")
    banks: list[dict[str, Any]] = data.get("bank_accounts") or []
    if isinstance(data.get("bank_account"), str) and data.get("bank_account"):
        banks = [{"account_number": data.get("bank_account"), "ifsc_code": data.get("ifsc_code")}]
    seen: set[str] = set()
    for bank in banks:
        acct = str(bank.get("account_number") or bank.get("bank_account") or "").strip()
        ifsc = str(bank.get("ifsc_code") or bank.get("ifsc") or "").strip().upper()
        if not acct:
            continue
        key = f"{acct}|{ifsc}"
        if key in seen:
            duplicates.append(f"Duplicate bank account {acct} detected.")
        seen.add(key)
    if vendor_id:
        similar = db.execute(
            """
            SELECT code, name, gstin FROM vendors
            WHERE COALESCE(is_deleted,0)=0 AND id!=? AND (
                UPPER(name)=UPPER(?) OR (gstin IS NOT NULL AND gstin!='' AND UPPER(gstin)=?)
            )
            LIMIT 5
            """,
            (vendor_id, name, gstin),
        ).fetchall()
    elif name:
        if gstin:
            similar = db.execute(
                """
                SELECT code, name, gstin FROM vendors
                WHERE COALESCE(is_deleted,0)=0 AND (
                    UPPER(name)=UPPER(?) OR (gstin IS NOT NULL AND TRIM(gstin)!='' AND UPPER(gstin)=?)
                )
                LIMIT 5
                """,
                (name, gstin),
            ).fetchall()
        else:
            similar = db.execute(
                """
                SELECT code, name, gstin FROM vendors
                WHERE COALESCE(is_deleted,0)=0 AND UPPER(name)=UPPER(?)
                LIMIT 5
                """,
                (name,),
            ).fetchall()
    else:
        similar = []
    for sim in similar:
        duplicates.append(f"Possible duplicate: {sim[0]} — {sim[1]}")
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
            "Validate ERP vendor/supplier records. Return JSON with keys: issues, suggestions.",
            json.dumps({"vendor": data, "rule_findings": result}, ensure_ascii=False),
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
