"""Store & Procurement — materials, vendors, PO, GRN, stock ledger."""

from __future__ import annotations

import json
import re
from datetime import datetime
from io import BytesIO
from typing import Any

from accounts_service import GST_RATES, TAX_TYPES, _safe_float, calc_gst_line

MATERIAL_CATEGORIES = (
    "Civil",
    "Steel",
    "Electrical",
    "Plumbing",
    "Finishing",
    "Consumables",
    "Equipment",
    "Other",
)
MATERIAL_UNITS = ("Nos", "Sqm", "Sqft", "Rmt", "Kg", "MT", "Ltr", "Cum", "Bag", "Set", "LS")
VENDOR_DOC_TYPES = (
    "GST Certificate",
    "PAN Card",
    "Aadhaar Card",
    "Bank Proof",
    "MSME",
    "Agreement",
    "Other",
)
VENDOR_TYPE_OPTIONS = (
    "Supplier",
    "Subcontractor",
    "Supplier + Subcontractor",
    "Labour Contractor",
    "Equipment Provider",
    "Transporter",
)
SUBCONTRACT_ELIGIBLE_VENDOR_TYPES = frozenset(
    {"Subcontractor", "Labour Contractor", "Supplier + Subcontractor"}
)
TRADE_CATEGORY_OPTIONS = (
    "Excavation",
    "PCC",
    "Reinforcement",
    "Shuttering",
    "Concrete",
    "Brick Work",
    "Plastering",
    "Painting",
    "Flooring",
    "Waterproofing",
    "Asphalt",
    "WMM",
    "GSB",
    "Bridge Work",
)
# Legacy alias — prefer VENDOR_TYPE_OPTIONS
VENDOR_TYPES = VENDOR_TYPE_OPTIONS
MOVEMENT_GRN_IN = "GRN_IN"
MOVEMENT_ISSUE_OUT = "ISSUE_OUT"
MOVEMENT_ADJUSTMENT = "ADJUSTMENT"
MOVEMENT_TRANSFER_OUT = "TRANSFER_OUT"
MOVEMENT_TRANSFER_IN = "TRANSFER_IN"

MATERIAL_TRANSFER_TYPES = (
    ("store_to_store", "Store-to-Store"),
    ("store_to_site", "Store-to-Site"),
    ("site_to_site", "Site-to-Site"),
)

MATERIAL_IMPORT_COLUMNS = [
    "code",
    "name",
    "category",
    "unit",
    "hsn_code",
    "gst_percent",
    "reorder_level",
    "min_stock",
    "max_stock",
]


def _table_exists(db, table: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _column_exists(db, table: str, column: str) -> bool:
    if not _table_exists(db, table):
        return False
    cols = [row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()]
    return column in cols


def _safe_scalar(db, sql: str, params: tuple = (), default: int | float = 0) -> int | float:
    try:
        row = db.execute(sql, params).fetchone()
        if not row:
            return default
        val = row[0] if isinstance(row, tuple) else row["c"]
        return int(val) if isinstance(default, int) else float(val)
    except Exception:
        return default


def _active_count(db, table: str) -> int:
    if not _table_exists(db, table):
        return 0
    if _column_exists(db, table, "is_active"):
        return int(_safe_scalar(db, f"SELECT COUNT(*) AS c FROM {table} WHERE is_active=1", default=0))
    return int(_safe_scalar(db, f"SELECT COUNT(*) AS c FROM {table}", default=0))


def _pending_approval_count(db, table: str) -> int:
    try:
        if not _table_exists(db, table) or not _column_exists(db, table, "approval_status"):
            return 0
        return int(
            _safe_scalar(
                db,
                f"SELECT COUNT(*) AS c FROM {table} WHERE approval_status != 'Approved'",
                default=0,
            )
        )
    except Exception:
        return 0


def _empty_store_dashboard_stats() -> dict[str, Any]:
    return {
        "materials": 0,
        "vendors": 0,
        "pending_material_requests": 0,
        "pending_purchase_requests": 0,
        "pending_purchase_orders": 0,
        "pending_grn": 0,
        "low_stock_count": 0,
        "low_stock_items": [],
        "stock_items": 0,
        "approx_stock_value": 0.0,
    }


def _ensure_column(db, table: str, column: str, col_type: str) -> None:
    if not _table_exists(db, table):
        return
    cols = [row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def generate_vendor_code(db) -> str:
    """Next vendor code in VEN101, VEN102, … sequence (matches CLT/EMP pattern)."""
    rows = db.execute("SELECT code FROM vendors").fetchall()
    max_code = 100
    for row in rows:
        code = str(row["code"] or "").strip().upper()
        match = re.match(r"^VEN-?(\d+)$", code)
        if match:
            max_code = max(max_code, int(match.group(1)))
    return f"VEN{max_code + 1}"


def _backfill_missing_vendor_codes(db) -> None:
    """Assign VEN codes to any legacy rows missing a code."""
    if not _table_exists(db, "vendors"):
        return
    rows = db.execute(
        "SELECT id FROM vendors WHERE code IS NULL OR TRIM(code) = '' ORDER BY id"
    ).fetchall()
    for row in rows:
        code = generate_vendor_code(db)
        db.execute("UPDATE vendors SET code=? WHERE id=?", (code, row["id"]))


def _next_doc_number(db, prefix: str, table: str, column: str) -> str:
    today = datetime.now().strftime("%Y%m%d")
    base = f"{prefix}-{today}-"
    row = db.execute(
        f"SELECT {column} FROM {table} WHERE {column} LIKE ? ORDER BY id DESC LIMIT 1",
        (f"{base}%",),
    ).fetchone()
    seq = 1
    if row and row[0]:
        m = re.search(r"-(\d+)$", str(row[0]))
        if m:
            seq = int(m.group(1)) + 1
    return f"{base}{seq:03d}"


def ensure_store_schema(db) -> None:
    """Idempotent store & procurement schema."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS vendors(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            gstin TEXT,
            pan TEXT,
            contact_person TEXT,
            phone TEXT,
            email TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            pincode TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT,
            modified_at TEXT
        )
    """)
    for column, col_type in (
        ("code", "TEXT"),
        ("name", "TEXT"),
        ("gstin", "TEXT"),
        ("pan", "TEXT"),
        ("contact_person", "TEXT"),
        ("phone", "TEXT"),
        ("email", "TEXT"),
        ("address", "TEXT"),
        ("city", "TEXT"),
        ("state", "TEXT"),
        ("pincode", "TEXT"),
        ("is_active", "INTEGER DEFAULT 1"),
        ("created_at", "TEXT"),
        ("modified_at", "TEXT"),
        ("vendor_type", "TEXT DEFAULT 'Vendor'"),
        ("subcontractor_id", "INTEGER"),
        ("photo", "TEXT"),
        ("gender", "TEXT"),
        ("date_of_birth", "TEXT"),
        ("bank_account", "TEXT"),
        ("bank_name", "TEXT"),
        ("ifsc_code", "TEXT"),
        ("branch_name", "TEXT"),
        ("aadhaar_number", "TEXT"),
        ("pan_document", "TEXT"),
        ("aadhaar_document", "TEXT"),
        ("gst_document", "TEXT"),
        ("bank_proof_document", "TEXT"),
        ("vendor_types", "TEXT"),
        ("trade_categories", "TEXT"),
    ):
        _ensure_column(db, "vendors", column, col_type)

    _migrate_vendor_type_fields(db)

    db.execute("""
        CREATE TABLE IF NOT EXISTS materials(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT,
            unit TEXT,
            hsn_code TEXT,
            gst_percent REAL DEFAULT 0,
            reorder_level REAL DEFAULT 0,
            min_stock REAL DEFAULT 0,
            max_stock REAL DEFAULT 0,
            preferred_vendor_id INTEGER,
            is_active INTEGER DEFAULT 1,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(preferred_vendor_id) REFERENCES vendors(id)
        )
    """)
    for column, col_type in (
        ("code", "TEXT"),
        ("name", "TEXT"),
        ("category", "TEXT"),
        ("unit", "TEXT"),
        ("hsn_code", "TEXT"),
        ("gst_percent", "REAL DEFAULT 0"),
        ("reorder_level", "REAL DEFAULT 0"),
        ("min_stock", "REAL DEFAULT 0"),
        ("max_stock", "REAL DEFAULT 0"),
        ("preferred_vendor_id", "INTEGER"),
        ("is_active", "INTEGER DEFAULT 1"),
        ("created_at", "TEXT"),
        ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "materials", column, col_type)

    db.execute("""
        CREATE TABLE IF NOT EXISTS vendor_documents(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            doc_type TEXT,
            uploaded_by TEXT,
            uploaded_at TEXT,
            FOREIGN KEY(vendor_id) REFERENCES vendors(id)
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS stock_ledger(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id INTEGER NOT NULL,
            project_id INTEGER,
            movement_date TEXT,
            movement_type TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit TEXT,
            reference_table TEXT,
            reference_id INTEGER,
            reference_line_id INTEGER,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            FOREIGN KEY(material_id) REFERENCES materials(id),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_stock_ledger_material ON stock_ledger(material_id)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_stock_ledger_ref ON stock_ledger(reference_table, reference_id)"
    )

    db.execute("""
        CREATE TABLE IF NOT EXISTS purchase_orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_number TEXT UNIQUE NOT NULL,
            vendor_id INTEGER,
            project_id INTEGER,
            order_date TEXT,
            delivery_date TEXT,
            terms TEXT,
            subtotal REAL DEFAULT 0,
            total_cgst REAL DEFAULT 0,
            total_sgst REAL DEFAULT 0,
            total_igst REAL DEFAULT 0,
            grand_total REAL DEFAULT 0,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(vendor_id) REFERENCES vendors(id),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    for column, col_type in (
        ("po_number", "TEXT"),
        ("vendor_id", "INTEGER"),
        ("project_id", "INTEGER"),
        ("order_date", "TEXT"),
        ("delivery_date", "TEXT"),
        ("terms", "TEXT"),
        ("subtotal", "REAL DEFAULT 0"),
        ("total_cgst", "REAL DEFAULT 0"),
        ("total_sgst", "REAL DEFAULT 0"),
        ("total_igst", "REAL DEFAULT 0"),
        ("grand_total", "REAL DEFAULT 0"),
        ("remarks", "TEXT"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT"),
        ("modified_at", "TEXT"),
        ("approval_status", "TEXT DEFAULT 'Pending Checker'"),
    ):
        _ensure_column(db, "purchase_orders", column, col_type)

    db.execute("""
        CREATE TABLE IF NOT EXISTS purchase_order_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_order_id INTEGER NOT NULL,
            line_no INTEGER DEFAULT 1,
            material_id INTEGER,
            description TEXT,
            quantity REAL DEFAULT 0,
            unit TEXT,
            rate REAL DEFAULT 0,
            gst_percent REAL DEFAULT 0,
            tax_type TEXT DEFAULT 'CGST_SGST',
            taxable_value REAL DEFAULT 0,
            cgst REAL DEFAULT 0,
            sgst REAL DEFAULT 0,
            igst REAL DEFAULT 0,
            line_total REAL DEFAULT 0,
            FOREIGN KEY(purchase_order_id) REFERENCES purchase_orders(id),
            FOREIGN KEY(material_id) REFERENCES materials(id)
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS material_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            request_date TEXT,
            material_id INTEGER,
            item_name TEXT,
            quantity REAL,
            unit TEXT,
            remarks TEXT,
            created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    for column, col_type in (
        ("project_id", "INTEGER"),
        ("request_date", "TEXT"),
        ("material_id", "INTEGER"),
        ("item_name", "TEXT"),
        ("quantity", "REAL"),
        ("unit", "TEXT"),
        ("remarks", "TEXT"),
        ("created_by", "TEXT"),
        ("approval_status", "TEXT DEFAULT 'Pending Checker'"),
    ):
        _ensure_column(db, "material_requests", column, col_type)

    db.execute("""
        CREATE TABLE IF NOT EXISTS store_receipts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            receipt_date TEXT,
            item_name TEXT,
            quantity REAL,
            unit TEXT,
            supplier TEXT,
            remarks TEXT,
            created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    for column, col_type in (
        ("grn_number", "TEXT"),
        ("vendor_id", "INTEGER"),
        ("purchase_order_id", "INTEGER"),
        ("material_id", "INTEGER"),
        ("total_amount", "REAL DEFAULT 0"),
        ("stock_posted", "INTEGER DEFAULT 0"),
        ("invoice_ref", "TEXT"),
        ("approval_status", "TEXT DEFAULT 'Pending Checker'"),
    ):
        _ensure_column(db, "store_receipts", column, col_type)

    for column, col_type in (
        ("material_id", "INTEGER"),
        ("stock_posted", "INTEGER DEFAULT 0"),
        ("approval_status", "TEXT DEFAULT 'Pending Checker'"),
    ):
        _ensure_column(db, "store_issues", column, col_type)

    db.execute("""
        CREATE TABLE IF NOT EXISTS store_receipt_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_receipt_id INTEGER NOT NULL,
            line_no INTEGER DEFAULT 1,
            material_id INTEGER,
            description TEXT,
            quantity REAL DEFAULT 0,
            unit TEXT,
            rate REAL DEFAULT 0,
            remarks TEXT,
            FOREIGN KEY(store_receipt_id) REFERENCES store_receipts(id),
            FOREIGN KEY(material_id) REFERENCES materials(id)
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS material_transfers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transfer_number TEXT UNIQUE,
            transfer_type TEXT NOT NULL,
            transfer_date TEXT,
            source_project_id INTEGER,
            dest_project_id INTEGER,
            remarks TEXT,
            created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            stock_posted INTEGER DEFAULT 0,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(source_project_id) REFERENCES projects(id),
            FOREIGN KEY(dest_project_id) REFERENCES projects(id)
        )
    """)
    for column, col_type in (
        ("transfer_number", "TEXT"),
        ("transfer_type", "TEXT"),
        ("transfer_date", "TEXT"),
        ("source_project_id", "INTEGER"),
        ("dest_project_id", "INTEGER"),
        ("remarks", "TEXT"),
        ("created_by", "TEXT"),
        ("approval_status", "TEXT DEFAULT 'Pending Checker'"),
        ("stock_posted", "INTEGER DEFAULT 0"),
        ("created_at", "TEXT"),
        ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "material_transfers", column, col_type)

    db.execute("""
        CREATE TABLE IF NOT EXISTS material_transfer_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transfer_id INTEGER NOT NULL,
            line_no INTEGER DEFAULT 1,
            material_id INTEGER,
            quantity REAL DEFAULT 0,
            unit TEXT,
            remarks TEXT,
            FOREIGN KEY(transfer_id) REFERENCES material_transfers(id) ON DELETE CASCADE,
            FOREIGN KEY(material_id) REFERENCES materials(id)
        )
    """)

    _backfill_missing_vendor_codes(db)
    ensure_procurement_flow_schema(db)
    db.commit()


def ensure_procurement_flow_schema(db) -> None:
    """Link MR → PR → PO → GRN and quotation comparison."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS purchase_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pr_number TEXT,
            project_id INTEGER,
            material_request_id INTEGER,
            material_id INTEGER,
            request_date TEXT,
            item_description TEXT,
            quantity REAL,
            unit TEXT,
            estimated_cost REAL,
            remarks TEXT,
            created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id),
            FOREIGN KEY(material_request_id) REFERENCES material_requests(id)
        )
    """)
    for column, col_type in (
        ("pr_number", "TEXT"),
        ("material_request_id", "INTEGER"),
        ("material_id", "INTEGER"),
        ("unit", "TEXT"),
    ):
        _ensure_column(db, "purchase_requests", column, col_type)

    for column, col_type in (
        ("material_request_id", "INTEGER"),
        ("cost_plan_id", "INTEGER"),
    ):
        _ensure_column(db, "material_requests", column, col_type)

    for column, col_type in (
        ("purchase_request_id", "INTEGER"),
    ):
        _ensure_column(db, "purchase_orders", column, col_type)

    for column, col_type in (
        ("challan_no", "TEXT"),
        ("vehicle_no", "TEXT"),
    ):
        _ensure_column(db, "store_receipts", column, col_type)

    for column, col_type in (
        ("accepted_qty", "REAL"),
        ("rejected_qty", "REAL DEFAULT 0"),
    ):
        _ensure_column(db, "store_receipt_lines", column, col_type)

    db.execute("""
        CREATE TABLE IF NOT EXISTS po_quotations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_order_id INTEGER NOT NULL,
            vendor_id INTEGER NOT NULL,
            rate REAL DEFAULT 0,
            delivery_days INTEGER DEFAULT 0,
            payment_terms TEXT,
            attachment_ref TEXT,
            is_selected INTEGER DEFAULT 0,
            remarks TEXT,
            created_at TEXT,
            FOREIGN KEY(purchase_order_id) REFERENCES purchase_orders(id) ON DELETE CASCADE,
            FOREIGN KEY(vendor_id) REFERENCES vendors(id)
        )
    """)


def list_approved_material_requests_for_pr(db) -> list[dict]:
    """Approved MRs not yet linked to an active PR."""
    if not _table_exists(db, "material_requests"):
        return []
    rows = db.execute(
        """
        SELECT m.*, p.project_name, mat.code AS material_code
        FROM material_requests m
        LEFT JOIN projects p ON m.project_id = p.id
        LEFT JOIN materials mat ON m.material_id = mat.id
        WHERE m.approval_status = 'Approved'
          AND NOT EXISTS (
            SELECT 1 FROM purchase_requests pr
            WHERE pr.material_request_id = m.id
              AND pr.approval_status NOT IN ('Rejected by Checker', 'Rejected by Approver')
          )
        ORDER BY m.id DESC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def load_purchase_request(db, pr_id: int) -> dict | None:
    row = db.execute(
        """
        SELECT pr.*, p.project_name, mr.item_name AS mr_item_name,
               mr.request_date AS mr_date, mat.code AS material_code
        FROM purchase_requests pr
        LEFT JOIN projects p ON pr.project_id = p.id
        LEFT JOIN material_requests mr ON pr.material_request_id = mr.id
        LEFT JOIN materials mat ON pr.material_id = mat.id
        WHERE pr.id=?
        """,
        (pr_id,),
    ).fetchone()
    return dict(row) if row else None


def list_purchase_requests(db) -> list[dict]:
    rows = db.execute(
        """
        SELECT pr.*, p.project_name, mat.code AS material_code
        FROM purchase_requests pr
        LEFT JOIN projects p ON pr.project_id = p.id
        LEFT JOIN materials mat ON pr.material_id = mat.id
        ORDER BY pr.id DESC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def save_purchase_request_from_mr(
    db,
    form,
    username: str,
    pr_id: int | None = None,
) -> int:
    mr_id_raw = (form.get("material_request_id") or "").strip()
    if not mr_id_raw and pr_id:
        existing_mr = db.execute(
            "SELECT material_request_id FROM purchase_requests WHERE id=?",
            (pr_id,),
        ).fetchone()
        if existing_mr and existing_mr["material_request_id"]:
            mr_id_raw = str(existing_mr["material_request_id"])
    if not mr_id_raw and not pr_id:
        raise ValueError("Select an approved Material Request — manual PR entry is not allowed.")
    mr_id = int(mr_id_raw) if mr_id_raw else None
    mr = None
    if mr_id:
        mr = db.execute(
            "SELECT * FROM material_requests WHERE id=? AND approval_status='Approved'",
            (mr_id,),
        ).fetchone()
        if not mr:
            raise ValueError("Material Request must be Approved before creating a Purchase Request.")
        existing = db.execute(
            """
            SELECT id FROM purchase_requests
            WHERE material_request_id=? AND id != COALESCE(?, -1)
              AND approval_status NOT IN ('Rejected by Checker', 'Rejected by Approver')
            """,
            (mr_id, pr_id),
        ).fetchone()
        if existing:
            raise ValueError("This Material Request already has an active Purchase Request.")

    project_id = (form.get("project_id") or (mr["project_id"] if mr else None))
    material_id = mr["material_id"] if mr else form.get("material_id")
    item_description = (mr["item_name"] if mr else form.get("item_description") or "").strip()
    unit = (mr["unit"] if mr else form.get("unit") or "").strip()
    qty = _safe_float(form.get("quantity") or (mr["quantity"] if mr else 0))
    if qty <= 0:
        raise ValueError("Quantity must be greater than zero.")
    estimated_cost = _safe_float(form.get("estimated_cost"))
    request_date = (form.get("request_date") or "").strip()
    remarks = (form.get("remarks") or "").strip()

    values = (
        project_id,
        mr_id,
        material_id,
        request_date,
        item_description,
        qty,
        unit,
        estimated_cost,
        remarks,
    )
    if pr_id:
        db.execute(
            """
            UPDATE purchase_requests SET project_id=?, material_request_id=?, material_id=?,
            request_date=?, item_description=?, quantity=?, unit=?, estimated_cost=?, remarks=?
            WHERE id=?
            """,
            values + (pr_id,),
        )
        return pr_id

    pr_number = _next_doc_number(db, "PR", "purchase_requests", "pr_number")
    db.execute(
        """
        INSERT INTO purchase_requests(pr_number, project_id, material_request_id, material_id,
        request_date, item_description, quantity, unit, estimated_cost, remarks, created_by,
        approval_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,'Pending Checker')
        """,
        (pr_number,) + values + (username,),
    )
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def list_approved_purchase_requests_for_po(db) -> list[dict]:
    rows = db.execute(
        """
        SELECT pr.*, p.project_name, mat.code AS material_code, mat.name AS material_name
        FROM purchase_requests pr
        LEFT JOIN projects p ON pr.project_id = p.id
        LEFT JOIN materials mat ON pr.material_id = mat.id
        WHERE pr.approval_status = 'Approved'
          AND NOT EXISTS (
            SELECT 1 FROM purchase_orders po
            WHERE po.purchase_request_id = pr.id
              AND po.approval_status NOT IN ('Rejected by Checker', 'Rejected by Approver')
          )
        ORDER BY pr.id DESC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def get_material_request_for_po(db, pr_id: int) -> dict | None:
    pr = load_purchase_request(db, pr_id)
    if not pr or not pr.get("material_request_id"):
        return None
    row = db.execute(
        "SELECT * FROM material_requests WHERE id=?",
        (pr["material_request_id"],),
    ).fetchone()
    return dict(row) if row else None


def save_po_quotations(db, po_id: int, form) -> None:
    vendor_ids = form.getlist("quote_vendor_id[]")
    rates = form.getlist("quote_rate[]")
    delivery_days = form.getlist("quote_delivery_days[]")
    payment_terms = form.getlist("quote_payment_terms[]")
    attachments = form.getlist("quote_attachment[]")
    selected = (form.get("selected_quote_vendor") or "").strip()
    db.execute("DELETE FROM po_quotations WHERE purchase_order_id=?", (po_id,))
    now = _now_ts()
    for idx in range(len(vendor_ids)):
        vid = (vendor_ids[idx] if idx < len(vendor_ids) else "").strip()
        if not vid:
            continue
        rate = _safe_float(rates[idx] if idx < len(rates) else 0)
        days = int(_safe_float(delivery_days[idx] if idx < len(delivery_days) else 0))
        terms = (payment_terms[idx] if idx < len(payment_terms) else "").strip()
        attach = (attachments[idx] if idx < len(attachments) else "").strip()
        is_sel = 1 if selected and selected == vid else 0
        db.execute(
            """
            INSERT INTO po_quotations(purchase_order_id, vendor_id, rate, delivery_days,
            payment_terms, attachment_ref, is_selected, created_at) VALUES(?,?,?,?,?,?,?,?)
            """,
            (po_id, int(vid), rate, days, terms, attach, is_sel, now),
        )


def load_po_quotations(db, po_id: int) -> list[dict]:
    if not _table_exists(db, "po_quotations"):
        return []
    rows = db.execute(
        """
        SELECT q.*, v.name AS vendor_name, v.code AS vendor_code
        FROM po_quotations q
        LEFT JOIN vendors v ON q.vendor_id = v.id
        WHERE q.purchase_order_id=?
        ORDER BY q.rate ASC, q.id
        """,
        (po_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def validate_po_quotations(db, po_id: int) -> str | None:
    quotes = load_po_quotations(db, po_id)
    if len(quotes) < 3:
        return "Add at least 3 vendor quotations before approval."
    if not any(q.get("is_selected") for q in quotes):
        return "Select the winning vendor quotation."
    return None


def get_po_receipt_balances(db, po_id: int) -> list[dict]:
    """Ordered vs received quantities per PO line for GRN dashboard."""
    po = load_purchase_order(db, po_id)
    if not po:
        return []
    result = []
    for line in po.get("lines") or []:
        mat_id = line.get("material_id")
        ordered = float(line.get("quantity") or 0)
        received = float(
            _safe_scalar(
                db,
                """
                SELECT COALESCE(SUM(
                    COALESCE(srl.accepted_qty, srl.quantity, 0)
                ), 0) AS c
                FROM store_receipt_lines srl
                JOIN store_receipts sr ON sr.id = srl.store_receipt_id
                WHERE sr.purchase_order_id = ? AND sr.approval_status = 'Approved'
                  AND srl.material_id = ?
                """,
                (po_id, mat_id),
                default=0.0,
            )
        )
        pending_grn = float(
            _safe_scalar(
                db,
                """
                SELECT COALESCE(SUM(COALESCE(srl.accepted_qty, srl.quantity, 0)), 0) AS c
                FROM store_receipt_lines srl
                JOIN store_receipts sr ON sr.id = srl.store_receipt_id
                WHERE sr.purchase_order_id = ? AND sr.approval_status != 'Approved'
                  AND srl.material_id = ?
                """,
                (po_id, mat_id),
                default=0.0,
            )
        )
        result.append({
            "material_id": mat_id,
            "material_code": line.get("material_code"),
            "description": line.get("description"),
            "unit": line.get("unit"),
            "ordered_qty": ordered,
            "previously_received": received,
            "pending_grn": pending_grn,
            "balance_qty": round(max(0.0, ordered - received - pending_grn), 4),
            "rate": line.get("rate"),
        })
    return result


def project_has_approved_cost_plan(db, project_id: int) -> bool:
    if not project_id or not _table_exists(db, "cost_plans"):
        return False
    row = db.execute(
        "SELECT 1 FROM cost_plans WHERE project_id=? AND approval_status='Approved' LIMIT 1",
        (project_id,),
    ).fetchone()
    return bool(row)


def save_material(db, form, material_id: int | None = None) -> int:
    code = (form.get("code") or "").strip().upper()
    name = (form.get("name") or "").strip()
    if not code or not name:
        raise ValueError("Material code and name are required.")
    now = _now_ts()
    preferred_vendor_id = form.get("preferred_vendor_id") or None
    values = (
        code,
        name,
        (form.get("category") or "").strip(),
        (form.get("unit") or "Nos").strip(),
        (form.get("hsn_code") or "").strip(),
        _safe_float(form.get("gst_percent")),
        _safe_float(form.get("reorder_level")),
        _safe_float(form.get("min_stock")),
        _safe_float(form.get("max_stock")),
        preferred_vendor_id,
        1 if str(form.get("is_active", "1")) in ("1", "on", "true") else 0,
    )
    if material_id:
        db.execute(
            "UPDATE materials SET code=?, name=?, category=?, unit=?, hsn_code=?, gst_percent=?, "
            "reorder_level=?, min_stock=?, max_stock=?, preferred_vendor_id=?, is_active=?, "
            "modified_at=? WHERE id=?",
            values + (now, material_id),
        )
        return material_id
    db.execute(
        "INSERT INTO materials(code, name, category, unit, hsn_code, gst_percent, reorder_level, "
        "min_stock, max_stock, preferred_vendor_id, is_active, created_at, modified_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        values + (now, now),
    )
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def list_materials(db, active_only: bool = False) -> list[dict]:
    sql = (
        "SELECT m.*, v.name AS preferred_vendor_name FROM materials m "
        "LEFT JOIN vendors v ON m.preferred_vendor_id = v.id "
    )
    if active_only:
        sql += "WHERE m.is_active=1 "
    sql += "ORDER BY m.code"
    return [dict(r) for r in db.execute(sql).fetchall()]


def get_material(db, material_id: int) -> dict | None:
    row = db.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
    return dict(row) if row else None


def materials_for_select(db) -> list[dict]:
    return list_materials(db, active_only=True)


def resolve_material_request_from_form(db, form) -> tuple[int, str, str]:
    """Resolve material master selection into stored request fields."""
    material_id_raw = (form.get("material_id") or "").strip()
    if not material_id_raw:
        raise ValueError("Select a material.")
    material_id = int(material_id_raw)
    mat = get_material(db, material_id)
    if not mat or not mat.get("is_active"):
        raise ValueError("Select a valid active material.")
    unit = (form.get("unit") or mat.get("unit") or "").strip()
    return material_id, mat["name"], unit


def get_project_planned_materials(db, project_id: int) -> dict[str, Any]:
    """Cost-plan materials for a project, matched to active materials master by name."""
    if not project_id:
        return {
            "project_id": project_id,
            "materials": [],
            "has_cost_plan": False,
            "unmatched_count": 0,
            "message": "Select a project.",
        }

    if not _table_exists(db, "cost_plan_materials") or not _table_exists(db, "cost_plans"):
        return {
            "project_id": project_id,
            "materials": [],
            "has_cost_plan": False,
            "unmatched_count": 0,
            "message": "No cost plan data available.",
        }

    rows = db.execute(
        """
        SELECT
            LOWER(TRIM(cpm.material_name)) AS name_key,
            cpm.material_name,
            cpm.material_unit,
            COALESCE(SUM(cpm.planned_qty), 0) AS planned_qty
        FROM cost_plan_materials cpm
        JOIN cost_plans cp ON cp.id = cpm.cost_plan_id
        WHERE cp.project_id = ?
          AND cp.approval_status = 'Approved'
          AND TRIM(cpm.material_name) != ''
        GROUP BY name_key, cpm.material_name, cpm.material_unit
        ORDER BY cpm.material_name COLLATE NOCASE
        """,
        (project_id,),
    ).fetchall()

    if not rows:
        return {
            "project_id": project_id,
            "materials": [],
            "has_cost_plan": False,
            "unmatched_count": 0,
            "message": "No planned materials in cost plan for this project.",
        }

    materials: list[dict[str, Any]] = []
    unmatched_count = 0
    for row in rows:
        row_dict = dict(row)
        name_key = (row_dict.get("name_key") or "").strip()
        mat_name = row_dict.get("material_name") or ""
        unit = row_dict.get("material_unit") or "Nos"
        planned_qty = round(float(row_dict.get("planned_qty") or 0), 4)

        matched = db.execute(
            "SELECT id, code, name, unit FROM materials WHERE is_active=1 AND LOWER(TRIM(name)) = ? LIMIT 1",
            (name_key,),
        ).fetchone()

        if matched:
            m = dict(matched)
            materials.append(
                {
                    "material_id": m["id"],
                    "code": m["code"],
                    "name": m["name"],
                    "unit": m.get("unit") or unit,
                    "planned_qty": planned_qty,
                    "matched": True,
                }
            )
        else:
            unmatched_count += 1

    message = None
    if not materials:
        if unmatched_count:
            message = (
                "Cost plan lists materials not found in master — use New Material to add them, "
                "then re-select the project."
            )
        else:
            message = "No planned materials in cost plan for this project."

    return {
        "project_id": project_id,
        "materials": materials,
        "has_cost_plan": True,
        "unmatched_count": unmatched_count,
        "message": message,
    }


def get_project_material_qty_stats(
    db,
    project_id: int,
    material_id: int,
    exclude_request_id: int | None = None,
) -> dict[str, Any]:
    """Per-project material quantity breakdown for material request monitoring."""
    mat = get_material(db, material_id)
    if not mat:
        return {
            "project_id": project_id,
            "material_id": material_id,
            "material_name": "",
            "unit": "Nos",
            "site_required_qty": 0.0,
            "allotted_qty": 0.0,
            "purchased_qty": 0.0,
            "received_qty": 0.0,
            "requested_qty": 0.0,
            "balance_required_qty": 0.0,
            "over_requirement": False,
            "has_site_requirement": False,
        }

    material_name = mat["name"]
    unit = mat.get("unit") or "Nos"

    site_required = 0.0
    if _table_exists(db, "cost_plan_materials") and _table_exists(db, "cost_plans"):
        site_required = float(
            _safe_scalar(
                db,
                """
                SELECT COALESCE(SUM(cpm.planned_qty), 0) AS c
                FROM cost_plan_materials cpm
                JOIN cost_plans cp ON cp.id = cpm.cost_plan_id
                WHERE cp.project_id = ?
                  AND cp.approval_status = 'Approved'
                  AND LOWER(TRIM(cpm.material_name)) = LOWER(TRIM(?))
                """,
                (project_id, material_name),
                default=0.0,
            )
        )

    allotted = float(
        _safe_scalar(
            db,
            """
            SELECT COALESCE(SUM(quantity), 0) AS c
            FROM store_issues
            WHERE project_id = ? AND material_id = ?
              AND approval_status = 'Approved'
              AND COALESCE(stock_posted, 0) = 1
            """,
            (project_id, material_id),
            default=0.0,
        )
    )

    purchased = 0.0
    if _table_exists(db, "purchase_order_lines") and _table_exists(db, "purchase_orders"):
        purchased = float(
            _safe_scalar(
                db,
                """
                SELECT COALESCE(SUM(pol.quantity), 0) AS c
                FROM purchase_order_lines pol
                JOIN purchase_orders po ON po.id = pol.purchase_order_id
                WHERE po.project_id = ? AND pol.material_id = ?
                  AND po.approval_status = 'Approved'
                """,
                (project_id, material_id),
                default=0.0,
            )
        )

    received = 0.0
    if _table_exists(db, "store_receipt_lines") and _table_exists(db, "store_receipts"):
        received = float(
            _safe_scalar(
                db,
                """
                SELECT COALESCE(SUM(COALESCE(srl.accepted_qty, srl.quantity, 0)), 0) AS c
                FROM store_receipt_lines srl
                JOIN store_receipts sr ON sr.id = srl.store_receipt_id
                WHERE sr.project_id = ? AND srl.material_id = ?
                  AND sr.approval_status = 'Approved'
                """,
                (project_id, material_id),
                default=0.0,
            )
        )

    req_params: list[Any] = [project_id, material_id, material_name]
    exclude_sql = ""
    if exclude_request_id:
        exclude_sql = " AND id != ?"
        req_params.append(exclude_request_id)
    requested = float(
        _safe_scalar(
            db,
            f"""
            SELECT COALESCE(SUM(quantity), 0) AS c
            FROM material_requests
            WHERE project_id = ?
              AND (
                material_id = ?
                OR (material_id IS NULL AND LOWER(TRIM(item_name)) = LOWER(TRIM(?)))
              )
              AND approval_status NOT IN ('Rejected by Checker', 'Rejected by Approver')
            {exclude_sql}
            """,
            tuple(req_params),
            default=0.0,
        )
    )

    site_required = round(site_required, 4)
    allotted = round(allotted, 4)
    purchased = round(purchased, 4)
    requested = round(requested, 4)
    balance = round(max(0.0, site_required - allotted - requested), 4)
    over_requirement = site_required > 0 and (allotted + requested) > site_required

    return {
        "project_id": project_id,
        "material_id": material_id,
        "material_name": material_name,
        "unit": unit,
        "site_required_qty": site_required,
        "allotted_qty": allotted,
            "purchased_qty": purchased,
            "received_qty": received,
            "requested_qty": requested,
        "balance_required_qty": balance,
        "over_requirement": over_requirement,
        "has_site_requirement": site_required > 0,
    }


def export_materials_excel(db) -> BytesIO:
    import pandas as pd

    rows = list_materials(db)
    df = pd.DataFrame(rows)
    cols = [c for c in MATERIAL_IMPORT_COLUMNS if c in df.columns]
    if not cols:
        df = pd.DataFrame(columns=MATERIAL_IMPORT_COLUMNS)
    else:
        df = df[cols]
    buf = BytesIO()
    df.to_excel(buf, index=False, sheet_name="Materials")
    buf.seek(0)
    return buf


def import_materials_excel(db, file_storage, username: str) -> tuple[int, list[str]]:
    import pandas as pd

    df = pd.read_excel(file_storage)
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    errors: list[str] = []
    imported = 0
    for idx, row in df.iterrows():
        code = str(row.get("code", "")).strip()
        name = str(row.get("name", "")).strip()
        if not code or not name or code == "nan" or name == "nan":
            continue
        row_data = {
            "code": code,
            "name": name,
            "category": str(row.get("category", "") or ""),
            "unit": str(row.get("unit", "Nos") or "Nos"),
            "hsn_code": str(row.get("hsn_code", "") or ""),
            "gst_percent": row.get("gst_percent", 0),
            "reorder_level": row.get("reorder_level", 0),
            "min_stock": row.get("min_stock", 0),
            "max_stock": row.get("max_stock", 0),
            "preferred_vendor_id": "",
            "is_active": "1",
        }
        try:
            existing = db.execute(
                "SELECT id FROM materials WHERE code=?", (code.upper(),)
            ).fetchone()
            save_material(db, row_data, existing["id"] if existing else None)
            imported += 1
        except Exception as exc:
            errors.append(f"Row {int(idx) + 2}: {exc}")
    return imported, errors


def _migrate_vendor_type_fields(db) -> None:
    """Copy legacy vendor_type into vendor_types JSON when empty."""
    if not _column_exists(db, "vendors", "vendor_types"):
        return
    rows = db.execute(
        "SELECT id, vendor_type, vendor_types FROM vendors "
        "WHERE vendor_types IS NULL OR TRIM(vendor_types) = '' OR vendor_types = '[]'"
    ).fetchall()
    for row in rows:
        legacy = str(row["vendor_type"] or "").strip()
        if legacy and legacy != "Vendor":
            encoded = json.dumps([legacy])
        else:
            encoded = json.dumps(["Supplier"])
        db.execute("UPDATE vendors SET vendor_types=? WHERE id=?", (encoded, row["id"]))


def parse_json_string_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    text = str(raw).strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
    return [part.strip() for part in text.split(",") if part.strip()]


def encode_json_string_list(values: list[str]) -> str:
    cleaned = [str(v).strip() for v in values if str(v).strip()]
    return json.dumps(cleaned)


def vendor_types_list(vendor_row: dict | None) -> list[str]:
    if not vendor_row:
        return []
    types = parse_json_string_list(vendor_row.get("vendor_types"))
    if types:
        return types
    legacy = str(vendor_row.get("vendor_type") or "").strip()
    if legacy and legacy != "Vendor":
        return [legacy]
    return []


def vendor_trade_categories_list(vendor_row: dict | None) -> list[str]:
    if not vendor_row:
        return []
    return parse_json_string_list(vendor_row.get("trade_categories"))


def parse_vendor_types_from_form(form) -> list[str]:
    selected = form.getlist("vendor_types[]") or form.getlist("vendor_types")
    if not selected:
        single = (form.get("vendor_type") or "").strip()
        if single:
            selected = [single]
    cleaned = [v for v in selected if v in VENDOR_TYPE_OPTIONS]
    if not cleaned:
        if (form.get("form_action") or "").strip() == "add_vendor":
            return ["Supplier"]
        raise ValueError("Select at least one vendor type.")
    return cleaned


def parse_trade_categories_from_form(form) -> list[str]:
    selected = form.getlist("trade_categories[]") or form.getlist("trade_categories")
    return [v for v in selected if v in TRADE_CATEGORY_OPTIONS]


def vendor_is_subcontract_eligible(vendor_row: dict) -> bool:
    types = vendor_types_list(vendor_row)
    return any(t in SUBCONTRACT_ELIGIBLE_VENDOR_TYPES for t in types)


def list_subcontract_eligible_vendors(db, active_only: bool = True) -> list[dict]:
    vendors = list_vendors(db, active_only=active_only)
    return [v for v in vendors if vendor_is_subcontract_eligible(v)]


def save_vendor(
    db,
    form,
    vendor_id: int | None = None,
    uploads: dict[str, str | None] | None = None,
) -> int:
    code = (form.get("code") or "").strip().upper()
    name = (form.get("name") or "").strip()
    if not name:
        raise ValueError("Vendor name is required.")
    if not vendor_id and not code:
        code = generate_vendor_code(db)
    if not code:
        raise ValueError("Vendor code is required.")
    uploads = uploads or {}
    existing = get_vendor(db, vendor_id) if vendor_id else None
    now = _now_ts()
    vendor_types = parse_vendor_types_from_form(form)
    trade_categories = parse_trade_categories_from_form(form)
    vendor_types_json = encode_json_string_list(vendor_types)
    trade_categories_json = encode_json_string_list(trade_categories)
    primary_vendor_type = vendor_types[0] if vendor_types else "Supplier"

    def _file_field(key: str) -> str | None:
        if key in uploads and uploads[key]:
            return uploads[key]
        return existing.get(key) if existing else None

    values = (
        code,
        name,
        (form.get("gstin") or "").strip().upper(),
        (form.get("pan") or "").strip().upper(),
        (form.get("contact_person") or "").strip(),
        (form.get("phone") or "").strip(),
        (form.get("email") or "").strip(),
        (form.get("address") or "").strip(),
        (form.get("city") or "").strip(),
        (form.get("state") or "").strip(),
        (form.get("pincode") or "").strip(),
        1 if str(form.get("is_active", "1")) in ("1", "on", "true") else 0,
        primary_vendor_type,
        (form.get("gender") or "").strip(),
        (form.get("date_of_birth") or "").strip(),
        (form.get("bank_account") or "").strip(),
        (form.get("bank_name") or "").strip(),
        (form.get("ifsc_code") or "").strip().upper(),
        (form.get("branch_name") or "").strip(),
        (form.get("aadhaar_number") or "").strip(),
        _file_field("photo"),
        _file_field("pan_document"),
        _file_field("aadhaar_document"),
        _file_field("gst_document"),
        _file_field("bank_proof_document"),
        vendor_types_json,
        trade_categories_json,
    )
    if vendor_id:
        db.execute(
            "UPDATE vendors SET code=?, name=?, gstin=?, pan=?, contact_person=?, phone=?, "
            "email=?, address=?, city=?, state=?, pincode=?, is_active=?, vendor_type=?, "
            "gender=?, date_of_birth=?, bank_account=?, bank_name=?, ifsc_code=?, branch_name=?, "
            "aadhaar_number=?, photo=?, pan_document=?, aadhaar_document=?, gst_document=?, "
            "bank_proof_document=?, vendor_types=?, trade_categories=?, modified_at=? WHERE id=?",
            values + (now, vendor_id),
        )
        return vendor_id
    db.execute(
        "INSERT INTO vendors(code, name, gstin, pan, contact_person, phone, email, address, "
        "city, state, pincode, is_active, vendor_type, gender, date_of_birth, bank_account, "
        "bank_name, ifsc_code, branch_name, aadhaar_number, photo, pan_document, aadhaar_document, "
        "gst_document, bank_proof_document, vendor_types, trade_categories, created_at, modified_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        values + (now, now),
    )
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def list_vendors(db, active_only: bool = False) -> list[dict]:
    sql = "SELECT * FROM vendors "
    if active_only:
        sql += "WHERE is_active=1 "
    sql += "ORDER BY name"
    return [dict(r) for r in db.execute(sql).fetchall()]


def get_vendor(db, vendor_id: int) -> dict | None:
    row = db.execute("SELECT * FROM vendors WHERE id=?", (vendor_id,)).fetchone()
    return dict(row) if row else None


def save_vendor_document(db, vendor_id: int, filename: str, doc_type: str, username: str) -> int:
    now = _now_ts()
    db.execute(
        "INSERT INTO vendor_documents(vendor_id, filename, doc_type, uploaded_by, uploaded_at) "
        "VALUES(?,?,?,?,?)",
        (vendor_id, filename, doc_type, username, now),
    )
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def list_vendor_documents(db, vendor_id: int) -> list[dict]:
    rows = db.execute(
        "SELECT * FROM vendor_documents WHERE vendor_id=? ORDER BY uploaded_at DESC",
        (vendor_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def parse_po_lines_from_form(form) -> tuple[list[dict], str | None]:
    material_ids = form.getlist("material_id[]")
    descriptions = form.getlist("description[]")
    quantities = form.getlist("quantity[]")
    units = form.getlist("unit[]")
    rates = form.getlist("rate[]")
    gst_percents = form.getlist("gst_percent[]")
    tax_types = form.getlist("tax_type[]")
    row_count = max(len(descriptions), len(quantities), len(rates))
    lines: list[dict] = []
    for idx in range(row_count):
        desc = (descriptions[idx] if idx < len(descriptions) else "").strip()
        qty_raw = quantities[idx] if idx < len(quantities) else ""
        rate_raw = rates[idx] if idx < len(rates) else ""
        mat_id = material_ids[idx] if idx < len(material_ids) else ""
        unit = (units[idx] if idx < len(units) else "").strip()
        gst_raw = gst_percents[idx] if idx < len(gst_percents) else "0"
        tax_type = (tax_types[idx] if idx < len(tax_types) else "CGST_SGST").strip()
        if tax_type not in TAX_TYPES:
            tax_type = "CGST_SGST"
        if not desc and not str(qty_raw).strip() and not str(rate_raw).strip():
            continue
        if not desc:
            return [], "Each PO line must have a description."
        qty = _safe_float(qty_raw)
        rate = _safe_float(rate_raw)
        if qty <= 0:
            return [], "Line quantity must be greater than zero."
        gst_percent = _safe_float(gst_raw)
        calc = calc_gst_line(qty, rate, gst_percent, tax_type)
        lines.append({
            "material_id": int(mat_id) if mat_id else None,
            "description": desc,
            "quantity": qty,
            "unit": unit,
            "rate": rate,
            "gst_percent": gst_percent,
            "tax_type": tax_type,
            "taxable_value": calc["taxable_value"],
            "cgst": calc["cgst"],
            "sgst": calc["sgst"],
            "igst": calc["igst"],
            "line_total": calc["line_total"],
            "line_no": len(lines) + 1,
        })
    if not lines:
        return [], "Add at least one PO line item."
    return lines, None


def _totals_from_po_lines(lines: list[dict]) -> dict[str, float]:
    subtotal = round(sum(l["taxable_value"] for l in lines), 2)
    total_cgst = round(sum(l["cgst"] for l in lines), 2)
    total_sgst = round(sum(l["sgst"] for l in lines), 2)
    total_igst = round(sum(l["igst"] for l in lines), 2)
    grand_total = round(subtotal + total_cgst + total_sgst + total_igst, 2)
    return {
        "subtotal": subtotal,
        "total_cgst": total_cgst,
        "total_sgst": total_sgst,
        "total_igst": total_igst,
        "grand_total": grand_total,
    }


def _persist_po_lines(db, po_id: int, lines: list[dict]) -> None:
    db.execute("DELETE FROM purchase_order_lines WHERE purchase_order_id=?", (po_id,))
    for line in lines:
        db.execute(
            "INSERT INTO purchase_order_lines("
            "purchase_order_id, line_no, material_id, description, quantity, unit, rate, "
            "gst_percent, tax_type, taxable_value, cgst, sgst, igst, line_total"
            ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                po_id,
                line["line_no"],
                line.get("material_id"),
                line["description"],
                line["quantity"],
                line.get("unit") or "",
                line["rate"],
                line["gst_percent"],
                line.get("tax_type") or "CGST_SGST",
                line["taxable_value"],
                line["cgst"],
                line["sgst"],
                line["igst"],
                line["line_total"],
            ),
        )


def save_purchase_order(db, form, username: str, po_id: int | None = None) -> int:
    pr_id_raw = (form.get("purchase_request_id") or "").strip()
    if not pr_id_raw and po_id:
        existing_pr = db.execute(
            "SELECT purchase_request_id FROM purchase_orders WHERE id=?",
            (po_id,),
        ).fetchone()
        if existing_pr and existing_pr["purchase_request_id"]:
            pr_id_raw = str(existing_pr["purchase_request_id"])
    if not pr_id_raw and not po_id:
        raise ValueError("Select an approved Purchase Request — manual PO entry is not allowed.")
    if pr_id_raw:
        pr = db.execute(
            "SELECT * FROM purchase_requests WHERE id=? AND approval_status='Approved'",
            (int(pr_id_raw),),
        ).fetchone()
        if not pr:
            raise ValueError("Purchase Request must be Approved before creating a PO.")
        dup = db.execute(
            """
            SELECT id FROM purchase_orders
            WHERE purchase_request_id=? AND id != COALESCE(?, -1)
              AND approval_status NOT IN ('Rejected by Checker', 'Rejected by Approver')
            """,
            (int(pr_id_raw), po_id),
        ).fetchone()
        if dup:
            raise ValueError("This Purchase Request already has an active Purchase Order.")

    lines, err = parse_po_lines_from_form(form)
    if err:
        raise ValueError(err)
    totals = _totals_from_po_lines(lines)
    now = _now_ts()
    vendor_id = form.get("vendor_id") or None
    if not vendor_id:
        raise ValueError("Select a vendor.")
    purchase_request_id = int(pr_id_raw) if pr_id_raw else None
    values = (
        form.get("project_id") or None,
        int(vendor_id),
        purchase_request_id,
        (form.get("order_date") or "").strip(),
        (form.get("delivery_date") or "").strip(),
        (form.get("terms") or "").strip(),
        totals["subtotal"],
        totals["total_cgst"],
        totals["total_sgst"],
        totals["total_igst"],
        totals["grand_total"],
        (form.get("remarks") or "").strip(),
    )
    if po_id:
        db.execute(
            "UPDATE purchase_orders SET project_id=?, vendor_id=?, purchase_request_id=?, order_date=?, "
            "delivery_date=?, terms=?, subtotal=?, total_cgst=?, total_sgst=?, total_igst=?, "
            "grand_total=?, remarks=?, modified_at=? WHERE id=?",
            values + (now, po_id),
        )
        _persist_po_lines(db, po_id, lines)
        save_po_quotations(db, po_id, form)
        return po_id
    po_number = _next_doc_number(db, "PO", "purchase_orders", "po_number")
    db.execute(
        "INSERT INTO purchase_orders(po_number, vendor_id, project_id, purchase_request_id, order_date, "
        "delivery_date, terms, subtotal, total_cgst, total_sgst, total_igst, grand_total, remarks, "
        "created_by, created_at, modified_at, approval_status) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'Pending Checker')",
        (
            po_number,
            int(vendor_id),
            values[0],
            purchase_request_id,
            values[3],
            values[4],
            values[5],
            values[6],
            values[7],
            values[8],
            values[9],
            values[10],
            values[11],
            username,
            now,
            now,
        ),
    )
    new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    _persist_po_lines(db, new_id, lines)
    save_po_quotations(db, new_id, form)
    return new_id


def load_purchase_order(db, po_id: int) -> dict | None:
    row = db.execute(
        "SELECT po.*, v.name AS vendor_name, v.gstin AS vendor_gstin, p.project_name, "
        "pr.pr_number, pr.material_request_id, mr.id AS mr_id "
        "FROM purchase_orders po "
        "LEFT JOIN vendors v ON po.vendor_id = v.id "
        "LEFT JOIN projects p ON po.project_id = p.id "
        "LEFT JOIN purchase_requests pr ON po.purchase_request_id = pr.id "
        "LEFT JOIN material_requests mr ON pr.material_request_id = mr.id "
        "WHERE po.id=?",
        (po_id,),
    ).fetchone()
    if not row:
        return None
    data = dict(row)
    line_rows = db.execute(
        "SELECT l.*, m.code AS material_code, m.name AS material_name "
        "FROM purchase_order_lines l "
        "LEFT JOIN materials m ON l.material_id = m.id "
        "WHERE l.purchase_order_id=? ORDER BY l.line_no, l.id",
        (po_id,),
    ).fetchall()
    data["lines"] = [dict(l) for l in line_rows]
    data["quotations"] = load_po_quotations(db, po_id)
    return data


def list_purchase_orders(db) -> list[dict]:
    rows = db.execute(
        "SELECT po.*, v.name AS vendor_name, p.project_name, pr.pr_number "
        "FROM purchase_orders po "
        "LEFT JOIN vendors v ON po.vendor_id = v.id "
        "LEFT JOIN projects p ON po.project_id = p.id "
        "LEFT JOIN purchase_requests pr ON po.purchase_request_id = pr.id "
        "ORDER BY po.order_date DESC, po.id DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def parse_grn_lines_from_form(form) -> tuple[list[dict], str | None]:
    material_ids = form.getlist("material_id[]")
    descriptions = form.getlist("description[]")
    quantities = form.getlist("quantity[]")
    accepted_qtys = form.getlist("accepted_qty[]")
    rejected_qtys = form.getlist("rejected_qty[]")
    units = form.getlist("unit[]")
    rates = form.getlist("rate[]")
    remarks_list = form.getlist("line_remarks[]")
    row_count = max(len(material_ids), len(quantities))
    lines: list[dict] = []
    for idx in range(row_count):
        mat_id = material_ids[idx] if idx < len(material_ids) else ""
        qty_raw = quantities[idx] if idx < len(quantities) else ""
        if not mat_id and not str(qty_raw).strip():
            continue
        if not mat_id:
            return [], "Each GRN line must select a material."
        qty = _safe_float(qty_raw)
        accepted = _safe_float(accepted_qtys[idx] if idx < len(accepted_qtys) else qty_raw)
        rejected = _safe_float(rejected_qtys[idx] if idx < len(rejected_qtys) else 0)
        if accepted <= 0 and qty <= 0:
            return [], "GRN line accepted quantity must be greater than zero."
        if accepted <= 0:
            accepted = qty
        desc = (descriptions[idx] if idx < len(descriptions) else "").strip()
        unit = (units[idx] if idx < len(units) else "").strip()
        rate = _safe_float(rates[idx] if idx < len(rates) else 0)
        line_remarks = (remarks_list[idx] if idx < len(remarks_list) else "").strip()
        lines.append({
            "material_id": int(mat_id),
            "description": desc,
            "quantity": accepted + rejected,
            "accepted_qty": accepted,
            "rejected_qty": rejected,
            "unit": unit,
            "rate": rate,
            "remarks": line_remarks,
            "line_no": len(lines) + 1,
        })
    if not lines:
        return [], "Add at least one GRN line item."
    return lines, None


def _persist_grn_lines(db, grn_id: int, lines: list[dict]) -> None:
    db.execute("DELETE FROM store_receipt_lines WHERE store_receipt_id=?", (grn_id,))
    for line in lines:
        db.execute(
            "INSERT INTO store_receipt_lines("
            "store_receipt_id, line_no, material_id, description, quantity, accepted_qty, "
            "rejected_qty, unit, rate, remarks"
            ") VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                grn_id,
                line["line_no"],
                line["material_id"],
                line.get("description") or "",
                line["quantity"],
                line.get("accepted_qty", line["quantity"]),
                line.get("rejected_qty", 0),
                line.get("unit") or "",
                line.get("rate") or 0,
                line.get("remarks") or "",
            ),
        )


def save_store_receipt(db, form, username: str, receipt_id: int | None = None) -> int:
    lines, err = parse_grn_lines_from_form(form)
    if err:
        raise ValueError(err)
    po_id = form.get("purchase_order_id") or None
    if not po_id and not receipt_id:
        raise ValueError("GRN must be linked to an Approved Purchase Order.")
    if po_id:
        po = db.execute(
            "SELECT * FROM purchase_orders WHERE id=? AND approval_status='Approved'",
            (int(po_id),),
        ).fetchone()
        if not po:
            raise ValueError("Purchase Order must be Approved before GRN.")
        balances = get_po_receipt_balances(db, int(po_id))
        bal_map = {b["material_id"]: b for b in balances}
        for line in lines:
            bal = bal_map.get(line["material_id"])
            if bal and line.get("accepted_qty", 0) > bal["balance_qty"] + 0.001:
                raise ValueError(
                    f"Accepted qty exceeds PO balance for {bal.get('description') or 'item'} "
                    f"(balance {bal['balance_qty']})."
                )

    total_amount = round(
        sum(l.get("accepted_qty", l["quantity"]) * l.get("rate", 0) for l in lines), 2
    )
    project_id = form.get("project_id") or None
    vendor_id = form.get("vendor_id") or None
    supplier = (form.get("supplier") or "").strip()
    challan_no = (form.get("challan_no") or "").strip()
    vehicle_no = (form.get("vehicle_no") or "").strip()
    if vendor_id:
        v = get_vendor(db, int(vendor_id))
        if v and not supplier:
            supplier = v["name"]
    first_line = lines[0]
    mat = get_material(db, first_line["material_id"])
    item_name = mat["name"] if mat else first_line.get("description") or "GRN Items"
    if receipt_id:
        db.execute(
            "UPDATE store_receipts SET project_id=?, receipt_date=?, item_name=?, quantity=?, "
            "unit=?, supplier=?, remarks=?, vendor_id=?, purchase_order_id=?, material_id=?, "
            "total_amount=?, invoice_ref=?, challan_no=?, vehicle_no=? WHERE id=?",
            (
                project_id,
                (form.get("receipt_date") or "").strip(),
                item_name,
                sum(l.get("accepted_qty", l["quantity"]) for l in lines),
                first_line.get("unit") or (mat["unit"] if mat else ""),
                supplier,
                (form.get("remarks") or "").strip(),
                vendor_id,
                po_id,
                first_line["material_id"],
                total_amount,
                (form.get("invoice_ref") or "").strip(),
                challan_no,
                vehicle_no,
                receipt_id,
            ),
        )
        _persist_grn_lines(db, receipt_id, lines)
        return receipt_id
    grn_number = _next_doc_number(db, "GRN", "store_receipts", "grn_number")
    db.execute(
        "INSERT INTO store_receipts(project_id, receipt_date, item_name, quantity, unit, supplier, "
        "remarks, created_by, approval_status, grn_number, vendor_id, purchase_order_id, "
        "material_id, total_amount, invoice_ref, challan_no, vehicle_no, stock_posted) "
        "VALUES(?,?,?,?,?,?,?,?,'Pending Checker',?,?,?,?,?,?,?,?,0)",
        (
            project_id,
            (form.get("receipt_date") or "").strip(),
            item_name,
            sum(l.get("accepted_qty", l["quantity"]) for l in lines),
            first_line.get("unit") or (mat["unit"] if mat else ""),
            supplier,
            (form.get("remarks") or "").strip(),
            username,
            grn_number,
            vendor_id,
            po_id,
            first_line["material_id"],
            total_amount,
            (form.get("invoice_ref") or "").strip(),
            challan_no,
            vehicle_no,
        ),
    )
    new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    _persist_grn_lines(db, new_id, lines)
    return new_id


def load_store_receipt(db, receipt_id: int) -> dict | None:
    row = db.execute(
        "SELECT s.*, p.project_name, v.name AS vendor_name, po.po_number "
        "FROM store_receipts s "
        "LEFT JOIN projects p ON s.project_id = p.id "
        "LEFT JOIN vendors v ON s.vendor_id = v.id "
        "LEFT JOIN purchase_orders po ON s.purchase_order_id = po.id "
        "WHERE s.id=?",
        (receipt_id,),
    ).fetchone()
    if not row:
        return None
    data = dict(row)
    line_rows = db.execute(
        "SELECT l.*, m.code AS material_code, m.name AS material_name "
        "FROM store_receipt_lines l "
        "LEFT JOIN materials m ON l.material_id = m.id "
        "WHERE l.store_receipt_id=? ORDER BY l.line_no, l.id",
        (receipt_id,),
    ).fetchall()
    data["lines"] = [dict(l) for l in line_rows]
    if not data["lines"] and data.get("material_id"):
        data["lines"] = [{
            "material_id": data["material_id"],
            "material_name": data.get("item_name"),
            "quantity": data.get("quantity"),
            "unit": data.get("unit"),
            "description": data.get("item_name"),
            "rate": 0,
            "remarks": "",
        }]
    return data


def list_store_receipts(db) -> list[dict]:
    rows = db.execute(
        "SELECT s.*, p.project_name, v.name AS vendor_name "
        "FROM store_receipts s "
        "LEFT JOIN projects p ON s.project_id = p.id "
        "LEFT JOIN vendors v ON s.vendor_id = v.id "
        "ORDER BY s.receipt_date DESC, s.id DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_stock_balance(db, material_id: int, project_id: int | None = None) -> float:
    if project_id:
        row = db.execute(
            "SELECT COALESCE(SUM(quantity), 0) AS bal FROM stock_ledger "
            "WHERE material_id=? AND (project_id=? OR project_id IS NULL)",
            (material_id, project_id),
        ).fetchone()
    else:
        row = db.execute(
            "SELECT COALESCE(SUM(quantity), 0) AS bal FROM stock_ledger WHERE material_id=?",
            (material_id,),
        ).fetchone()
    return float(row["bal"] if row else 0)


def validate_issue_stock(db, material_id: int, quantity: float, project_id: int | None) -> str | None:
    if quantity <= 0:
        return "Issue quantity must be greater than zero."
    balance = get_stock_balance(db, material_id, project_id)
    if quantity > balance:
        return f"Insufficient stock. Available: {balance:.2f}, requested: {quantity:.2f}"
    return None


def save_store_issue(db, form, username: str, issue_id: int | None = None) -> int:
    material_id = form.get("material_id")
    if not material_id:
        raise ValueError("Select a material.")
    material_id = int(material_id)
    qty = _safe_float(form.get("quantity"))
    project_id = form.get("project_id") or None
    err = validate_issue_stock(db, material_id, qty, int(project_id) if project_id else None)
    if err and not issue_id:
        raise ValueError(err)
    mat = get_material(db, material_id)
    if not mat:
        raise ValueError("Invalid material.")
    item_name = mat["name"]
    unit = (form.get("unit") or mat.get("unit") or "").strip()
    values = (
        project_id,
        (form.get("issue_date") or "").strip(),
        item_name,
        qty,
        unit,
        (form.get("issued_to") or "").strip(),
        (form.get("remarks") or "").strip(),
        material_id,
    )
    if issue_id:
        existing = db.execute(
            "SELECT approval_status, stock_posted FROM store_issues WHERE id=?",
            (issue_id,),
        ).fetchone()
        if existing and existing["stock_posted"]:
            raise ValueError("Cannot edit issue after stock has been posted.")
        if err:
            raise ValueError(err)
        db.execute(
            "UPDATE store_issues SET project_id=?, issue_date=?, item_name=?, quantity=?, unit=?, "
            "issued_to=?, remarks=?, material_id=? WHERE id=?",
            values + (issue_id,),
        )
        return issue_id
    db.execute(
        "INSERT INTO store_issues(project_id, issue_date, item_name, quantity, unit, issued_to, "
        "remarks, created_by, approval_status, material_id, stock_posted) "
        "VALUES(?,?,?,?,?,?,?,?,'Pending Checker',?,0)",
        values + (username,),
    )
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def load_store_issue(db, issue_id: int) -> dict | None:
    row = db.execute(
        "SELECT s.*, p.project_name, m.code AS material_code, m.name AS material_name "
        "FROM store_issues s "
        "LEFT JOIN projects p ON s.project_id = p.id "
        "LEFT JOIN materials m ON s.material_id = m.id "
        "WHERE s.id=?",
        (issue_id,),
    ).fetchone()
    return dict(row) if row else None


def list_store_issues(db) -> list[dict]:
    rows = db.execute(
        "SELECT s.*, p.project_name, m.code AS material_code "
        "FROM store_issues s "
        "LEFT JOIN projects p ON s.project_id = p.id "
        "LEFT JOIN materials m ON s.material_id = m.id "
        "ORDER BY s.issue_date DESC, s.id DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def void_stock_for_reference(db, reference_table: str, reference_id: int) -> None:
    db.execute(
        "DELETE FROM stock_ledger WHERE reference_table=? AND reference_id=?",
        (reference_table, reference_id),
    )
    if reference_table == "store_receipts":
        db.execute(
            "UPDATE store_receipts SET stock_posted=0 WHERE id=?",
            (reference_id,),
        )
    elif reference_table == "store_issues":
        db.execute(
            "UPDATE store_issues SET stock_posted=0 WHERE id=?",
            (reference_id,),
        )
    elif reference_table == "material_transfers":
        db.execute(
            "UPDATE material_transfers SET stock_posted=0 WHERE id=?",
            (reference_id,),
        )


def post_stock_on_approval(db, reference_table: str, reference_id: int, username: str) -> None:
    now = _now_ts()
    if reference_table == "store_receipts":
        rec = load_store_receipt(db, reference_id)
        if not rec or rec.get("stock_posted"):
            return
        void_stock_for_reference(db, reference_table, reference_id)
        for line in rec.get("lines") or []:
            mat_id = line.get("material_id")
            if not mat_id:
                continue
            qty_in = float(line.get("accepted_qty") or line.get("quantity") or 0)
            if qty_in <= 0:
                continue
            db.execute(
                "INSERT INTO stock_ledger(material_id, project_id, movement_date, movement_type, "
                "quantity, unit, reference_table, reference_id, reference_line_id, remarks, "
                "created_by, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    mat_id,
                    rec.get("project_id"),
                    rec.get("receipt_date"),
                    MOVEMENT_GRN_IN,
                    qty_in,
                    line.get("unit") or "",
                    reference_table,
                    reference_id,
                    line.get("id"),
                    line.get("remarks") or rec.get("remarks") or "",
                    username,
                    now,
                ),
            )
        db.execute(
            "UPDATE store_receipts SET stock_posted=1 WHERE id=?",
            (reference_id,),
        )
    elif reference_table == "store_issues":
        issue = load_store_issue(db, reference_id)
        if not issue or issue.get("stock_posted"):
            return
        mat_id = issue.get("material_id")
        if not mat_id:
            return
        err = validate_issue_stock(
            db,
            mat_id,
            float(issue.get("quantity") or 0),
            issue.get("project_id"),
        )
        if err:
            raise ValueError(err)
        void_stock_for_reference(db, reference_table, reference_id)
        db.execute(
            "INSERT INTO stock_ledger(material_id, project_id, movement_date, movement_type, "
            "quantity, unit, reference_table, reference_id, remarks, created_by, created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                mat_id,
                issue.get("project_id"),
                issue.get("issue_date"),
                MOVEMENT_ISSUE_OUT,
                -float(issue.get("quantity") or 0),
                issue.get("unit") or "",
                reference_table,
                reference_id,
                issue.get("remarks") or "",
                username,
                now,
            ),
        )
        db.execute(
            "UPDATE store_issues SET stock_posted=1 WHERE id=?",
            (reference_id,),
        )
    elif reference_table == "material_transfers":
        transfer = load_material_transfer(db, reference_id)
        if not transfer or transfer.get("stock_posted"):
            return
        void_stock_for_reference(db, reference_table, reference_id)
        source_pid = transfer.get("source_project_id")
        dest_pid = transfer.get("dest_project_id")
        for line in transfer.get("lines") or []:
            mat_id = line.get("material_id")
            qty = float(line.get("quantity") or 0)
            if not mat_id or qty <= 0:
                continue
            err = validate_issue_stock(
                db, mat_id, qty, int(source_pid) if source_pid else None
            )
            if err:
                raise ValueError(err)
            db.execute(
                "INSERT INTO stock_ledger(material_id, project_id, movement_date, movement_type, "
                "quantity, unit, reference_table, reference_id, reference_line_id, remarks, "
                "created_by, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    mat_id,
                    source_pid,
                    transfer.get("transfer_date"),
                    MOVEMENT_TRANSFER_OUT,
                    -qty,
                    line.get("unit") or "",
                    reference_table,
                    reference_id,
                    line.get("id"),
                    transfer.get("remarks") or "",
                    username,
                    now,
                ),
            )
            db.execute(
                "INSERT INTO stock_ledger(material_id, project_id, movement_date, movement_type, "
                "quantity, unit, reference_table, reference_id, reference_line_id, remarks, "
                "created_by, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    mat_id,
                    dest_pid,
                    transfer.get("transfer_date"),
                    MOVEMENT_TRANSFER_IN,
                    qty,
                    line.get("unit") or "",
                    reference_table,
                    reference_id,
                    line.get("id"),
                    transfer.get("remarks") or "",
                    username,
                    now,
                ),
            )
        db.execute(
            "UPDATE material_transfers SET stock_posted=1 WHERE id=?",
            (reference_id,),
        )


def list_inventory_stock(db) -> list[dict]:
    rows = db.execute(
        "SELECT m.id AS material_id, m.code, m.name, m.category, m.unit, "
        "m.reorder_level, m.min_stock, m.max_stock, "
        "COALESCE(SUM(sl.quantity), 0) AS balance "
        "FROM materials m "
        "LEFT JOIN stock_ledger sl ON sl.material_id = m.id "
        "WHERE m.is_active=1 "
        "GROUP BY m.id "
        "ORDER BY m.code"
    ).fetchall()
    result = []
    for r in rows:
        row = dict(r)
        bal = float(row.get("balance") or 0)
        reorder = float(row.get("reorder_level") or 0)
        row["balance"] = bal
        row["low_stock"] = reorder > 0 and bal <= reorder
        result.append(row)
    return result


def store_dashboard_stats(db) -> dict[str, Any]:
    try:
        materials = _active_count(db, "materials")
        vendors = _active_count(db, "vendors")
        pending_mr = _pending_approval_count(db, "material_requests")
        pending_pr = _pending_approval_count(db, "purchase_requests")
        pending_po = _pending_approval_count(db, "purchase_orders")
        pending_grn = _pending_approval_count(db, "store_receipts")

        inventory_rows: list[dict] = []
        try:
            inventory_rows = list_inventory_stock(db)
        except Exception:
            inventory_rows = []

        low_stock = [r for r in inventory_rows if r.get("low_stock")]

        approx_stock_value = 0.0
        if _table_exists(db, "stock_ledger"):
            try:
                approx_stock_value = float(
                    _safe_scalar(
                        db,
                        "SELECT COALESCE(SUM(sl.quantity * COALESCE(l.rate, 0)), 0) AS c "
                        "FROM stock_ledger sl "
                        "LEFT JOIN store_receipt_lines l ON sl.reference_line_id = l.id "
                        "WHERE sl.movement_type=? AND sl.quantity > 0",
                        (MOVEMENT_GRN_IN,),
                        default=0.0,
                    )
                )
            except Exception:
                approx_stock_value = 0.0

        return {
            "materials": materials,
            "vendors": vendors,
            "pending_material_requests": pending_mr,
            "pending_purchase_requests": pending_pr,
            "pending_purchase_orders": pending_po,
            "pending_grn": pending_grn,
            "low_stock_count": len(low_stock),
            "low_stock_items": low_stock[:10],
            "stock_items": len(inventory_rows),
            "approx_stock_value": approx_stock_value,
        }
    except Exception:
        return _empty_store_dashboard_stats()


def _parse_transfer_lines(form) -> list[dict]:
    material_ids = form.getlist("material_id[]")
    quantities = form.getlist("quantity[]")
    units = form.getlist("unit[]")
    remarks_list = form.getlist("line_remarks[]")
    lines = []
    row_count = max(len(material_ids), len(quantities), len(units))
    for idx in range(row_count):
        mat_raw = material_ids[idx] if idx < len(material_ids) else ""
        qty_raw = quantities[idx] if idx < len(quantities) else ""
        if not str(mat_raw).strip():
            continue
        try:
            mat_id = int(mat_raw)
            qty = _safe_float(qty_raw)
        except (ValueError, TypeError):
            raise ValueError("Enter valid material and quantity on each transfer line.")
        if qty <= 0:
            raise ValueError("Transfer quantity must be greater than zero.")
        unit = (units[idx] if idx < len(units) else "").strip()
        line_remarks = (remarks_list[idx] if idx < len(remarks_list) else "").strip()
        lines.append({
            "line_no": len(lines) + 1,
            "material_id": mat_id,
            "quantity": qty,
            "unit": unit,
            "remarks": line_remarks,
        })
    return lines


def _validate_transfer_type(transfer_type: str, source_id, dest_id) -> None:
    valid_types = {t[0] for t in MATERIAL_TRANSFER_TYPES}
    if transfer_type not in valid_types:
        raise ValueError("Select a valid transfer type.")
    if transfer_type == "store_to_store":
        if source_id == dest_id and source_id is not None:
            raise ValueError("Source and destination must differ for Store-to-Store transfer.")
        if dest_id is None:
            raise ValueError("Select a destination store for Store-to-Store transfer.")
    elif transfer_type == "store_to_site":
        if source_id is not None:
            raise ValueError("Store-to-Site transfers must originate from Central Store.")
        if dest_id is None:
            raise ValueError("Select a destination site (project) for Store-to-Site transfer.")
    elif transfer_type == "site_to_site":
        if source_id is None or dest_id is None:
            raise ValueError("Select both source and destination sites for Site-to-Site transfer.")
        if int(source_id) == int(dest_id):
            raise ValueError("Source and destination sites must differ.")


def save_material_transfer(db, form, username: str, transfer_id: int | None = None) -> int:
    transfer_type = (form.get("transfer_type") or "").strip()
    transfer_date = (form.get("transfer_date") or "").strip()
    source_raw = (form.get("source_project_id") or "").strip()
    dest_raw = (form.get("dest_project_id") or "").strip()
    source_id = int(source_raw) if source_raw else None
    dest_id = int(dest_raw) if dest_raw else None
    remarks = (form.get("remarks") or "").strip()
    _validate_transfer_type(transfer_type, source_id, dest_id)
    lines = _parse_transfer_lines(form)
    if not lines:
        raise ValueError("Add at least one material line to transfer.")
    for line in lines:
        mat = get_material(db, line["material_id"])
        if not mat:
            raise ValueError("Invalid material on transfer line.")
        if not line["unit"]:
            line["unit"] = mat.get("unit") or "Nos"
        err = validate_issue_stock(db, line["material_id"], line["quantity"], source_id)
        if err and not transfer_id:
            raise ValueError(err)
    now = _now_ts()
    if transfer_id:
        existing = db.execute(
            "SELECT approval_status, stock_posted FROM material_transfers WHERE id=?",
            (transfer_id,),
        ).fetchone()
        if existing and existing["stock_posted"]:
            raise ValueError("Cannot edit transfer after stock has been posted.")
        for line in lines:
            err = validate_issue_stock(db, line["material_id"], line["quantity"], source_id)
            if err:
                raise ValueError(err)
        db.execute(
            "UPDATE material_transfers SET transfer_type=?, transfer_date=?, source_project_id=?, "
            "dest_project_id=?, remarks=?, modified_at=? WHERE id=?",
            (transfer_type, transfer_date, source_id, dest_id, remarks, now, transfer_id),
        )
        db.execute("DELETE FROM material_transfer_lines WHERE transfer_id=?", (transfer_id,))
        for line in lines:
            db.execute(
                "INSERT INTO material_transfer_lines(transfer_id, line_no, material_id, quantity, unit, remarks) "
                "VALUES(?,?,?,?,?,?)",
                (transfer_id, line["line_no"], line["material_id"], line["quantity"], line["unit"], line["remarks"]),
            )
        return transfer_id
    transfer_number = _next_doc_number(db, "MT", "material_transfers", "transfer_number")
    db.execute(
        "INSERT INTO material_transfers(transfer_number, transfer_type, transfer_date, source_project_id, "
        "dest_project_id, remarks, created_by, approval_status, stock_posted, created_at, modified_at) "
        "VALUES(?,?,?,?,?,?,?,'Pending Checker',0,?,?)",
        (transfer_number, transfer_type, transfer_date, source_id, dest_id, remarks, username, now, now),
    )
    new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    for line in lines:
        db.execute(
            "INSERT INTO material_transfer_lines(transfer_id, line_no, material_id, quantity, unit, remarks) "
            "VALUES(?,?,?,?,?,?)",
            (new_id, line["line_no"], line["material_id"], line["quantity"], line["unit"], line["remarks"]),
        )
    return new_id


def load_material_transfer(db, transfer_id: int) -> dict | None:
    row = db.execute(
        "SELECT t.*, sp.project_name AS source_project_name, dp.project_name AS dest_project_name "
        "FROM material_transfers t "
        "LEFT JOIN projects sp ON t.source_project_id = sp.id "
        "LEFT JOIN projects dp ON t.dest_project_id = dp.id "
        "WHERE t.id=?",
        (transfer_id,),
    ).fetchone()
    if not row:
        return None
    result = dict(row)
    line_rows = db.execute(
        "SELECT l.*, m.code AS material_code, m.name AS material_name "
        "FROM material_transfer_lines l "
        "LEFT JOIN materials m ON l.material_id = m.id "
        "WHERE l.transfer_id=? ORDER BY l.line_no, l.id",
        (transfer_id,),
    ).fetchall()
    result["lines"] = [dict(r) for r in line_rows]
    type_labels = dict(MATERIAL_TRANSFER_TYPES)
    result["transfer_type_label"] = type_labels.get(result.get("transfer_type"), result.get("transfer_type"))
    return result


def list_material_transfers(db) -> list[dict]:
    rows = db.execute(
        "SELECT t.*, sp.project_name AS source_project_name, dp.project_name AS dest_project_name "
        "FROM material_transfers t "
        "LEFT JOIN projects sp ON t.source_project_id = sp.id "
        "LEFT JOIN projects dp ON t.dest_project_id = dp.id "
        "ORDER BY t.transfer_date DESC, t.id DESC"
    ).fetchall()
    type_labels = dict(MATERIAL_TRANSFER_TYPES)
    result = []
    for row in rows:
        item = dict(row)
        item["transfer_type_label"] = type_labels.get(item.get("transfer_type"), item.get("transfer_type"))
        result.append(item)
    return result
