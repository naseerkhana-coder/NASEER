from flask import Flask, g, render_template, request, redirect, url_for, session, flash, send_from_directory, jsonify, make_response
from werkzeug.utils import secure_filename
import sqlite3
import os
import json
import pandas as pd
import bcrypt
from datetime import datetime, timedelta
from calendar import monthrange
from zoneinfo import ZoneInfo

from workflow_service import (
    ALLOWED_RECORD_TABLES,
    create_approval_request,
    advance_approval,
    reopen_transaction,
    resubmit_record,
    can_maker_edit,
    can_user_edit,
    delete_workflow_record,
    get_edit_role_for_user,
    get_approval_request,
    get_pending_counts,
    get_pending_items,
    get_workflow_queue,
    get_workflow_for_module,
    seed_workflow_master,
    migrate_workflow_statuses,
    sync_workflow_designations,
    seed_demo_users,
    status_display,
    display_status_from_workflow,
    display_status,
    maker_status_message,
    get_dashboard_counters,
    get_approval_summary,
    get_workflow_audit_report,
    get_workflow_access_for_designation,
    get_workflow_access_label,
    user_workflow_capabilities,
    get_user_workflow_role,
    is_admin_role,
    get_recent_activities,
    get_approval_history,
    get_notifications,
    mark_notifications_read,
    WORKFLOW_STATUS,
    RECORD_PENDING_CHECKER,
    RECORD_PENDING_APPROVAL,
    RECORD_APPROVED,
    RECORD_REJECTED_CHECKER,
    RECORD_REJECTED_APPROVER,
)

APP_VERSION = "1.0.0"

BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")


def is_bcrypt_hash(stored_password):
    if not stored_password:
        return False
    return str(stored_password).startswith(BCRYPT_PREFIXES)


def verify_password(stored_password, provided_password):
    if stored_password is None or provided_password is None:
        return False
    stored = str(stored_password)
    provided = str(provided_password)
    if is_bcrypt_hash(stored):
        try:
            return bcrypt.checkpw(provided.encode("utf-8"), stored.encode("utf-8"))
        except (ValueError, TypeError):
            return False
    return stored == provided


def _is_truthy(value):
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in ("1", "true", "yes", "y")


def user_is_active(user_row):
    if user_row is None:
        return False
    keys = user_row.keys()
    if "is_disabled" in keys or "account_locked" in keys:
        disabled = _is_truthy(user_row["is_disabled"]) if "is_disabled" in keys else False
        locked = _is_truthy(user_row["account_locked"]) if "account_locked" in keys else False
        return not disabled and not locked
    if "status" in keys:
        return str(user_row["status"] or "").strip().lower() == "active"
    return True


def get_user_id(user_row):
    if user_row is None:
        return None
    keys = user_row.keys()
    if "id" in keys and user_row["id"] is not None:
        return user_row["id"]
    if "user_id" in keys:
        return user_row["user_id"]
    return None


def _row_val(user_row, key, default=""):
    if key not in user_row.keys():
        return default
    val = user_row[key]
    return val if val is not None else default


def get_user_display_name(user_row):
    return (
        _row_val(user_row, "employee_name")
        or _row_val(user_row, "full_name")
        or _row_val(user_row, "username")
    )


def authenticate_user(db, username, password):
    user = db.execute(
        "SELECT * FROM users WHERE username=?",
        (username.strip(),),
    ).fetchone()
    if not user or not user_is_active(user):
        return None
    if not verify_password(user["password"], password):
        return None
    return user


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "maxek.db")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
PHOTOS_DIR = os.path.join(BASE_DIR, "static", "photos")
UPLOADS_DIR = os.path.join(BASE_DIR, "static", "uploads")
STAFF_DOCS_DIR = os.path.join(UPLOADS_DIR, "staff")
WORKER_DOCS_DIR = os.path.join(UPLOADS_DIR, "workers")
SUBCONTRACTOR_DOCS_DIR = os.path.join(UPLOADS_DIR, "subcontractors")
CLIENT_DOCS_DIR = os.path.join(UPLOADS_DIR, "clients")
PROJECT_DOCS_DIR = os.path.join(UPLOADS_DIR, "projects")

os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(PHOTOS_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(STAFF_DOCS_DIR, exist_ok=True)
os.makedirs(WORKER_DOCS_DIR, exist_ok=True)
os.makedirs(SUBCONTRACTOR_DOCS_DIR, exist_ok=True)
os.makedirs(CLIENT_DOCS_DIR, exist_ok=True)
os.makedirs(PROJECT_DOCS_DIR, exist_ok=True)

GOV_DEPARTMENTS = ["PWD", "NH", "KIIFB", "Kerala PWD", "NHAI", "Other"]
GUARANTEE_TYPES = ["Performance Guarantee", "Bank Guarantee", "Both"]
MAX_MAKER_ASSIGNMENTS = 15
BOQ_UNITS = ["Nos", "Sqm", "Sqft", "Rmt", "Kg", "MT", "Ltr", "Cum", "Hour", "Day", "LS", "Set", "Bag"]
MAX_BOQ_LINES = 25
STEEL_DIAMETERS_MM = [8, 10, 12, 16, 20, 25, 32, 40]
VOLUME_UNITS = {"Cum", "cum", "m3", "M3", "CUM"}
AREA_UNITS = {"Sqm", "sqm", "m2", "M2", "SQM", "Sqft"}
STEEL_UNITS = {"Kg", "kg", "MT", "mt", "Ton", "ton", "Tonne", "tonne"}
DEFAULT_STEEL_SHAPES = [
    ("Straight", 1, "straight"),
    ("L-Shape", 2, "perimeter"),
    ("U-Shape", 3, "perimeter"),
    ("Rectangle", 4, "perimeter"),
    ("Pentagon", 5, "perimeter"),
    ("Ring / Hexagon", 6, "perimeter"),
]
MANPOWER_TRADES = [
    "Carpenter",
    "Steel Fixer",
    "Helper",
    "Mason",
    "Electrician",
    "Plumber",
    "Painter",
]
MAX_MANPOWER_TRADES = 7
SUBCONTRACTOR_RATE_TYPES = ("Manpower", "BOQ Base Rate")

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = "change-this-secret"
app.config["TEMPLATES_AUTO_RELOAD"] = True


@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def save_file(file_storage, dest_folder):
    if file_storage and file_storage.filename:
        try:
            os.makedirs(dest_folder, exist_ok=True)
            filename = secure_filename(file_storage.filename)
            timestamp = int(datetime.utcnow().timestamp())
            saved_name = f"{timestamp}_{filename}"
            path = os.path.join(dest_folder, saved_name)
            file_storage.save(path)
            return saved_name
        except OSError:
            return None
    return None


def generate_employee_code(db):
    rows = db.execute(
        "SELECT employee_code FROM staff WHERE employee_code LIKE 'EMP%'"
    ).fetchall()
    max_code = 100
    for row in rows:
        code = str(row["employee_code"] or "").strip().upper()
        number = code[3:]
        if number.isdigit():
            max_code = max(max_code, int(number))
    return f"EMP{max_code + 1}"


def _clean_name_letters(name):
    return "".join(ch for ch in (name or "").upper() if ch.isalnum())


def subcontractor_name_prefix(name):
    """First two letters of cleaned name."""
    letters = _clean_name_letters(name)
    if len(letters) >= 2:
        return letters[:2]
    if letters:
        return (letters + "U")[:2]
    return "SU"


def subcontractor_code_prefix(code_or_name):
    """Two-letter prefix from stored ID (SA100 -> SA) or from a name."""
    raw = str(code_or_name or "").strip().upper()
    letters = "".join(ch for ch in raw if ch.isalnum())
    if not letters:
        return "SU"
    alpha_end = 0
    while alpha_end < len(letters) and letters[alpha_end].isalpha():
        alpha_end += 1
    if alpha_end > 0 and alpha_end < len(letters) and letters[alpha_end:].isdigit():
        alpha = letters[:alpha_end]
        if len(alpha) >= 2:
            return alpha[:2]
        return (alpha + "U")[:2]
    return subcontractor_name_prefix(raw)


def _subcontractor_prefix_candidates(name):
    """Try 1st+2nd letters, then 1st+3rd, 1st+4th, … when prefixes collide."""
    letters = _clean_name_letters(name)
    if not letters:
        return ["SU"]
    candidates = []

    def add(prefix):
        if prefix and len(prefix) == 2 and prefix not in candidates:
            candidates.append(prefix)

    if len(letters) >= 2:
        add(letters[:2])
    if len(letters) >= 3:
        add(letters[0] + letters[2])
    if len(letters) >= 4:
        add(letters[0] + letters[3])
    if len(letters) >= 5:
        add(letters[0] + letters[4])
    if len(letters) >= 6:
        add(letters[0] + letters[5])
    add("SU")
    return candidates


def _subcontractor_prefix_in_use(db, prefix, exclude_id=None):
    prefix = (prefix or "").upper()
    rows = db.execute(
        "SELECT id, subcontractor_code FROM subcontractors "
        "WHERE subcontractor_code IS NOT NULL AND TRIM(subcontractor_code) != ''"
    ).fetchall()
    for row in rows:
        if exclude_id is not None and row["id"] == exclude_id:
            continue
        if subcontractor_code_prefix(row["subcontractor_code"]) == prefix:
            return True
    return False


def resolve_subcontractor_prefix(db, name, exclude_id=None):
    for prefix in _subcontractor_prefix_candidates(name):
        if not _subcontractor_prefix_in_use(db, prefix, exclude_id=exclude_id):
            return prefix
    return _subcontractor_prefix_candidates(name)[0]


def _max_prefix_code_number(db, prefix):
    max_num = 99
    for table, column in (("subcontractors", "subcontractor_code"), ("workers", "worker_code")):
        rows = db.execute(
            f"SELECT {column} AS code FROM {table} WHERE {column} LIKE ?",
            (f"{prefix}%",),
        ).fetchall()
        for row in rows:
            code = str(row["code"] or "").strip().upper()
            if not code.startswith(prefix):
                continue
            number = code[len(prefix):]
            if number.isdigit():
                max_num = max(max_num, int(number))
    return max_num


def generate_subcontractor_code(db, name):
    prefix = resolve_subcontractor_prefix(db, name)
    max_num = _max_prefix_code_number(db, prefix)
    next_num = 100 if max_num < 100 else max_num + 1
    return f"{prefix}{next_num}"


def generate_worker_code(db, worker_category, subcontractor_id=None):
    if worker_category == "Sub Contractor Staff" and subcontractor_id:
        sub = db.execute(
            "SELECT subcontractor_code, subcontractor_name FROM subcontractors WHERE id=?",
            (subcontractor_id,),
        ).fetchone()
        if sub:
            if sub["subcontractor_code"]:
                prefix = subcontractor_code_prefix(sub["subcontractor_code"])
            elif sub["subcontractor_name"]:
                prefix = resolve_subcontractor_prefix(db, sub["subcontractor_name"])
            else:
                prefix = "SU"
            max_num = _max_prefix_code_number(db, prefix)
            next_num = max_num + 1 if max_num >= 100 else 101
            return f"{prefix}{next_num}"
    rows = db.execute("SELECT worker_code FROM workers WHERE worker_code LIKE 'WRK%'").fetchall()
    max_code = 100
    for row in rows:
        code = str(row["worker_code"] or "").strip().upper()
        number = code[3:]
        if number.isdigit():
            max_code = max(max_code, int(number))
    return f"WRK{max_code + 1}"


def backfill_subcontractor_codes(db):
    rows = db.execute(
        "SELECT id, subcontractor_name FROM subcontractors "
        "WHERE subcontractor_code IS NULL OR TRIM(subcontractor_code) = '' "
        "ORDER BY id"
    ).fetchall()
    for row in rows:
        code = generate_subcontractor_code(db, row["subcontractor_name"])
        db.execute(
            "UPDATE subcontractors SET subcontractor_code=? WHERE id=?",
            (code, row["id"]),
        )


def ensure_subcontractor_rate_tables(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS subcontractor_manpower_rates(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subcontractor_id INTEGER NOT NULL,
            trade_name TEXT,
            rate_unit TEXT,
            working_hours REAL,
            rate_amount REAL,
            salary_amount REAL,
            FOREIGN KEY(subcontractor_id) REFERENCES subcontractors(id)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS subcontractor_boq_rates(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subcontractor_id INTEGER NOT NULL,
            project_id INTEGER,
            boq_item_id INTEGER,
            boq_number TEXT,
            item_description TEXT,
            unit TEXT,
            rate REAL,
            quantity REAL,
            total_amount REAL,
            line_no INTEGER,
            FOREIGN KEY(subcontractor_id) REFERENCES subcontractors(id),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    for table, column, col_type in (
        ("subcontractor_manpower_rates", "subcontractor_id", "INTEGER"),
        ("subcontractor_manpower_rates", "trade_name", "TEXT"),
        ("subcontractor_manpower_rates", "rate_unit", "TEXT"),
        ("subcontractor_manpower_rates", "working_hours", "REAL"),
        ("subcontractor_manpower_rates", "rate_amount", "REAL"),
        ("subcontractor_manpower_rates", "salary_amount", "REAL"),
        ("subcontractor_boq_rates", "subcontractor_id", "INTEGER"),
        ("subcontractor_boq_rates", "project_id", "INTEGER"),
        ("subcontractor_boq_rates", "boq_item_id", "INTEGER"),
        ("subcontractor_boq_rates", "boq_number", "TEXT"),
        ("subcontractor_boq_rates", "item_description", "TEXT"),
        ("subcontractor_boq_rates", "unit", "TEXT"),
        ("subcontractor_boq_rates", "rate", "REAL"),
        ("subcontractor_boq_rates", "quantity", "REAL"),
        ("subcontractor_boq_rates", "total_amount", "REAL"),
        ("subcontractor_boq_rates", "line_no", "INTEGER"),
    ):
        _ensure_column(db, table, column, col_type)


def _parse_subcontractor_manpower_rates():
    trades = request.form.getlist("mp_trade_name[]")
    units = request.form.getlist("mp_rate_unit[]")
    working_hours_list = request.form.getlist("mp_working_hours[]")
    salary_amounts = request.form.getlist("mp_salary_amount[]")
    rows = []
    for idx, trade in enumerate(trades):
        trade_name = (trade or "").strip()
        if not trade_name:
            continue
        rate_unit = units[idx].strip() if idx < len(units) else "Day"
        try:
            working_hours = float(working_hours_list[idx] or 8) if idx < len(working_hours_list) else 8.0
        except ValueError:
            working_hours = 8.0
        if working_hours <= 0:
            working_hours = 8.0
        try:
            salary_amount = float(salary_amounts[idx] or 0) if idx < len(salary_amounts) else 0.0
        except ValueError:
            salary_amount = 0.0
        if salary_amount <= 0:
            continue
        rate_amount = (
            round(salary_amount / working_hours, 2)
            if rate_unit == "Hour"
            else salary_amount
        )
        rows.append({
            "trade_name": trade_name,
            "rate_unit": rate_unit or "Day",
            "working_hours": working_hours,
            "rate_amount": rate_amount,
            "salary_amount": salary_amount,
        })
    if len(rows) > MAX_MANPOWER_TRADES:
        return None, f"Maximum {MAX_MANPOWER_TRADES} trade rates allowed."
    return rows, None


def _parse_subcontractor_boq_rates():
    project_id = request.form.get("boq_project_id", "").strip()
    item_ids = request.form.getlist("sb_boq_item_id[]")
    boq_numbers = request.form.getlist("sb_boq_number[]")
    descriptions = request.form.getlist("sb_item_description[]")
    units = request.form.getlist("sb_unit[]")
    rates = request.form.getlist("sb_rate[]")
    quantities = request.form.getlist("sb_quantity[]")
    totals = request.form.getlist("sb_total_amount[]")
    rows = []
    for idx, item_id in enumerate(item_ids):
        if not (item_id or "").strip() and not (descriptions[idx] if idx < len(descriptions) else "").strip():
            continue
        try:
            rate_val = float(rates[idx] or 0) if idx < len(rates) else 0.0
        except ValueError:
            rate_val = 0.0
        try:
            qty_val = float(quantities[idx] or 0) if idx < len(quantities) else 0.0
        except ValueError:
            qty_val = 0.0
        try:
            total_val = float(totals[idx] or 0) if idx < len(totals) else 0.0
        except ValueError:
            total_val = round(rate_val * qty_val, 2)
        if total_val <= 0 and rate_val <= 0:
            continue
        rows.append({
            "boq_item_id": int(item_id) if (item_id or "").strip().isdigit() else None,
            "boq_number": boq_numbers[idx].strip() if idx < len(boq_numbers) else "",
            "item_description": descriptions[idx].strip() if idx < len(descriptions) else "",
            "unit": units[idx].strip() if idx < len(units) else "",
            "rate": rate_val,
            "quantity": qty_val,
            "total_amount": total_val if total_val > 0 else round(rate_val * qty_val, 2),
            "line_no": idx + 1,
        })
    return project_id or None, rows


def _insert_subcontractor_manpower_rates(db, subcontractor_id, manpower_rows):
    for row in manpower_rows:
        db.execute(
            "INSERT INTO subcontractor_manpower_rates("
            "subcontractor_id, trade_name, rate_unit, working_hours, rate_amount, salary_amount"
            ") VALUES(?,?,?,?,?,?)",
            (
                subcontractor_id, row["trade_name"], row["rate_unit"],
                row["working_hours"], row["rate_amount"], row["salary_amount"],
            ),
        )


def _insert_subcontractor_boq_rates(db, subcontractor_id, project_id, boq_rows):
    for line in boq_rows:
        db.execute(
            "INSERT INTO subcontractor_boq_rates("
            "subcontractor_id, project_id, boq_item_id, boq_number, item_description, "
            "unit, rate, quantity, total_amount, line_no"
            ") VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                subcontractor_id, project_id, line["boq_item_id"],
                line["boq_number"], line["item_description"], line["unit"],
                line["rate"], line["quantity"], line["total_amount"], line["line_no"],
            ),
        )


def _sync_subcontractor_rates(db, subcontractor_id, rate_type, is_update=False):
    if rate_type == "Manpower":
        db.execute("DELETE FROM subcontractor_boq_rates WHERE subcontractor_id=?", (subcontractor_id,))
        manpower_rows, mp_error = _parse_subcontractor_manpower_rates()
        if mp_error:
            return mp_error
        if not manpower_rows:
            if is_update:
                return None
            return "Add at least one manpower trade rate."
        db.execute(
            "DELETE FROM subcontractor_manpower_rates WHERE subcontractor_id=?",
            (subcontractor_id,),
        )
        _insert_subcontractor_manpower_rates(db, subcontractor_id, manpower_rows)
        return None
    if rate_type == "BOQ Base Rate":
        db.execute(
            "DELETE FROM subcontractor_manpower_rates WHERE subcontractor_id=?",
            (subcontractor_id,),
        )
        project_id, boq_rows = _parse_subcontractor_boq_rates()
        if boq_rows:
            if not project_id:
                return "Select a project for BOQ base rates."
            db.execute(
                "DELETE FROM subcontractor_boq_rates WHERE subcontractor_id=?",
                (subcontractor_id,),
            )
            _insert_subcontractor_boq_rates(db, subcontractor_id, project_id, boq_rows)
        elif not is_update:
            return "Add at least one BOQ line item for BOQ base rate."
        return None
    return None


def _subcontractor_dependent_counts(db, subcontractor_id):
    workers = db.execute(
        "SELECT COUNT(*) AS c FROM workers WHERE subcontractor_id=?",
        (subcontractor_id,),
    ).fetchone()["c"]
    requests = db.execute(
        "SELECT COUNT(*) AS c FROM subcontract_requests WHERE subcontractor_id=?",
        (subcontractor_id,),
    ).fetchone()["c"]
    return int(workers or 0), int(requests or 0)


def generate_client_code(db):
    rows = db.execute("SELECT client_code FROM clients WHERE client_code LIKE 'CLT%'").fetchall()
    max_code = 100
    for row in rows:
        code = str(row["client_code"] or "").strip().upper()
        number = code[3:]
        if number.isdigit():
            max_code = max(max_code, int(number))
    return f"CLT{max_code + 1}"


def generate_project_code(db):
    """Return the next numeric project code (minimum 104 when none higher exist)."""
    rows = db.execute(
        "SELECT project_code FROM projects WHERE project_code IS NOT NULL AND project_code != ''"
    ).fetchall()
    max_num = 103
    for row in rows:
        code = str(row["project_code"] or "").strip().upper()
        number = code[3:] if code.startswith("PRJ") else code
        if number.isdigit():
            max_num = max(max_num, int(number))
    return str(max_num + 1)


def get_workflow_modules():
    return query_db(
        "SELECT module_id, module_name FROM workflow_master WHERE status='Active' ORDER BY module_name"
    )


def ensure_user_maker_assignments_table(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS user_maker_assignments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            slot_no INTEGER NOT NULL,
            department TEXT,
            module_id TEXT,
            status TEXT DEFAULT 'Active',
            UNIQUE(user_id, slot_no),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)


def save_user_maker_assignments(db, user_id, departments, module_ids, statuses):
    ensure_user_maker_assignments_table(db)
    db.execute("DELETE FROM user_maker_assignments WHERE user_id=?", (user_id,))
    for idx, dept in enumerate(departments):
        module_id = module_ids[idx] if idx < len(module_ids) else ""
        status = statuses[idx] if idx < len(statuses) else "Active"
        dept = (dept or "").strip()
        module_id = (module_id or "").strip()
        if not dept and not module_id:
            continue
        db.execute(
            "INSERT INTO user_maker_assignments(user_id, slot_no, department, module_id, status) "
            "VALUES(?,?,?,?,?)",
            (user_id, idx + 1, dept, module_id, status or "Active"),
        )


def get_user_maker_assignments(db, user_id):
    ensure_user_maker_assignments_table(db)
    return query_db(
        "SELECT * FROM user_maker_assignments WHERE user_id=? ORDER BY slot_no",
        (user_id,),
    )


def ensure_boq_master_table(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS boq_master(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            boq_number TEXT,
            project_id INTEGER,
            total_amount REAL DEFAULT 0,
            line_count INTEGER DEFAULT 0,
            created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            created_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)


def generate_boq_number(db):
    rows = db.execute("SELECT boq_number FROM boq_master WHERE boq_number LIKE 'BOQ%'").fetchall()
    max_code = 100
    for row in rows:
        code = str(row["boq_number"] or "").strip().upper()
        number = code[3:]
        if number.isdigit():
            max_code = max(max_code, int(number))
    return f"BOQ{max_code + 1}"


def ensure_dpr_measurement_tables(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS steel_shapes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shape_name TEXT NOT NULL,
            side_count INTEGER DEFAULT 1,
            formula_type TEXT DEFAULT 'straight',
            created_by TEXT,
            created_at TEXT
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS dpr_measurements(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            report_date TEXT,
            boq_item_id INTEGER,
            boq_number TEXT,
            boq_description TEXT,
            unit TEXT,
            calculated_quantity REAL DEFAULT 0,
            measurement_type TEXT,
            bill_client INTEGER DEFAULT 0,
            for_costing INTEGER DEFAULT 0,
            billing_status TEXT DEFAULT 'none',
            costing_status TEXT DEFAULT 'none',
            measurement_data TEXT,
            created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            created_at TEXT,
            work_description TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id),
            FOREIGN KEY(boq_item_id) REFERENCES boq_items(id)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS dpr_steel_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            measurement_id INTEGER,
            line_description TEXT,
            num_bars INTEGER DEFAULT 0,
            cutting_length REAL DEFAULT 0,
            diameter_mm REAL DEFAULT 0,
            shape_id INTEGER,
            side_measurements TEXT,
            quantity REAL DEFAULT 0,
            FOREIGN KEY(measurement_id) REFERENCES dpr_measurements(id),
            FOREIGN KEY(shape_id) REFERENCES steel_shapes(id)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS dpr_manpower(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            measurement_id INTEGER,
            subcontractor_id INTEGER,
            worker_id INTEGER,
            worker_name TEXT,
            trade_name TEXT,
            hours_worked REAL DEFAULT 0,
            remarks TEXT,
            FOREIGN KEY(measurement_id) REFERENCES dpr_measurements(id),
            FOREIGN KEY(subcontractor_id) REFERENCES subcontractors(id),
            FOREIGN KEY(worker_id) REFERENCES workers(id)
        )
    """)
    count = db.execute("SELECT COUNT(*) AS c FROM steel_shapes").fetchone()["c"]
    if count == 0:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for name, sides, formula in DEFAULT_STEEL_SHAPES:
            db.execute(
                "INSERT INTO steel_shapes(shape_name, side_count, formula_type, created_by, created_at) "
                "VALUES(?,?,?,?,?)",
                (name, sides, formula, "system", now),
            )
    _ensure_dpr_measurement_columns(db)
    db.commit()


def _ensure_dpr_measurement_columns(db):
    """Backfill columns when dpr_measurements was created from an older/partial schema."""
    for table, column, col_type in (
        ("dpr_measurements", "project_id", "INTEGER"),
        ("dpr_measurements", "report_date", "TEXT"),
        ("dpr_measurements", "boq_item_id", "INTEGER"),
        ("dpr_measurements", "boq_number", "TEXT"),
        ("dpr_measurements", "boq_description", "TEXT"),
        ("dpr_measurements", "unit", "TEXT"),
        ("dpr_measurements", "calculated_quantity", "REAL DEFAULT 0"),
        ("dpr_measurements", "measurement_type", "TEXT"),
        ("dpr_measurements", "bill_client", "INTEGER DEFAULT 0"),
        ("dpr_measurements", "for_costing", "INTEGER DEFAULT 0"),
        ("dpr_measurements", "billing_status", "TEXT DEFAULT 'none'"),
        ("dpr_measurements", "costing_status", "TEXT DEFAULT 'none'"),
        ("dpr_measurements", "measurement_data", "TEXT"),
        ("dpr_measurements", "created_by", "TEXT"),
        ("dpr_measurements", "approval_status", "TEXT DEFAULT 'Pending Checker'"),
        ("dpr_measurements", "created_at", "TEXT"),
        ("dpr_measurements", "work_description", "TEXT"),
        ("dpr_steel_lines", "measurement_id", "INTEGER"),
        ("dpr_steel_lines", "line_description", "TEXT"),
        ("dpr_steel_lines", "num_bars", "INTEGER DEFAULT 0"),
        ("dpr_steel_lines", "cutting_length", "REAL DEFAULT 0"),
        ("dpr_steel_lines", "diameter_mm", "REAL DEFAULT 0"),
        ("dpr_steel_lines", "shape_id", "INTEGER"),
        ("dpr_steel_lines", "side_measurements", "TEXT"),
        ("dpr_steel_lines", "quantity", "REAL DEFAULT 0"),
        ("dpr_manpower", "measurement_id", "INTEGER"),
        ("dpr_manpower", "subcontractor_id", "INTEGER"),
        ("dpr_manpower", "worker_id", "INTEGER"),
        ("dpr_manpower", "worker_name", "TEXT"),
        ("dpr_manpower", "trade_name", "TEXT"),
        ("dpr_manpower", "hours_worked", "REAL DEFAULT 0"),
        ("dpr_manpower", "remarks", "TEXT"),
    ):
        _ensure_column(db, table, column, col_type)


def prepare_dpr_page_db(db):
    """Ensure DPR tables and related columns exist before rendering DPR pages."""
    ensure_dpr_measurement_tables(db)
    _ensure_column(db, "subcontractors", "subcontractor_code", "TEXT")
    _ensure_column(db, "projects", "project_code", "TEXT")
    _ensure_column(db, "boq_items", "boq_id", "INTEGER")
    _ensure_column(db, "boq_items", "project_id", "INTEGER")
    if _table_exists(db, "project_expenses"):
        _ensure_column(db, "project_expenses", "dpr_measurement_id", "INTEGER")
    db.commit()


def prepare_workers_page_db(db):
    """Ensure worker and subcontractor rate schema before worker pages."""
    ensure_subcontractor_rate_tables(db)
    worker_columns = (
        ("worker_code", "TEXT"),
        ("aadhaar_number", "TEXT"),
        ("worker_category", "TEXT DEFAULT 'Company Staff'"),
        ("subcontractor_id", "INTEGER"),
        ("bank_account", "TEXT"),
        ("bank_name", "TEXT"),
        ("ifsc_code", "TEXT"),
        ("branch_name", "TEXT"),
        ("pan_number", "TEXT"),
        ("id_proof", "TEXT"),
        ("aadhaar_document", "TEXT"),
        ("pan_document", "TEXT"),
        ("photo", "TEXT"),
        ("mobile", "TEXT"),
        ("designation", "TEXT"),
        ("salary_type", "TEXT"),
        ("salary_amount", "REAL"),
        ("ot_applicable", "TEXT"),
        ("working_hours", "REAL"),
        ("joining_date", "TEXT"),
        ("status", "TEXT"),
    )
    for column, col_type in worker_columns:
        _ensure_column(db, "workers", column, col_type)
    db.commit()


STAFF_SALARY_COMPONENT_OPTIONS = [
    "Basic Salary",
    "Room Rent",
    "Travel Expense",
    "Telephone",
    "HRA",
    "DA",
    "Special Allowance",
    "Medical Allowance",
    "Food Allowance",
    "Other",
]


def ensure_staff_hr_tables(db):
    """Salary split-up, increments, travel tiers, company provision flags."""
    _ensure_column(db, "staff", "company_room_provided", "TEXT DEFAULT 'No'")
    _ensure_column(db, "staff", "company_food_provided", "TEXT DEFAULT 'No'")
    db.execute("""
        CREATE TABLE IF NOT EXISTS staff_salary_components(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            component_name TEXT NOT NULL,
            amount REAL DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY(staff_id) REFERENCES staff(id) ON DELETE CASCADE
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS staff_salary_increments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            effective_date TEXT,
            previous_amount REAL DEFAULT 0,
            new_amount REAL DEFAULT 0,
            increment_amount REAL DEFAULT 0,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            FOREIGN KEY(staff_id) REFERENCES staff(id) ON DELETE CASCADE
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS staff_travel_tiers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            continuous_months INTEGER NOT NULL,
            travel_mode TEXT NOT NULL,
            allowance_amount REAL DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY(staff_id) REFERENCES staff(id) ON DELETE CASCADE
        )
    """)
    db.commit()


APP_TIMEZONE_OPTIONS = [
    ("Asia/Kolkata", "India — IST (Asia/Kolkata)"),
    ("Asia/Colombo", "Sri Lanka — SLST (Asia/Colombo)"),
    ("Asia/Kathmandu", "Nepal — NPT (Asia/Kathmandu)"),
    ("Asia/Dhaka", "Bangladesh — BST (Asia/Dhaka)"),
    ("Asia/Karachi", "Pakistan — PKT (Asia/Karachi)"),
    ("Asia/Dubai", "UAE — GST (Asia/Dubai)"),
    ("Asia/Riyadh", "Saudi Arabia — AST (Asia/Riyadh)"),
    ("Asia/Qatar", "Qatar — AST (Asia/Qatar)"),
    ("Asia/Singapore", "Singapore — SGT (Asia/Singapore)"),
    ("Asia/Kuala_Lumpur", "Malaysia — MYT (Asia/Kuala_Lumpur)"),
    ("Asia/Bangkok", "Thailand — ICT (Asia/Bangkok)"),
    ("Asia/Jakarta", "Indonesia — WIB (Asia/Jakarta)"),
    ("Asia/Manila", "Philippines — PHT (Asia/Manila)"),
    ("Asia/Hong_Kong", "Hong Kong — HKT (Asia/Hong_Kong)"),
    ("Asia/Shanghai", "China — CST (Asia/Shanghai)"),
    ("Asia/Tokyo", "Japan — JST (Asia/Tokyo)"),
    ("Asia/Seoul", "South Korea — KST (Asia/Seoul)"),
    ("Australia/Sydney", "Australia — AEST (Australia/Sydney)"),
    ("Europe/London", "United Kingdom — GMT/BST (Europe/London)"),
    ("Europe/Paris", "France — CET (Europe/Paris)"),
    ("Europe/Berlin", "Germany — CET (Europe/Berlin)"),
    ("America/New_York", "United States — Eastern (America/New_York)"),
    ("America/Chicago", "United States — Central (America/Chicago)"),
    ("America/Los_Angeles", "United States — Pacific (America/Los_Angeles)"),
    ("UTC", "UTC"),
]


def ensure_app_settings_table(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS app_settings(
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT
        )
    """)
    row = db.execute(
        "SELECT setting_value FROM app_settings WHERE setting_key=?",
        ("timezone",),
    ).fetchone()
    if not row:
        db.execute(
            "INSERT INTO app_settings(setting_key, setting_value) VALUES(?,?)",
            ("timezone", "Asia/Kolkata"),
        )
    db.commit()


def get_app_setting(db, key, default=None):
    ensure_app_settings_table(db)
    row = db.execute(
        "SELECT setting_value FROM app_settings WHERE setting_key=?",
        (key,),
    ).fetchone()
    if not row or row["setting_value"] is None:
        return default
    return row["setting_value"]


def set_app_setting(db, key, value):
    ensure_app_settings_table(db)
    db.execute(
        "INSERT INTO app_settings(setting_key, setting_value) VALUES(?,?) "
        "ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value",
        (key, value),
    )
    db.commit()


def get_app_timezone(db=None):
    if db is None:
        db = get_db()
    tz_name = get_app_setting(db, "timezone", "Asia/Kolkata")
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("Asia/Kolkata")


def get_app_now(db=None):
    return datetime.now(get_app_timezone(db))


def format_app_datetime(dt=None, fmt="%A, %d %b %Y | %H:%M", db=None):
    if dt is None:
        dt = get_app_now(db)
    elif isinstance(dt, str):
        text = dt.strip()
        if not text:
            return "—"
        parsed = None
        for parse_fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(text, parse_fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            return text
        dt = parsed.replace(tzinfo=get_app_timezone(db))
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=get_app_timezone(db))
    else:
        dt = dt.astimezone(get_app_timezone(db))
    return dt.strftime(fmt)


@app.template_filter("app_datetime")
def app_datetime_filter(value, fmt="%d %b %Y %H:%M"):
    if value is None or value == "":
        return "—"
    return format_app_datetime(value, fmt=fmt)


def ensure_staff_bonus_table(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS staff_bonus(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            bonus_period TEXT NOT NULL,
            worked_days REAL DEFAULT 0,
            leave_days REAL DEFAULT 0,
            held_ot_hours REAL DEFAULT 0,
            method TEXT NOT NULL,
            per_day_rate REAL DEFAULT 0,
            calculated_amount REAL DEFAULT 0,
            rounded_amount REAL DEFAULT 0,
            final_amount REAL DEFAULT 0,
            payment_status TEXT DEFAULT 'pending',
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            paid_at TEXT,
            FOREIGN KEY(staff_id) REFERENCES staff(id) ON DELETE CASCADE,
            UNIQUE(staff_id, bonus_period)
        )
    """)
    db.commit()


def _bonus_period_bounds(year, month):
    period = f"{year:04d}-{month:02d}"
    last_day = monthrange(year, month)[1]
    period_start = f"{year:04d}-{month:02d}-01"
    period_end = f"{year:04d}-{month:02d}-{last_day:02d}"
    return period, period_start, period_end


def compute_staff_bonus_attendance_stats(db, staff_id, year, month):
    """Worked/leave days in period; cumulative held OT through month end."""
    _, period_start, period_end = _bonus_period_bounds(year, month)
    rows = db.execute(
        "SELECT status, ot_hours FROM attendance "
        "WHERE worker_id=? AND COALESCE(worker_source, 'worker')='staff' "
        "AND attendance_date BETWEEN ? AND ?",
        (staff_id, period_start, period_end),
    ).fetchall()
    worked_days = 0.0
    leave_days = 0.0
    for row in rows:
        status = (row["status"] or "Present").strip()
        if status == "Present":
            worked_days += 1.0
        elif status == "Half Day":
            worked_days += 0.5
            leave_days += 0.5
        elif status == "Absent":
            leave_days += 1.0
    ot_row = db.execute(
        "SELECT COALESCE(SUM(ot_hours), 0) AS total_ot FROM attendance "
        "WHERE worker_id=? AND COALESCE(worker_source, 'worker')='staff' "
        "AND attendance_date <= ?",
        (staff_id, period_end),
    ).fetchone()
    held_ot_hours = float(ot_row["total_ot"] or 0) if ot_row else 0.0
    staff_row = db.execute(
        "SELECT salary_type, salary_amount FROM staff WHERE id=?",
        (staff_id,),
    ).fetchone()
    suggested_per_day = 0.0
    if staff_row:
        salary_amount = float(staff_row["salary_amount"] or 0)
        salary_type = (staff_row["salary_type"] or "Monthly").strip()
        days_in_month = monthrange(year, month)[1]
        if salary_type == "Daily":
            suggested_per_day = salary_amount
        elif days_in_month > 0:
            suggested_per_day = round(salary_amount / days_in_month, 2)
    return {
        "worked_days": round(worked_days, 2),
        "leave_days": round(leave_days, 2),
        "held_ot_hours": round(held_ot_hours, 2),
        "suggested_per_day_rate": suggested_per_day,
        "period_start": period_start,
        "period_end": period_end,
    }


def prepare_staff_page_db(db):
    ensure_staff_hr_tables(db)
    ensure_staff_bonus_table(db)


def prepare_hr_bonus_db(db):
    ensure_staff_bonus_table(db)
    ensure_app_settings_table(db)


def _fetch_staff_salary_components(db, staff_id):
    rows = db.execute(
        "SELECT component_name, amount FROM staff_salary_components "
        "WHERE staff_id=? ORDER BY sort_order, id",
        (staff_id,),
    ).fetchall()
    return [{"component_name": r["component_name"], "amount": float(r["amount"] or 0)} for r in rows]


def _fetch_staff_travel_tiers(db, staff_id):
    rows = db.execute(
        "SELECT continuous_months, travel_mode, allowance_amount FROM staff_travel_tiers "
        "WHERE staff_id=? ORDER BY sort_order, continuous_months, id",
        (staff_id,),
    ).fetchall()
    return [
        {
            "continuous_months": int(r["continuous_months"] or 0),
            "travel_mode": r["travel_mode"] or "One Side",
            "allowance_amount": float(r["allowance_amount"] or 0),
        }
        for r in rows
    ]


def _fetch_staff_salary_increments(db, staff_id):
    rows = db.execute(
        "SELECT * FROM staff_salary_increments WHERE staff_id=? "
        "ORDER BY effective_date DESC, id DESC",
        (staff_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _save_staff_salary_components(db, staff_id, components):
    db.execute("DELETE FROM staff_salary_components WHERE staff_id=?", (staff_id,))
    for idx, comp in enumerate(components):
        name = (comp.get("component_name") or "").strip()
        if not name:
            continue
        try:
            amount = float(comp.get("amount") or 0)
        except (TypeError, ValueError):
            amount = 0.0
        db.execute(
            "INSERT INTO staff_salary_components(staff_id, component_name, amount, sort_order) "
            "VALUES(?,?,?,?)",
            (staff_id, name, amount, idx),
        )


def _save_staff_travel_tiers(db, staff_id, tiers):
    db.execute("DELETE FROM staff_travel_tiers WHERE staff_id=?", (staff_id,))
    for idx, tier in enumerate(tiers):
        try:
            months = int(tier.get("continuous_months") or 0)
        except (TypeError, ValueError):
            months = 0
        if months <= 0:
            continue
        mode = (tier.get("travel_mode") or "One Side").strip()
        if mode not in ("One Side", "Both Side"):
            mode = "One Side"
        try:
            allowance = float(tier.get("allowance_amount") or 0)
        except (TypeError, ValueError):
            allowance = 0.0
        db.execute(
            "INSERT INTO staff_travel_tiers(staff_id, continuous_months, travel_mode, "
            "allowance_amount, sort_order) VALUES(?,?,?,?,?)",
            (staff_id, months, mode, allowance, idx),
        )


def _parse_staff_hr_json(raw, default):
    try:
        data = json.loads(raw or "[]")
        return data if isinstance(data, list) else default
    except json.JSONDecodeError:
        return default


def _unit_measurement_type(unit):
    u = (unit or "").strip()
    if u in VOLUME_UNITS:
        return "volume"
    if u in AREA_UNITS:
        return "area"
    if u in STEEL_UNITS:
        return "steel"
    return "simple"


def _average_readings(values):
    nums = []
    for v in values:
        try:
            n = float(v)
            if n > 0:
                nums.append(n)
        except (TypeError, ValueError):
            continue
    return round(sum(nums) / len(nums), 4) if nums else 0.0


def _steel_bar_weight_kg(diameter_mm, length_m, num_bars):
    d = float(diameter_mm or 0)
    length = float(length_m or 0)
    bars = int(num_bars or 0)
    if d <= 0 or length <= 0 or bars <= 0:
        return 0.0
    return round((d * d * length * bars) / 162.0, 4)


def _cutting_length_from_shape(formula_type, sides, manual_length):
    manual = float(manual_length or 0)
    if formula_type == "straight":
        return manual
    side_vals = []
    for s in sides or []:
        try:
            v = float(s)
            if v > 0:
                side_vals.append(v)
        except (TypeError, ValueError):
            continue
    if side_vals:
        return round(sum(side_vals) / 1000.0, 4)
    return manual


def _parse_dpr_measurement_payload(payload, unit):
    mtype = _unit_measurement_type(unit)
    result = {"type": mtype, "quantity": 0.0, "data": payload}
    if mtype == "volume":
        avg_l = _average_readings(payload.get("lengths") or [])
        avg_w = _average_readings(payload.get("widths") or [])
        avg_d = _average_readings(payload.get("depths") or [])
        qty = round(avg_l * avg_w * avg_d, 4)
        result["quantity"] = qty
        result["data"] = {
            "lengths": payload.get("lengths") or [],
            "widths": payload.get("widths") or [],
            "depths": payload.get("depths") or [],
            "avg_length": avg_l,
            "avg_width": avg_w,
            "avg_depth": avg_d,
        }
    elif mtype == "area":
        avg_l = _average_readings(payload.get("lengths") or [])
        avg_w = _average_readings(payload.get("widths") or [])
        qty = round(avg_l * avg_w, 4)
        result["quantity"] = qty
        result["data"] = {
            "lengths": payload.get("lengths") or [],
            "widths": payload.get("widths") or [],
            "avg_length": avg_l,
            "avg_width": avg_w,
        }
    elif mtype == "steel":
        lines = []
        total_qty = 0.0
        unit_norm = (unit or "").strip().upper()
        for line in payload.get("lines") or []:
            cutting_m = _cutting_length_from_shape(
                line.get("formula_type", "straight"),
                line.get("side_measurements") or [],
                line.get("cutting_length"),
            )
            weight_kg = _steel_bar_weight_kg(
                line.get("diameter_mm"),
                cutting_m,
                line.get("num_bars"),
            )
            if unit_norm == "MT":
                line_qty = round(weight_kg / 1000.0, 4)
            else:
                line_qty = weight_kg
            line["cutting_length_m"] = cutting_m
            line["quantity"] = line_qty
            lines.append(line)
            total_qty += line_qty
        result["quantity"] = round(total_qty, 4)
        result["data"] = {"lines": lines}
    else:
        try:
            result["quantity"] = round(float(payload.get("quantity") or 0), 4)
        except (TypeError, ValueError):
            result["quantity"] = 0.0
    return result


CLIENT_BILL_SQL = """
    SELECT m.*, p.project_code, p.project_name, p.client_id, p.private_client_name,
           c.company_name, c.client_name, c.gst_number, c.address AS client_address,
           COALESCE(bi.rate, 0) AS boq_rate,
           ROUND(m.calculated_quantity * COALESCE(bi.rate, 0), 2) AS bill_amount
    FROM dpr_measurements m
    LEFT JOIN projects p ON m.project_id = p.id
    LEFT JOIN clients c ON p.client_id = c.id
    LEFT JOIN boq_items bi ON m.boq_item_id = bi.id
"""


def _fetch_client_bill_rows(measurement_ids=None, pending_only=True):
    clauses = []
    params = []
    if pending_only:
        clauses.append("m.bill_client=1 AND m.billing_status='pending'")
    if measurement_ids:
        placeholders = ",".join("?" * len(measurement_ids))
        clauses.append(f"m.id IN ({placeholders})")
        params.extend(measurement_ids)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return query_db(
        CLIENT_BILL_SQL + where + " ORDER BY m.report_date DESC, m.id DESC",
        params,
    )


def _manpower_line_cost(mp_row):
    hours = float(mp_row.get("hours_worked") or 0)
    if hours <= 0:
        return 0.0
    subcontractor_id = mp_row.get("subcontractor_id")
    trade = (mp_row.get("trade_name") or "").strip()
    if subcontractor_id and trade:
        rate = get_subcontractor_manpower_rate(subcontractor_id, trade)
        if rate:
            rate_unit = (rate["rate_unit"] or "Day").strip()
            rate_amount = float(rate["rate_amount"] or 0)
            salary_amount = float(rate["salary_amount"] or 0)
            if rate_unit == "Hour":
                return round(hours * rate_amount, 2)
            working_hours = float(rate["working_hours"] or 8) or 8
            day_rate = rate_amount or salary_amount
            return round((hours / working_hours) * day_rate, 2)
    worker_id = mp_row.get("worker_id")
    if worker_id:
        worker = query_db(
            "SELECT salary_type, salary_amount, working_hours FROM workers WHERE id=?",
            (worker_id,),
            one=True,
        )
        if worker:
            working_hours = float(worker["working_hours"] or 8) or 8
            salary = float(worker["salary_amount"] or 0)
            if (worker["salary_type"] or "").strip() == "Hourly":
                return round(hours * salary, 2)
            return round((hours / working_hours) * salary, 2)
    return 0.0


def _push_dpr_to_project_costing(db, measurement_id):
    row = query_db(
        CLIENT_BILL_SQL + " WHERE m.id=?",
        (measurement_id,),
        one=True,
    )
    if not row:
        return False, "Measurement not found."
    measurement = dict(row)
    if not measurement["for_costing"]:
        return False, "Measurement is not flagged for costing."
    if measurement["costing_status"] == "linked":
        return False, "Already linked to Project Costing."

    mp_rows = query_db(
        "SELECT mp.*, s.subcontractor_name FROM dpr_manpower mp "
        "LEFT JOIN subcontractors s ON mp.subcontractor_id = s.id "
        "WHERE mp.measurement_id=?",
        (measurement_id,),
    )
    created_by = session.get("username", "")
    expense_ids = []
    total_amount = 0.0

    work_amount = float(measurement["bill_amount"] or 0)
    if work_amount > 0:
        work_desc = (
            f"DPR #{measurement_id}: {measurement['boq_number'] or ''} — "
            f"{measurement['boq_description'] or ''} "
            f"({measurement['calculated_quantity']} {measurement['unit']})"
        )
        if measurement.get("work_description"):
            work_desc = f"{measurement['work_description']} | {work_desc}"
        db.execute(
            "INSERT INTO project_expenses(project_id, expense_date, expense_category, amount, "
            "description, dpr_measurement_id, created_by, approval_status) VALUES(?,?,?,?,?,?,?,?)",
            (
                measurement["project_id"],
                measurement["report_date"],
                "DPR Work Progress",
                work_amount,
                work_desc,
                measurement_id,
                created_by,
                RECORD_PENDING_CHECKER,
            ),
        )
        expense_ids.append(db.execute("SELECT last_insert_rowid()").fetchone()[0])
        total_amount += work_amount

    for mp in mp_rows:
        mp_dict = dict(mp)
        amount = _manpower_line_cost(mp_dict)
        worker_label = mp_dict.get("worker_name") or "Worker"
        sub_label = mp_dict.get("subcontractor_name") or "Company"
        trade = mp_dict.get("trade_name") or "Manpower"
        desc = (
            f"DPR #{measurement_id} manpower — {sub_label}, {worker_label}, "
            f"{trade}, {mp_dict.get('hours_worked') or 0} hrs"
        )
        if mp_dict.get("remarks"):
            desc += f" ({mp_dict['remarks']})"
        db.execute(
            "INSERT INTO project_expenses(project_id, expense_date, expense_category, amount, "
            "description, dpr_measurement_id, created_by, approval_status) VALUES(?,?,?,?,?,?,?,?)",
            (
                measurement["project_id"],
                measurement["report_date"],
                f"DPR Manpower — {trade}",
                amount,
                desc,
                measurement_id,
                created_by,
                RECORD_PENDING_CHECKER,
            ),
        )
        expense_ids.append(db.execute("SELECT last_insert_rowid()").fetchone()[0])
        total_amount += amount

    if not expense_ids:
        return False, "No costing lines to create (add manpower or ensure BOQ rate exists)."

    for expense_id in expense_ids:
        create_approval_request(
            db, "project_expenses", expense_id, "project_expenses", created_by, session.get("user_id")
        )

    db.execute(
        "UPDATE dpr_measurements SET costing_status='linked' WHERE id=?",
        (measurement_id,),
    )
    db.commit()
    return True, f"Created {len(expense_ids)} expense line(s), total {total_amount:,.2f}."


def get_project_options_for_boq():
    return query_db(
        "SELECT id, project_code, project_name FROM projects "
        "WHERE status IS NULL OR status != 'Inactive' ORDER BY project_name"
    )


ATTENDANCE_WORKER_JOIN_SQL = (
    "LEFT JOIN workers w ON a.worker_id = w.id "
    "AND COALESCE(a.worker_source, 'worker') = 'worker' "
    "LEFT JOIN staff s ON a.worker_id = s.id AND a.worker_source = 'staff'"
)


def format_attendance_worker_ref(worker_id, worker_source=None):
    if worker_id is None or str(worker_id).strip() == "":
        return ""
    source = (worker_source or "worker").strip().lower()
    prefix = "s" if source == "staff" else "w"
    return f"{prefix}:{int(worker_id)}"


def parse_attendance_worker_ref(ref):
    value = (ref or "").strip()
    if not value:
        return None, "worker"
    if value.startswith("s:"):
        try:
            return int(value[2:]), "staff"
        except ValueError:
            return None, "staff"
    if value.startswith("w:"):
        try:
            return int(value[2:]), "worker"
        except ValueError:
            return None, "worker"
    try:
        return int(value), "worker"
    except ValueError:
        return None, "worker"


def get_attendance_worker_options():
    """Legacy combined list; prefer get_attendance_form_worker_data() for the form."""
    data = get_attendance_form_worker_data()
    return data["company_staff"]


def get_attendance_form_worker_data():
    """Company staff, subcontractors, and subcontractor workers for attendance form."""
    staff_rows = query_db(
        "SELECT id, employee_code AS worker_code, staff_name AS worker_name, photo "
        "FROM staff WHERE status IS NULL OR status = 'Active' "
        "ORDER BY staff_name, employee_code"
    )
    company_worker_rows = query_db(
        "SELECT id, worker_code, worker_name, photo FROM workers "
        "WHERE (status IS NULL OR status = 'Active') "
        "AND COALESCE(worker_category, 'Company Staff') != 'Sub Contractor Staff' "
        "ORDER BY worker_name, worker_code"
    )
    subcontractor_rows = query_db(
        "SELECT id, subcontractor_code, subcontractor_name FROM subcontractors "
        "WHERE status IS NULL OR status = 'Active' "
        "ORDER BY subcontractor_name"
    )
    subcontractor_worker_rows = query_db(
        "SELECT id, worker_code, worker_name, photo, subcontractor_id FROM workers "
        "WHERE (status IS NULL OR status = 'Active') "
        "AND COALESCE(worker_category, 'Company Staff') = 'Sub Contractor Staff' "
        "AND subcontractor_id IS NOT NULL "
        "ORDER BY worker_name, worker_code"
    )
    company_staff = []
    for row in staff_rows:
        item = dict(row)
        item["worker_source"] = "staff"
        item["ref"] = format_attendance_worker_ref(item["id"], "staff")
        company_staff.append(item)
    for row in company_worker_rows:
        item = dict(row)
        item["worker_source"] = "worker"
        item["ref"] = format_attendance_worker_ref(item["id"], "worker")
        company_staff.append(item)
    company_staff.sort(
        key=lambda item: (
            (item.get("worker_name") or "").lower(),
            (item.get("worker_code") or "").lower(),
        )
    )
    subcontractor_workers = []
    for row in subcontractor_worker_rows:
        item = dict(row)
        item["worker_source"] = "worker"
        item["ref"] = format_attendance_worker_ref(item["id"], "worker")
        subcontractor_workers.append(item)
    return {
        "company_staff": company_staff,
        "subcontractors": [dict(row) for row in subcontractor_rows],
        "subcontractor_workers": subcontractor_workers,
    }


def get_attendance_edit_worker_context(edit_record):
    """Derive staff type and subcontractor for attendance edit form."""
    if not edit_record:
        return {"staff_type": "", "subcontractor_id": ""}
    edit_record = dict(edit_record)
    if (edit_record.get("worker_source") or "worker") == "staff":
        return {"staff_type": "Company Staff", "subcontractor_id": ""}
    worker_row = query_db(
        "SELECT worker_category, subcontractor_id FROM workers WHERE id=?",
        (edit_record["worker_id"],),
        one=True,
    )
    if not worker_row:
        return {"staff_type": "Company Staff", "subcontractor_id": ""}
    worker_row = dict(worker_row)
    worker_category = (worker_row.get("worker_category") or "Company Staff").strip()
    if worker_category == "Sub Contractor Staff" and worker_row.get("subcontractor_id"):
        return {
            "staff_type": "Sub Contractor Staff",
            "subcontractor_id": str(worker_row["subcontractor_id"]),
        }
    return {"staff_type": "Company Staff", "subcontractor_id": ""}


def get_attendance_project_options():
    return query_db(
        "SELECT id, project_code, project_name FROM projects "
        "WHERE status IS NULL OR status != 'Inactive' ORDER BY project_name"
    )


def _parse_boq_line_items():
    descriptions = request.form.getlist("item_description[]")
    quantities = request.form.getlist("quantity[]")
    units = request.form.getlist("unit[]")
    rates = request.form.getlist("rate[]")
    lines = []
    row_count = max(len(descriptions), len(quantities), len(units), len(rates))
    for idx in range(min(row_count, MAX_BOQ_LINES)):
        desc = (descriptions[idx] if idx < len(descriptions) else "").strip()
        qty_raw = quantities[idx] if idx < len(quantities) else ""
        rate_raw = rates[idx] if idx < len(rates) else ""
        unit = (units[idx] if idx < len(units) else "").strip() or BOQ_UNITS[0]
        if unit not in BOQ_UNITS:
            unit = BOQ_UNITS[0]
        if not desc and not str(qty_raw).strip() and not str(rate_raw).strip():
            continue
        if not desc:
            return None, "Each BOQ line item must have a description."
        try:
            qty = float(qty_raw or 0)
            rate = float(rate_raw or 0)
        except ValueError:
            return None, "Enter valid quantity and rate for all BOQ line items."
        lines.append({
            "line_no": len(lines) + 1,
            "item_description": desc,
            "quantity": qty,
            "unit": unit,
            "rate": rate,
            "amount": round(qty * rate, 2),
        })
    return lines, None


DEFAULT_DEPARTMENTS = [
    "Head Office", "Accounts", "Site Operations", "Store", "Purchase",
    "HR & Payroll", "Projects", "Management",
]


def ensure_department_master(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS departments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department_name TEXT UNIQUE,
            description TEXT,
            status TEXT DEFAULT 'Active'
        )
    """)
    cols = [row[1] for row in db.execute("PRAGMA table_info(departments)").fetchall()]
    if "department_name" not in cols:
        db.execute("ALTER TABLE departments ADD COLUMN department_name TEXT")
    if "description" not in cols:
        db.execute("ALTER TABLE departments ADD COLUMN description TEXT")
    if "status" not in cols:
        db.execute("ALTER TABLE departments ADD COLUMN status TEXT DEFAULT 'Active'")
    row = db.execute("SELECT COUNT(*) AS count FROM departments").fetchone()
    if int(row["count"]) == 0:
        db.executemany(
            "INSERT INTO departments(department_name, status) VALUES(?, 'Active')",
            [(dept,) for dept in DEFAULT_DEPARTMENTS],
        )
        db.commit()


def get_departments():
    ensure_department_master(get_db())
    rows = query_db("SELECT department_name FROM departments WHERE status='Active' ORDER BY department_name")
    return [row["department_name"] for row in rows] or DEFAULT_DEPARTMENTS


def _table_exists(db, table):
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _ensure_column(db, table, column, col_type):
    if not _table_exists(db, table):
        return
    cols = [row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def _create_transaction_tables(cursor):
    tables = [
        """CREATE TABLE IF NOT EXISTS material_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, request_date TEXT, item_name TEXT,
            quantity REAL, unit TEXT, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
        """CREATE TABLE IF NOT EXISTS purchase_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, request_date TEXT, item_description TEXT,
            quantity REAL, estimated_cost REAL, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
        """CREATE TABLE IF NOT EXISTS payroll_records(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT, department TEXT, total_amount REAL,
            employee_count INTEGER, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker')""",
        """CREATE TABLE IF NOT EXISTS daily_timesheets(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, timesheet_date TEXT, supervisor TEXT,
            total_workers INTEGER, total_hours REAL, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
        """CREATE TABLE IF NOT EXISTS project_expenses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, expense_date TEXT, expense_category TEXT,
            amount REAL, description TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
        """CREATE TABLE IF NOT EXISTS head_office_expenses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_date TEXT, expense_category TEXT, amount REAL,
            department TEXT, description TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker')""",
        """CREATE TABLE IF NOT EXISTS subcontract_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, subcontractor_id INTEGER, work_description TEXT,
            contract_amount REAL, start_date TEXT, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id),
            FOREIGN KEY(subcontractor_id) REFERENCES subcontractors(id))""",
        """CREATE TABLE IF NOT EXISTS boq_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, boq_date TEXT, item_code TEXT, item_description TEXT,
            quantity REAL, unit TEXT, rate REAL, amount REAL, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
        """CREATE TABLE IF NOT EXISTS dpr_entries(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, report_date TEXT, prepared_by TEXT,
            work_done TEXT, manpower_count INTEGER, material_used TEXT,
            issues TEXT, progress_percent REAL, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
        """CREATE TABLE IF NOT EXISTS manager_tasks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, task_date TEXT, manager_name TEXT,
            action_item TEXT, priority TEXT, target_date TEXT, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
        """CREATE TABLE IF NOT EXISTS account_transactions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_type TEXT, project_id INTEGER, transaction_date TEXT,
            party_name TEXT, account_head TEXT, amount REAL, payment_mode TEXT,
            reference_no TEXT, tax_percent REAL, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
        """CREATE TABLE IF NOT EXISTS leave_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_name TEXT, leave_type TEXT, from_date TEXT, to_date TEXT,
            days REAL, reason TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker')""",
        """CREATE TABLE IF NOT EXISTS store_issues(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, issue_date TEXT, item_name TEXT,
            quantity REAL, unit TEXT, issued_to TEXT, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
        """CREATE TABLE IF NOT EXISTS store_receipts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, receipt_date TEXT, item_name TEXT,
            quantity REAL, unit TEXT, supplier TEXT, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
    ]
    for sql in tables:
        cursor.execute(sql)


def init_db():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT,
            status TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS staff(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT,
            staff_name TEXT,
            mobile TEXT,
            email TEXT,
            department TEXT,
            designation TEXT,
            salary_type TEXT,
            salary_amount REAL,
            ot_applicable TEXT,
            working_hours REAL,
            joining_date TEXT,
            photo TEXT,
            status TEXT
        )
    """)
    cursor.execute("""
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
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS departments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department_name TEXT UNIQUE,
            description TEXT,
            status TEXT DEFAULT 'Active'
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT,
            company_name TEXT,
            mobile TEXT,
            email TEXT,
            address TEXT,
            gst_number TEXT,
            status TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT,
            client_id INTEGER,
            location TEXT,
            start_date TEXT,
            end_date TEXT,
            project_manager TEXT,
            budget REAL,
            status TEXT,
            FOREIGN KEY(client_id) REFERENCES clients(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_code TEXT,
            worker_name TEXT,
            mobile TEXT,
            aadhaar_number TEXT,
            photo TEXT,
            worker_category TEXT,
            designation TEXT,
            salary_type TEXT,
            salary_amount REAL,
            ot_applicable TEXT,
            working_hours REAL,
            subcontractor_id INTEGER,
            project_id INTEGER,
            joining_date TEXT,
            status TEXT,
            FOREIGN KEY(subcontractor_id) REFERENCES subcontractors(id),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER,
            project_id INTEGER,
            attendance_date TEXT,
            in_time TEXT,
            out_time TEXT,
            break_hours REAL,
            total_hours REAL,
            ot_hours REAL,
            status TEXT,
            FOREIGN KEY(worker_id) REFERENCES workers(id),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS petty_cash(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            expense_date TEXT,
            expense_type TEXT,
            amount REAL,
            payment_mode TEXT,
            remarks TEXT,
            created_by TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS salary(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER,
            month TEXT,
            total_days INTEGER,
            normal_wage REAL,
            ot_amount REAL,
            advance_deduction REAL,
            final_salary REAL,
            payment_status TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(worker_id) REFERENCES workers(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS designations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            designation_name TEXT UNIQUE,
            description TEXT,
            status TEXT DEFAULT 'Active'
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflow_master(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_name TEXT NOT NULL,
            module_id TEXT UNIQUE NOT NULL,
            workflow_role_mapping TEXT,
            maker_designation_id INTEGER,
            checker_designation_id INTEGER,
            approver_designation_id INTEGER,
            status TEXT DEFAULT 'Active',
            FOREIGN KEY(maker_designation_id) REFERENCES designations(id),
            FOREIGN KEY(checker_designation_id) REFERENCES designations(id),
            FOREIGN KEY(approver_designation_id) REFERENCES designations(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS approval_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id TEXT NOT NULL,
            record_id INTEGER NOT NULL,
            record_table TEXT NOT NULL,
            current_stage TEXT DEFAULT 'checker',
            workflow_status TEXT DEFAULT 'pending_checker',
            maker_user_id INTEGER,
            checker_user_id INTEGER,
            approver_user_id INTEGER,
            maker_action_at TEXT,
            checker_action_at TEXT,
            approver_action_at TEXT,
            rejection_reason TEXT,
            created_by TEXT,
            created_at TEXT,
            UNIQUE(module_id, record_id, record_table)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            notification_type TEXT,
            module_id TEXT,
            record_id INTEGER,
            record_table TEXT,
            is_read INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS approval_audit(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            approval_request_id INTEGER,
            module_id TEXT,
            record_id INTEGER,
            record_table TEXT,
            action TEXT,
            actor_user_id INTEGER,
            actor_username TEXT,
            remarks TEXT,
            created_at TEXT,
            FOREIGN KEY(approval_request_id) REFERENCES approval_requests(id)
        )
    """)
    _ensure_column(db, "users", "designation_id", "INTEGER")
    _ensure_column(db, "users", "workflow_role", "TEXT")
    _ensure_column(db, "users", "reporting_manager", "TEXT")
    _ensure_column(db, "users", "employee_name", "TEXT")
    _ensure_column(db, "users", "department", "TEXT")
    _ensure_column(db, "users", "status", "TEXT DEFAULT 'Active'")
    _ensure_column(db, "users", "role", "TEXT")
    db.execute(
        "UPDATE users SET status='Active' WHERE status IS NULL OR TRIM(status)=''"
    )
    _ensure_column(db, "staff", "designation_id", "INTEGER")
    _ensure_column(db, "staff", "reporting_manager", "TEXT")
    _ensure_column(db, "staff", "workflow_role", "TEXT")
    _ensure_column(db, "staff", "aadhaar_number", "TEXT")
    _ensure_column(db, "staff", "pan_number", "TEXT")
    _ensure_column(db, "staff", "bank_account", "TEXT")
    _ensure_column(db, "staff", "bank_name", "TEXT")
    _ensure_column(db, "staff", "ifsc_code", "TEXT")
    _ensure_column(db, "staff", "branch_name", "TEXT")
    _ensure_column(db, "staff", "id_proof", "TEXT")
    _ensure_column(db, "staff", "aadhaar_document", "TEXT")
    _ensure_column(db, "staff", "pan_document", "TEXT")
    _ensure_column(db, "workers", "worker_code", "TEXT")
    _ensure_column(db, "workers", "aadhaar_number", "TEXT")
    _ensure_column(db, "workers", "worker_category", "TEXT DEFAULT 'Company Staff'")
    _ensure_column(db, "workers", "subcontractor_id", "INTEGER")
    db.execute(
        "UPDATE workers SET worker_category='Company Staff' "
        "WHERE worker_category IS NULL OR TRIM(worker_category)=''"
    )
    _ensure_column(db, "workers", "bank_account", "TEXT")
    _ensure_column(db, "workers", "bank_name", "TEXT")
    _ensure_column(db, "workers", "ifsc_code", "TEXT")
    _ensure_column(db, "workers", "branch_name", "TEXT")
    _ensure_column(db, "workers", "pan_number", "TEXT")
    _ensure_column(db, "workers", "id_proof", "TEXT")
    _ensure_column(db, "workers", "aadhaar_document", "TEXT")
    _ensure_column(db, "workers", "pan_document", "TEXT")
    _ensure_column(db, "approval_requests", "checker_comment", "TEXT")
    _ensure_column(db, "approval_requests", "approver_comment", "TEXT")
    _ensure_column(db, "petty_cash", "approval_status", "TEXT DEFAULT 'Pending Checker'")
    _ensure_column(db, "attendance", "approval_status", "TEXT DEFAULT 'Pending Checker'")
    _ensure_column(db, "attendance", "worker_source", "TEXT DEFAULT 'worker'")
    _ensure_column(db, "notifications", "notification_type", "TEXT")
    _ensure_column(db, "notifications", "module_id", "TEXT")
    _ensure_column(db, "notifications", "record_id", "INTEGER")
    _ensure_column(db, "notifications", "record_table", "TEXT")
    _ensure_column(db, "approval_audit", "actor_username", "TEXT")
    _ensure_column(db, "salary", "approval_status", "TEXT DEFAULT 'Pending Checker'")
    _ensure_column(db, "clients", "client_code", "TEXT")
    _ensure_column(db, "clients", "contact_person", "TEXT")
    _ensure_column(db, "clients", "pan_number", "TEXT")
    _ensure_column(db, "projects", "project_code", "TEXT")
    _ensure_column(db, "projects", "project_type", "TEXT")
    _ensure_column(db, "projects", "gov_department", "TEXT")
    _ensure_column(db, "projects", "agreement_number", "TEXT")
    _ensure_column(db, "projects", "agreement_date", "TEXT")
    _ensure_column(db, "projects", "completion_time", "TEXT")
    _ensure_column(db, "projects", "quoted_amount", "REAL")
    _ensure_column(db, "projects", "security_deposit_pct", "REAL")
    _ensure_column(db, "projects", "guarantee_type", "TEXT")
    _ensure_column(db, "projects", "bank_guarantee_number", "TEXT")
    _ensure_column(db, "projects", "bank_guarantee_issued_date", "TEXT")
    _ensure_column(db, "projects", "bank_guarantee_expiry_date", "TEXT")
    _ensure_column(db, "projects", "bank_guarantee_amount", "REAL")
    _ensure_column(db, "projects", "treasury_deposit_number", "TEXT")
    _ensure_column(db, "projects", "security_deposit_amount", "REAL")
    _ensure_column(db, "projects", "security_deposit_issued_date", "TEXT")
    _ensure_column(db, "projects", "security_deposit_maturity_date", "TEXT")
    _ensure_column(db, "projects", "agreement_document", "TEXT")
    _ensure_column(db, "projects", "bank_guarantee_document", "TEXT")
    _ensure_column(db, "projects", "security_deposit_document", "TEXT")
    _ensure_column(db, "projects", "work_order_number", "TEXT")
    _ensure_column(db, "projects", "work_order_date", "TEXT")
    _ensure_column(db, "projects", "work_order_amount", "REAL")
    _ensure_column(db, "projects", "project_contact_person", "TEXT")
    _ensure_column(db, "projects", "private_client_name", "TEXT")
    _ensure_column(db, "projects", "work_order_document", "TEXT")
    _ensure_column(db, "projects", "approved_total_amount", "REAL")
    db.execute(
        "UPDATE projects SET approved_total_amount = budget "
        "WHERE approved_total_amount IS NULL AND budget IS NOT NULL"
    )
    _ensure_column(db, "users", "staff_id", "INTEGER")
    _ensure_column(db, "subcontractors", "subcontractor_code", "TEXT")
    _ensure_column(db, "subcontractors", "date_of_birth", "TEXT")
    _ensure_column(db, "subcontractors", "id_number", "TEXT")
    _ensure_column(db, "subcontractors", "id_document", "TEXT")
    _ensure_column(db, "subcontractors", "photo", "TEXT")
    _ensure_column(db, "subcontractors", "pan_number", "TEXT")
    _ensure_column(db, "subcontractors", "pan_document", "TEXT")
    _ensure_column(db, "subcontractors", "bank_account", "TEXT")
    _ensure_column(db, "subcontractors", "bank_name", "TEXT")
    _ensure_column(db, "subcontractors", "ifsc_code", "TEXT")
    _ensure_column(db, "subcontractors", "branch_name", "TEXT")
    _ensure_column(db, "subcontractors", "rate_type", "TEXT")
    _ensure_column(db, "subcontractors", "id_proof", "TEXT")
    ensure_subcontractor_rate_tables(db)
    backfill_subcontractor_codes(db)
    ensure_user_maker_assignments_table(db)
    ensure_boq_master_table(db)
    _create_transaction_tables(cursor)
    ensure_dpr_measurement_tables(db)
    ensure_staff_hr_tables(db)
    ensure_staff_bonus_table(db)
    ensure_app_settings_table(db)
    _ensure_column(db, "project_expenses", "dpr_measurement_id", "INTEGER")
    _ensure_column(db, "boq_items", "boq_id", "INTEGER")
    _ensure_column(db, "boq_items", "line_no", "INTEGER")
    db.commit()
    ensure_department_master(db)
    seed_workflow_master(db)
    migrate_workflow_statuses(db)
    sync_workflow_designations(db)
    db.commit()
    cursor.execute("SELECT * FROM users LIMIT 1")
    if cursor.fetchone() is None:
        cursor.execute(
            "INSERT INTO users(username, password, role, status, employee_name, department, workflow_role) "
            "VALUES(?,?,?,?,?,?,?)",
            ("admin", "admin", "Admin", "Active", "System Administrator", "Head Office", "Administrator"),
        )
        db.commit()
    if not os.environ.get("MAXEK_SKIP_DEMO_SEED"):
        seed_demo_users(db)
        db.commit()


def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def login_required(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapper


def is_admin_user():
    if not session.get("user_id"):
        return False
    wf = (session.get("workflow_role") or "").lower()
    role = (session.get("role") or "").lower()
    if wf == "administrator" or role in ("admin", "administrator"):
        return True
    return is_admin_role(get_db(), session.get("user_id"), session.get("role"))


def admin_required(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        if not is_admin_user():
            flash("Administrator access required.")
            return redirect(url_for("dashboard"))
        return fn(*args, **kwargs)

    return wrapper


MODULE_ROUTES = {
    "petty_cash": "petty_cash",
    "material_request": "material_request",
    "purchase_request": "purchase_request",
    "payroll": "salary",
    "daily_timesheet": "attendance",
    "project_expenses": "project_expenses",
    "head_office_expenses": "head_office_expenses",
    "subcontract": "subcontract_request",
    "boq": "boq_management",
    "dpr": "dpr_entry",
    "manager_tool": "manager_tool",
    "account_receipt": "account_receipts",
    "account_payment": "account_payments",
    "account_gst": "account_gst",
    "account_tds": "account_tds",
    "leave_request": "leave_request",
    "store_issue": "store_issue",
    "store_receipt": "store_receipt",
}


def _workflow_view_context(module_id, record_id, record_table, approval_status):
    db = get_db()
    user_id = session.get("user_id")
    admin = is_admin_user()
    history = get_approval_history(db, module_id, record_id, record_table)
    edit_role = get_edit_role_for_user(db, user_id, module_id, approval_status, admin)
    req = get_approval_request(db, module_id, record_id, record_table)
    return {
        "history": history,
        "edit_role": edit_role,
        "can_reopen": admin and approval_status == RECORD_APPROVED and req,
        "approval_id": req["id"] if req else None,
    }


def _enrich_approval_items(db, items):
    enriched = []
    for item in items:
        row = dict(item)
        table = row.get("record_table")
        if table in ALLOWED_RECORD_TABLES:
            rec = db.execute(
                f"SELECT approval_status FROM {table} WHERE id=?",
                (row["record_id"],),
            ).fetchone()
            row["record_status"] = rec["approval_status"] if rec else WORKFLOW_STATUS.get(
                row.get("workflow_status"), row.get("workflow_status")
            )
        else:
            row["record_status"] = WORKFLOW_STATUS.get(
                row.get("workflow_status"), row.get("workflow_status")
            )
        row["history"] = get_approval_history(
            db, row.get("module_id"), row["record_id"], row.get("record_table")
        )
        enriched.append(row)
    return enriched


def _history_for_record(module_id, record_id, record_table):
    return get_approval_history(get_db(), module_id, record_id, record_table)


NAV_GROUPS = [
    {
        "label": "Dashboard",
        "icon": "fa-gauge-high",
        "slug": "dashboard",
        "items": [
            {"endpoint": "dashboard", "label": "Overview", "active_endpoints": ["dashboard"]},
            {"endpoint": "dashboard_choice_b", "label": "Operations View", "active_endpoints": ["dashboard_choice_b"]},
        ],
    },
    {
        "label": "Projects",
        "icon": "fa-layer-group",
        "slug": "projects",
        "items": [
            {"endpoint": "projects", "label": "Project Creation", "active_endpoints": ["projects"]},
            {"endpoint": "boq_management", "label": "BOQ Creation", "active_endpoints": ["boq_management"]},
            {"endpoint": "dpr_entry", "label": "DPR Entry", "active_endpoints": ["dpr_entry", "dpr_client_bill_pending", "dpr_costing_pending"]},
            {"endpoint": "project_expenses", "label": "Project Costing", "active_endpoints": ["project_expenses"]},
            {"endpoint": "reports", "label": "Project Reports", "active_endpoints": ["reports", "workflow_audit_report"]},
        ],
    },
    {
        "label": "Workforce",
        "icon": "fa-users",
        "slug": "workforce",
        "items": [
            {"endpoint": "staff", "label": "Employees", "active_endpoints": ["staff"]},
            {"endpoint": "staff_bonus", "label": "Staff Bonus", "active_endpoints": ["staff_bonus"]},
            {"endpoint": "attendance", "label": "Attendance", "active_endpoints": ["attendance"]},
            {"endpoint": "timesheet", "label": "Timesheet", "active_endpoints": ["timesheet"]},
            {"endpoint": "salary", "label": "Salary Processing", "active_endpoints": ["salary"]},
        ],
    },
    {
        "label": "Subcontract",
        "icon": "fa-people-group",
        "slug": "subcontract",
        "items": [
            {"endpoint": "subcontractors", "label": "Subcontractors", "active_endpoints": ["subcontractors"]},
            {"endpoint": "workers", "label": "Worker Creation", "anchor": "add-worker", "active_endpoints": ["workers"]},
            {"endpoint": "subcontract_request", "label": "Bills & Payments", "active_endpoints": ["subcontract_request"]},
        ],
    },
    {
        "label": "Store & Procurement",
        "icon": "fa-warehouse",
        "slug": "store-procurement",
        "items": [
            {"endpoint": "store", "label": "Store Dashboard", "active_endpoints": ["store"]},
            {"endpoint": "material_request", "label": "Material Request", "active_endpoints": ["material_request"]},
            {"endpoint": "purchase_request", "label": "Purchase Request", "active_endpoints": ["purchase_request"]},
            {"endpoint": "purchase", "label": "Purchase Order", "active_endpoints": ["purchase"]},
            {"endpoint": "store_receipt", "label": "Delivery / GRN", "active_endpoints": ["store_receipt"]},
            {"endpoint": "store_issue", "label": "Store Issue", "active_endpoints": ["store_issue"]},
            {"endpoint": "inventory", "label": "Inventory Stock", "active_endpoints": ["inventory"]},
        ],
    },
    {
        "label": "Accounts",
        "icon": "fa-landmark",
        "slug": "accounts",
        "items": [
            {"endpoint": "petty_cash", "label": "Petty Cash", "active_endpoints": ["petty_cash"]},
            {"endpoint": "head_office_expenses", "label": "Daily Expenses", "active_endpoints": ["head_office_expenses", "project_expenses"]},
            {"endpoint": "account_receipts", "label": "Receipts", "active_endpoints": ["account_receipts"]},
            {"endpoint": "account_payments", "label": "Payments", "active_endpoints": ["account_payments"]},
            {"endpoint": "cash_book", "label": "Cash Book", "active_endpoints": ["cash_book"]},
            {"endpoint": "bank_book", "label": "Bank Book", "active_endpoints": ["bank_book"]},
            {"endpoint": "account_gst", "label": "GST", "active_endpoints": ["account_gst"]},
            {"endpoint": "account_tds", "label": "TDS", "active_endpoints": ["account_tds"]},
            {"endpoint": "ledger", "label": "Ledger", "active_endpoints": ["ledger"]},
            {"endpoint": "reports", "label": "Accounts Reports", "active_endpoints": ["reports"]},
        ],
    },
    {
        "label": "Approvals",
        "icon": "fa-clipboard-check",
        "slug": "approvals",
        "items": [
            {"endpoint": "approvals", "label": "Approval Center", "active_endpoints": ["approvals", "approval_action"]},
        ],
    },
    {
        "label": "Settings",
        "icon": "fa-gear",
        "slug": "settings",
        "items": [
            {"endpoint": "user_settings", "label": "Users", "active_endpoints": ["user_settings"]},
            {"endpoint": "settings", "label": "Company & Departments", "active_endpoints": ["settings"]},
            {"endpoint": "workflow_settings", "label": "Workflow Settings", "active_endpoints": ["workflow_settings", "workflow_matrix"]},
        ],
    },
]

NAV_ITEMS = [
    item
    for group in NAV_GROUPS
    for item in (
        group.get("items")
        or [
            {
                "endpoint": group.get("endpoint"),
                "label": group["label"],
                "icon": group["icon"],
                "active_endpoints": group.get("active_endpoints", []),
            }
        ]
    )
]


def get_nav_group_by_slug(slug):
    for group in NAV_GROUPS:
        if group.get("slug") == slug:
            return group
    return None


def active_nav_group(endpoint, nav_slug=None):
    if endpoint == "department_hub" and nav_slug:
        group = get_nav_group_by_slug(nav_slug)
        if group:
            return group
    for group in NAV_GROUPS:
        for item in group.get("items", []):
            if endpoint in item.get("active_endpoints", []):
                return group
        if endpoint in group.get("active_endpoints", []):
            return group
    return NAV_GROUPS[0]


def get_approval_widgets():
    if not session.get("user_id"):
        return {"maker": 0, "checker": 0, "approver": 0}
    return get_pending_counts(get_db(), session.get("user_id"), is_admin_user())


@app.context_processor
def inject_maxek_layout():
    if not session.get("user_id"):
        return {}
    username = session.get("username") or "Administrator"
    user_id = session.get("user_id")
    db = get_db()
    widgets = get_pending_counts(db, user_id, is_admin_user())
    dashboard_counters = get_dashboard_counters(db, user_id, username, is_admin_user())
    approval_summary = get_approval_summary(db)
    workflow_caps = user_workflow_capabilities(db, user_id, is_admin_user())
    notifs = get_notifications(db, user_id, limit=10, unread_only=True)
    approval_total = widgets["maker"] + widgets["checker"] + widgets["approver"]
    nav_slug = request.view_args.get("slug") if request.endpoint == "department_hub" else None
    current_nav_group = active_nav_group(request.endpoint, nav_slug)
    return {
        "nav_groups": NAV_GROUPS,
        "nav_items": NAV_ITEMS,
        "current_nav_group": current_nav_group,
        "timestamp": format_app_datetime(),
        "app_timezone": get_app_setting(get_db(), "timezone", "Asia/Kolkata"),
        "admin_initial": username[0].upper(),
        "branches": ["Head Office", "Chennai Site", "Walajabad Unit"],
        "selected_branch": session.get("branch", "Head Office"),
        "notification_count": len(notifs) or approval_total,
        "approval_total": approval_total,
        "approval_widgets": widgets,
        "dashboard_counters": dashboard_counters,
        "approval_summary": approval_summary,
        "workflow_caps": workflow_caps,
        "user_notifications": notifs,
        "display_status": display_status,
        "maker_status_message": maker_status_message,
    }


@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        remember = request.form.get("remember") == "on"
        user = authenticate_user(get_db(), username, password)
        if user:
            session.clear()
            session["user_id"] = get_user_id(user)
            session["username"] = user["username"]
            session["role"] = _row_val(user, "role")
            session["workflow_role"] = _row_val(user, "workflow_role")
            session["employee_name"] = get_user_display_name(user)
            if remember:
                session.permanent = True
                app.permanent_session_lifetime = timedelta(days=30)
            return redirect(url_for("dashboard"))
        flash("Invalid username or password, or account is inactive.")
    return render_template("login.html", app_version=APP_VERSION)


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        user = query_db("SELECT * FROM users WHERE username=?", (username,), one=True)
        if user:
            flash("Password reset request received. Contact your system administrator.")
        else:
            flash("If that username exists, an administrator will reset your password.")
        return redirect(url_for("login"))
    return render_template("forgot_password.html", app_version=APP_VERSION)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/department/<slug>")
@login_required
def department_hub(slug):
    group = get_nav_group_by_slug(slug)
    if not group:
        flash("Department not found.")
        return redirect(url_for("dashboard"))
    items = group.get("items") or []
    if items:
        first = items[0]
        target = url_for(first["endpoint"])
        if first.get("anchor"):
            target = f"{target}#{first['anchor']}"
        return redirect(target)
    return render_template("department_hub.html", nav_group=group)


def build_system_rows():
    rows = []
    for item in get_workflow_queue(get_db(), limit=10):
        status = item.get("workflow_status") or "pending_checker"
        status_label = display_status_from_workflow(status, "maker")
        if status in ("pending_checker", "rejected_checker"):
            priority, priority_class = "High", "high"
            action_label = "Review"
        elif status == "pending_approval":
            priority, priority_class = "Medium", "medium"
            action_label = "Approve"
        else:
            priority, priority_class = "Low", "low"
            action_label = "View"
        pill = "active" if status == "approved" else "pending"
        module_code = (item.get("module_id") or "WF").upper().replace("_", "")[:3]
        created = item.get("created_at") or "—"
        if len(created) >= 10:
            parts = created[:10].split("-")
            if len(parts) == 3:
                created = f"{parts[2]}/{parts[1]}/{parts[0]}"
        rows.append(
            {
                "ref": f"{module_code}-{item['record_id']}",
                "label": item.get("module_name") or item["module_id"],
                "date_created": created,
                "priority": priority,
                "priority_class": priority_class,
                "submitted_by": item.get("created_by") or item.get("maker_designation") or "—",
                "status": pill,
                "status_label": status_label,
                "action_url": url_for("approvals"),
                "action_label": action_label,
            }
        )
    return rows


def get_dashboard_stats(db):
    """Aggregate KPI and chart data for the home dashboard."""
    total_projects = query_db("SELECT COUNT(*) AS count FROM projects", one=True)["count"]
    active_projects = query_db(
        "SELECT COUNT(*) AS count FROM projects WHERE status='Active'", one=True
    )["count"]
    active_workers = query_db(
        "SELECT COUNT(*) AS count FROM workers WHERE status='Active'", one=True
    )["count"]
    active_staff = query_db(
        "SELECT COUNT(*) AS count FROM staff WHERE status='Active'", one=True
    )["count"]
    pending_mrs = 0
    try:
        pending_mrs = db.execute(
            "SELECT COUNT(*) AS c FROM material_requests "
            "WHERE approval_status IN ('Pending Checker', 'Pending Approval')"
        ).fetchone()["c"]
    except Exception:
        pass
    workflow_tasks = db.execute(
        "SELECT COUNT(*) AS c FROM approval_requests "
        "WHERE workflow_status NOT IN ('approved')"
    ).fetchone()["c"]

    featured = query_db(
        "SELECT project_name, location, status FROM projects "
        "WHERE status='Active' ORDER BY id DESC LIMIT 1",
        one=True,
    )
    progress_pct = 80
    if featured and total_projects:
        progress_pct = min(95, 50 + active_projects * 10)

    attendance_rows = query_db(
        "SELECT attendance_date, COUNT(*) AS cnt FROM attendance "
        "WHERE attendance_date >= date('now', '-6 days') "
        "GROUP BY attendance_date ORDER BY attendance_date ASC"
    )
    day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    counts_by_day = [row["cnt"] for row in attendance_rows]
    while len(counts_by_day) < 7:
        counts_by_day.append(0)
    counts_by_day = counts_by_day[-7:]
    max_cnt = max(counts_by_day) if counts_by_day else 1
    if max_cnt == 0:
        max_cnt = 1
    attendance_bars = []
    for i, label in enumerate(day_labels):
        cnt = counts_by_day[i] if i < len(counts_by_day) else 0
        attendance_bars.append(
            {
                "label": label,
                "count": cnt,
                "height": int((cnt / max_cnt) * 100) if cnt else 8,
            }
        )

    present_today = 0
    try:
        present_today = db.execute(
            "SELECT COUNT(*) AS c FROM attendance WHERE attendance_date=date('now') AND status='Present'"
        ).fetchone()["c"]
    except Exception:
        pass

    health_score = min(100, 40 + active_projects * 10 + min(active_workers, 30))
    health_segments = [
        {"label": "Product Dev", "pct": min(95, 60 + active_projects * 5), "color": "#3B82F6"},
        {"label": "Operations", "pct": min(90, 30 + active_workers), "color": "#10B981"},
        {"label": "Site Logistics", "pct": min(85, 20 + pending_mrs * 8), "color": "#F59E0B"},
    ]

    return {
        "total_projects": total_projects,
        "active_projects": active_projects,
        "active_workers": active_workers,
        "active_staff": active_staff,
        "pending_mrs": pending_mrs,
        "workflow_tasks": workflow_tasks,
        "featured_project": featured,
        "progress_pct": progress_pct,
        "attendance_bars": attendance_bars,
        "present_today": present_today or active_workers,
        "health_score": health_score,
        "health_segments": health_segments,
    }


def render_choice_b_dashboard():
    db = get_db()
    user_id = session.get("user_id")
    admin = is_admin_user()
    stats = get_dashboard_stats(db)
    counts = {
        "staff": stats["active_staff"],
        "workers": stats["active_workers"],
        "projects": stats["total_projects"],
    }
    approval_widgets = get_pending_counts(db, user_id, admin)
    system_rows = build_system_rows()
    total_pending = (
        approval_widgets["maker"]
        + approval_widgets["checker"]
        + approval_widgets["approver"]
    )
    username = session.get("username") or "Administrator"
    dashboard_counters = get_dashboard_counters(db, user_id, username, admin)
    approval_summary = get_approval_summary(db)
    recent_activities = get_recent_activities(db, limit=12)
    user_notifications = get_notifications(db, user_id, limit=8, unread_only=False)
    return render_template(
        "dashboard.html",
        counts=counts,
        stats=stats,
        approval_widgets=approval_widgets,
        dashboard_counters=dashboard_counters,
        approval_summary=approval_summary,
        recent_activities=recent_activities,
        user_notifications=user_notifications,
        system_rows=system_rows,
        alert_count=total_pending,
        welcome_name=session.get("employee_name") or (
            username.title() if username.islower() else username
        ),
    )


@app.route("/dashboard")
@login_required
def dashboard():
    return render_choice_b_dashboard()


@app.route("/dashboard/choice-b")
@login_required
def dashboard_choice_b():
    return render_choice_b_dashboard()


@app.route("/staff", methods=["GET", "POST"])
@login_required
def staff():
    db = get_db()
    prepare_staff_page_db(db)
    edit_id = request.args.get("edit", type=int)
    editing_staff = None
    editing_components = []
    editing_travel_tiers = []
    editing_salary_increments = []
    if edit_id:
        editing_staff = db.execute("SELECT * FROM staff WHERE id=?", (edit_id,)).fetchone()
        if not editing_staff:
            flash("Employee record not found.")
            return redirect(url_for("staff"))
        editing_components = _fetch_staff_salary_components(db, edit_id)
        editing_travel_tiers = _fetch_staff_travel_tiers(db, edit_id)
        editing_salary_increments = _fetch_staff_salary_increments(db, edit_id)
    designations = query_db(
        "SELECT id, designation_name FROM designations WHERE status='Active' ORDER BY designation_name"
    )
    departments = get_departments()
    staff_list = query_db("SELECT staff_name FROM staff WHERE status='Active' ORDER BY staff_name")
    if request.method == "POST":
        form_action = request.form.get("form_action", "").strip()
        if form_action == "add_increment":
            inc_staff_id = request.form.get("staff_id", "").strip()
            effective_date = request.form.get("effective_date", "").strip()
            new_amount_raw = request.form.get("new_salary_amount", "").strip()
            remarks = request.form.get("increment_remarks", "").strip()
            if not inc_staff_id:
                flash("Employee not found for increment.")
                return redirect(url_for("staff"))
            staff_row = db.execute("SELECT * FROM staff WHERE id=?", (inc_staff_id,)).fetchone()
            if not staff_row:
                flash("Employee not found.")
                return redirect(url_for("staff"))
            try:
                new_amount = float(new_amount_raw or 0)
            except ValueError:
                flash("Enter a valid new salary amount.")
                return redirect(url_for("staff", edit=inc_staff_id) + "#salary-increment")
            if new_amount <= 0:
                flash("New salary must be greater than zero.")
                return redirect(url_for("staff", edit=inc_staff_id) + "#salary-increment")
            previous = float(staff_row["salary_amount"] or 0)
            increment_amt = round(new_amount - previous, 2)
            created_at = get_app_now(db).strftime("%Y-%m-%d %H:%M:%S")
            db.execute(
                "INSERT INTO staff_salary_increments(staff_id, effective_date, previous_amount, "
                "new_amount, increment_amount, remarks, created_by, created_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (
                    inc_staff_id,
                    effective_date or get_app_now(db).strftime("%Y-%m-%d"),
                    previous,
                    new_amount,
                    increment_amt,
                    remarks,
                    session.get("username", ""),
                    created_at,
                ),
            )
            db.execute(
                "UPDATE staff SET salary_amount=? WHERE id=?",
                (new_amount, inc_staff_id),
            )
            db.commit()
            flash(f"Salary increment recorded: {previous:,.2f} → {new_amount:,.2f}")
            return redirect(url_for("staff", edit=inc_staff_id) + "#salary-increment")

        staff_id = request.form.get("staff_id", "").strip()
        staff_name = request.form.get("staff_name", "").strip()
        mobile = request.form.get("mobile", "").strip()
        email = request.form.get("email", "").strip()
        department = request.form.get("department", "").strip()
        designation_id = request.form.get("designation_id", "") or None
        reporting_manager = request.form.get("reporting_manager", "").strip()
        workflow_role = request.form.get("workflow_role", "").strip()
        salary_type = request.form.get("salary_type", "").strip()
        salary_amount = request.form.get("salary_amount", "0").strip()
        ot_applicable = request.form.get("ot_applicable", "No").strip()
        working_hours = request.form.get("working_hours", "0").strip()
        joining_date = request.form.get("joining_date", "").strip()
        status = request.form.get("status", "Active").strip()
        aadhaar_number = request.form.get("aadhaar_number", "").strip()
        pan_number = request.form.get("pan_number", "").strip()
        bank_account = request.form.get("bank_account", "").strip()
        bank_name = request.form.get("bank_name", "").strip()
        ifsc_code = request.form.get("ifsc_code", "").strip()
        branch_name = request.form.get("branch_name", "").strip()
        company_room_provided = request.form.get("company_room_provided", "No").strip()
        company_food_provided = request.form.get("company_food_provided", "No").strip()
        components = _parse_staff_hr_json(request.form.get("salary_components_payload"), [])
        travel_tiers = _parse_staff_hr_json(request.form.get("travel_tiers_payload"), [])
        if salary_type == "Monthly" and components:
            comp_total = sum(float(c.get("amount") or 0) for c in components if (c.get("component_name") or "").strip())
            if comp_total > 0:
                salary_amount = str(comp_total)
        existing_staff = None
        if staff_id:
            existing_staff = db.execute("SELECT * FROM staff WHERE id=?", (staff_id,)).fetchone()
            if not existing_staff:
                flash("Employee record not found.")
                return redirect(url_for("staff"))
        photo = save_file(request.files.get("photo"), PHOTOS_DIR)
        id_proof = save_file(request.files.get("id_proof"), STAFF_DOCS_DIR)
        aadhaar_document = save_file(request.files.get("aadhaar_document"), STAFF_DOCS_DIR)
        pan_document = save_file(request.files.get("pan_document"), STAFF_DOCS_DIR)
        if existing_staff:
            photo = photo or existing_staff["photo"]
            id_proof = id_proof or existing_staff["id_proof"]
            aadhaar_document = aadhaar_document or existing_staff["aadhaar_document"]
            pan_document = pan_document or existing_staff["pan_document"]
        employee_code = existing_staff["employee_code"] if existing_staff else generate_employee_code(db)
        designation_name = ""
        if designation_id:
            drow = db.execute(
                "SELECT designation_name FROM designations WHERE id=?", (designation_id,)
            ).fetchone()
            designation_name = drow["designation_name"] if drow else ""
        try:
            salary_amount_val = float(salary_amount or 0)
            working_hours_val = float(working_hours or 0)
        except ValueError:
            flash("Enter valid numeric values for salary and working hours.")
            return redirect(url_for("staff"))
        values = (
            employee_code, staff_name, mobile, email, department, designation_name,
            designation_id, reporting_manager, workflow_role or None,
            salary_type, salary_amount_val, ot_applicable, working_hours_val,
            joining_date, photo, status, aadhaar_number, pan_number,
            bank_account, bank_name, ifsc_code, branch_name,
            id_proof, aadhaar_document, pan_document,
            company_room_provided or "No", company_food_provided or "No",
        )
        if existing_staff:
            db.execute(
                "UPDATE staff SET employee_code=?, staff_name=?, mobile=?, email=?, department=?, "
                "designation=?, designation_id=?, reporting_manager=?, workflow_role=?, salary_type=?, "
                "salary_amount=?, ot_applicable=?, working_hours=?, joining_date=?, photo=?, status=?, "
                "aadhaar_number=?, pan_number=?, bank_account=?, bank_name=?, ifsc_code=?, "
                "branch_name=?, id_proof=?, aadhaar_document=?, pan_document=?, "
                "company_room_provided=?, company_food_provided=? WHERE id=?",
                values + (staff_id,),
            )
            saved_id = int(staff_id)
            flash(f"Employee updated. Employee Code: {employee_code}")
        else:
            db.execute(
                "INSERT INTO staff(employee_code, staff_name, mobile, email, department, designation, "
                "designation_id, reporting_manager, workflow_role, salary_type, salary_amount, "
                "ot_applicable, working_hours, joining_date, photo, status, aadhaar_number, pan_number, "
                "bank_account, bank_name, ifsc_code, branch_name, id_proof, aadhaar_document, pan_document, "
                "company_room_provided, company_food_provided) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                values,
            )
            saved_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            flash(f"Employee saved. Employee Code: {employee_code}")
        if salary_type == "Monthly":
            _save_staff_salary_components(db, saved_id, components)
            _save_staff_travel_tiers(db, saved_id, travel_tiers)
        else:
            db.execute("DELETE FROM staff_salary_components WHERE staff_id=?", (saved_id,))
            db.execute("DELETE FROM staff_travel_tiers WHERE staff_id=?", (saved_id,))
        db.commit()
        return redirect(url_for("staff"))
    rows_raw = query_db(
        "SELECT s.*, d.designation_name AS designation_label "
        "FROM staff s LEFT JOIN designations d ON s.designation_id = d.id "
        "ORDER BY s.id DESC"
    )
    rows = []
    for r in rows_raw:
        row = dict(r)
        row["workflow_access"] = get_workflow_access_label(
            db, row.get("designation_id"), row.get("workflow_role")
        )
        if row.get("workflow_role"):
            row["workflow_access"] = row["workflow_role"]
        elif row.get("designation_id"):
            row["workflow_access"] = get_workflow_access_for_designation(
                db, row["designation_id"]
            )
        row["display_designation"] = row.get("designation_label") or row.get("designation") or "—"
        row["salary_components"] = _fetch_staff_salary_components(db, row["id"])
        row["travel_tiers"] = _fetch_staff_travel_tiers(db, row["id"])
        row["salary_increments"] = _fetch_staff_salary_increments(db, row["id"])
        rows.append(row)
    return render_template(
        "staff.html",
        rows=rows,
        designations=designations,
        departments=departments,
        staff_list=staff_list,
        next_employee_code=generate_employee_code(db),
        editing_staff=editing_staff,
        editing_components=editing_components,
        editing_travel_tiers=editing_travel_tiers,
        editing_salary_increments=editing_salary_increments,
        salary_component_options=STAFF_SALARY_COMPONENT_OPTIONS,
    )


@app.route("/api/staff-bonus/attendance-stats")
@login_required
def api_staff_bonus_attendance_stats():
    staff_id = request.args.get("staff_id", type=int)
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    if not staff_id or not year or not month:
        return jsonify({"error": "staff_id, year, and month are required"}), 400
    if month < 1 or month > 12:
        return jsonify({"error": "Invalid month"}), 400
    db = get_db()
    staff_row = db.execute(
        "SELECT id, employee_code, staff_name FROM staff WHERE id=?",
        (staff_id,),
    ).fetchone()
    if not staff_row:
        return jsonify({"error": "Employee not found"}), 404
    stats = compute_staff_bonus_attendance_stats(db, staff_id, year, month)
    period, _, _ = _bonus_period_bounds(year, month)
    existing = db.execute(
        "SELECT id, payment_status, final_amount FROM staff_bonus "
        "WHERE staff_id=? AND bonus_period=?",
        (staff_id, period),
    ).fetchone()
    return jsonify({
        "staff_id": staff_id,
        "employee_code": staff_row["employee_code"],
        "staff_name": staff_row["staff_name"],
        "bonus_period": period,
        **stats,
        "existing_bonus_id": existing["id"] if existing else None,
        "existing_payment_status": existing["payment_status"] if existing else None,
        "existing_final_amount": float(existing["final_amount"] or 0) if existing else None,
    })


@app.route("/staff-bonus", methods=["GET", "POST"])
@login_required
def staff_bonus():
    db = get_db()
    prepare_hr_bonus_db(db)
    active_tab = request.args.get("tab", "calculation")
    if active_tab not in ("calculation", "payment"):
        active_tab = "calculation"

    staff_options = query_db(
        "SELECT id, employee_code, staff_name, salary_type, salary_amount "
        "FROM staff WHERE status='Active' ORDER BY staff_name"
    )
    now = get_app_now(db)
    default_year = now.year
    default_month = now.month

    if request.method == "POST":
        form_action = request.form.get("form_action", "save_bonus").strip()

        if form_action == "mark_paid":
            bonus_id = request.form.get("bonus_id", type=int)
            if not bonus_id:
                flash("Invalid bonus record.")
                return redirect(url_for("staff_bonus", tab="payment"))
            row = db.execute(
                "SELECT id, payment_status FROM staff_bonus WHERE id=?",
                (bonus_id,),
            ).fetchone()
            if not row:
                flash("Bonus record not found.")
                return redirect(url_for("staff_bonus", tab="payment"))
            if (row["payment_status"] or "").lower() == "paid":
                flash("Bonus is already marked paid.")
                return redirect(url_for("staff_bonus", tab="payment"))
            paid_at = get_app_now(db).strftime("%Y-%m-%d %H:%M:%S")
            db.execute(
                "UPDATE staff_bonus SET payment_status='paid', paid_at=? WHERE id=?",
                (paid_at, bonus_id),
            )
            db.commit()
            flash("Bonus marked as paid.")
            return redirect(url_for("staff_bonus", tab="payment"))

        staff_id = request.form.get("staff_id", type=int)
        year = request.form.get("bonus_year", type=int)
        month = request.form.get("bonus_month", type=int)
        method = (request.form.get("method") or "auto").strip().lower()
        if method not in ("auto", "manual"):
            method = "auto"
        remarks = request.form.get("remarks", "").strip()
        worked_days_raw = request.form.get("worked_days", "0").strip()
        leave_days_raw = request.form.get("leave_days", "0").strip()
        held_ot_raw = request.form.get("held_ot_hours", "0").strip()
        per_day_rate_raw = request.form.get("per_day_rate", "0").strip()
        manual_amount_raw = request.form.get("manual_amount", "0").strip()
        rounded_amount_raw = request.form.get("rounded_amount", "0").strip()

        if not staff_id or not year or not month:
            flash("Select employee, month, and year.")
            return redirect(url_for("staff_bonus", tab="calculation"))
        if month < 1 or month > 12:
            flash("Invalid month.")
            return redirect(url_for("staff_bonus", tab="calculation"))

        staff_row = db.execute("SELECT id FROM staff WHERE id=?", (staff_id,)).fetchone()
        if not staff_row:
            flash("Employee not found.")
            return redirect(url_for("staff_bonus", tab="calculation"))

        try:
            worked_days = float(worked_days_raw or 0)
            leave_days = float(leave_days_raw or 0)
            held_ot_hours = float(held_ot_raw or 0)
            per_day_rate = float(per_day_rate_raw or 0)
            manual_amount = float(manual_amount_raw or 0)
            rounded_amount = float(rounded_amount_raw or 0)
        except ValueError:
            flash("Enter valid numeric values.")
            return redirect(url_for("staff_bonus", tab="calculation"))

        if method == "auto":
            calculated_amount = round(per_day_rate * worked_days, 2)
        else:
            calculated_amount = round(manual_amount, 2)

        if rounded_amount <= 0:
            rounded_amount = calculated_amount
        final_amount = round(rounded_amount, 2)
        bonus_period, _, _ = _bonus_period_bounds(year, month)
        created_at = get_app_now(db).strftime("%Y-%m-%d %H:%M:%S")

        existing = db.execute(
            "SELECT id, payment_status FROM staff_bonus WHERE staff_id=? AND bonus_period=?",
            (staff_id, bonus_period),
        ).fetchone()
        if existing and (existing["payment_status"] or "").lower() == "paid":
            flash("Cannot modify a bonus that is already paid.")
            return redirect(url_for("staff_bonus", tab="payment"))

        if existing:
            db.execute(
                "UPDATE staff_bonus SET worked_days=?, leave_days=?, held_ot_hours=?, method=?, "
                "per_day_rate=?, calculated_amount=?, rounded_amount=?, final_amount=?, "
                "payment_status='pending', remarks=?, created_by=?, created_at=?, paid_at=NULL "
                "WHERE id=?",
                (
                    worked_days, leave_days, held_ot_hours, method,
                    per_day_rate, calculated_amount, rounded_amount, final_amount,
                    remarks, session.get("username", ""), created_at, existing["id"],
                ),
            )
            flash(f"Bonus updated for {bonus_period}. Payment status: pending.")
        else:
            db.execute(
                "INSERT INTO staff_bonus(staff_id, bonus_period, worked_days, leave_days, "
                "held_ot_hours, method, per_day_rate, calculated_amount, rounded_amount, "
                "final_amount, payment_status, remarks, created_by, created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    staff_id, bonus_period, worked_days, leave_days, held_ot_hours,
                    method, per_day_rate, calculated_amount, rounded_amount, final_amount,
                    "pending", remarks, session.get("username", ""), created_at,
                ),
            )
            flash(f"Bonus saved for {bonus_period}. Payment status: pending.")
        db.commit()
        return redirect(url_for("staff_bonus", tab="payment"))

    bonus_rows = query_db(
        "SELECT b.*, s.employee_code, s.staff_name FROM staff_bonus b "
        "JOIN staff s ON b.staff_id = s.id "
        "ORDER BY b.bonus_period DESC, b.id DESC"
    )
    payment_filter = request.args.get("payment_filter", "all")
    if payment_filter == "pending":
        bonus_rows = [r for r in bonus_rows if (r["payment_status"] or "").lower() == "pending"]
    elif payment_filter == "paid":
        bonus_rows = [r for r in bonus_rows if (r["payment_status"] or "").lower() == "paid"]

    return render_template(
        "staff_bonus.html",
        staff_options=staff_options,
        bonus_rows=bonus_rows,
        active_tab=active_tab,
        default_year=default_year,
        default_month=default_month,
        payment_filter=payment_filter,
        app_now_display=format_app_datetime(db=db),
    )


@app.route("/subcontractors", methods=["GET", "POST"])
@login_required
def subcontractors():
    db = get_db()
    ensure_subcontractor_rate_tables(db)
    projects = query_db(
        "SELECT id, project_code, project_name FROM projects ORDER BY project_name"
    )
    edit_id = request.args.get("edit", type=int)
    editing_subcontractor = None
    editing_manpower_rates = []
    editing_boq_rates = []
    editing_boq_project_id = None
    if edit_id:
        editing_subcontractor = query_db(
            "SELECT * FROM subcontractors WHERE id=?", (edit_id,), one=True
        )
        if not editing_subcontractor:
            flash("Subcontractor record not found.")
            return redirect(url_for("subcontractors"))
        editing_manpower_rates = query_db(
            "SELECT trade_name, rate_unit, working_hours, rate_amount, salary_amount "
            "FROM subcontractor_manpower_rates WHERE subcontractor_id=? ORDER BY trade_name",
            (edit_id,),
        )
        editing_boq_rates = query_db(
            "SELECT r.*, p.project_code, p.project_name FROM subcontractor_boq_rates r "
            "LEFT JOIN projects p ON r.project_id = p.id "
            "WHERE r.subcontractor_id=? ORDER BY r.line_no, r.id",
            (edit_id,),
        )
        if editing_boq_rates:
            editing_boq_project_id = editing_boq_rates[0]["project_id"]

    if request.method == "POST":
        form_action = request.form.get("form_action", "create").strip()
        if form_action == "delete":
            sub_id = request.form.get("subcontractor_id", type=int)
            if not sub_id:
                flash("Invalid subcontractor.")
                return redirect(url_for("subcontractors"))
            existing = query_db(
                "SELECT id, subcontractor_name FROM subcontractors WHERE id=?",
                (sub_id,),
                one=True,
            )
            if not existing:
                flash("Subcontractor record not found.")
                return redirect(url_for("subcontractors"))
            worker_count, request_count = _subcontractor_dependent_counts(db, sub_id)
            if worker_count or request_count:
                parts = []
                if worker_count:
                    parts.append(f"{worker_count} worker(s)")
                if request_count:
                    parts.append(f"{request_count} bill/payment request(s)")
                flash(
                    f"Cannot delete {existing['subcontractor_name']} — linked to "
                    f"{', '.join(parts)}. Set status to Inactive instead."
                )
                return redirect(url_for("subcontractors"))
            db.execute(
                "DELETE FROM subcontractor_manpower_rates WHERE subcontractor_id=?",
                (sub_id,),
            )
            db.execute(
                "DELETE FROM subcontractor_boq_rates WHERE subcontractor_id=?",
                (sub_id,),
            )
            if _table_exists(db, "dpr_manpower"):
                db.execute("DELETE FROM dpr_manpower WHERE subcontractor_id=?", (sub_id,))
            db.execute("DELETE FROM subcontractors WHERE id=?", (sub_id,))
            db.commit()
            flash(f"Subcontractor {existing['subcontractor_name']} deleted.")
            return redirect(url_for("subcontractors"))

        if form_action == "add_boq_rates":
            subcontractor_id = request.form.get("existing_subcontractor_id", "").strip()
            if not subcontractor_id.isdigit():
                flash("Select a subcontractor to add BOQ rates.")
                return redirect(url_for("subcontractors") + "#add-boq-rates")
            project_id, boq_rows = _parse_subcontractor_boq_rates()
            if not project_id:
                flash("Select a project for BOQ rates.")
                return redirect(url_for("subcontractors") + "#add-boq-rates")
            if not boq_rows:
                flash("Add at least one BOQ line item.")
                return redirect(url_for("subcontractors") + "#add-boq-rates")
            _insert_subcontractor_boq_rates(db, int(subcontractor_id), project_id, boq_rows)
            db.execute(
                "UPDATE subcontractors SET rate_type=? WHERE id=?",
                ("BOQ Base Rate", int(subcontractor_id)),
            )
            db.commit()
            flash(f"Added {len(boq_rows)} BOQ rate line(s) to subcontractor.")
            return redirect(url_for("subcontractors"))

        subcontractor_id_raw = request.form.get("subcontractor_id", "").strip()
        existing = None
        if subcontractor_id_raw.isdigit():
            existing = query_db(
                "SELECT * FROM subcontractors WHERE id=?",
                (int(subcontractor_id_raw),),
                one=True,
            )
            if not existing:
                flash("Subcontractor record not found.")
                return redirect(url_for("subcontractors"))

        subcontractor_name = request.form.get("subcontractor_name", "").strip()
        if not subcontractor_name:
            flash("Subcontractor name is required.")
            if existing:
                return redirect(url_for("subcontractors", edit=existing["id"]) + "#add-subcontractor")
            return redirect(url_for("subcontractors") + "#add-subcontractor")
        date_of_birth = request.form.get("date_of_birth", "").strip()
        id_number = request.form.get("id_number", "").strip()
        mobile = request.form.get("mobile", "").strip()
        pan_number = request.form.get("pan_number", "").strip()
        bank_account = request.form.get("bank_account", "").strip()
        bank_name = request.form.get("bank_name", "").strip()
        ifsc_code = request.form.get("ifsc_code", "").strip()
        branch_name = request.form.get("branch_name", "").strip()
        rate_type = request.form.get("rate_type", "Manpower").strip()
        if rate_type not in SUBCONTRACTOR_RATE_TYPES:
            rate_type = "Manpower"
        status = request.form.get("status", "Active").strip()
        photo = save_file(request.files.get("photo"), PHOTOS_DIR)
        id_document = save_file(request.files.get("id_document"), SUBCONTRACTOR_DOCS_DIR)
        pan_document = save_file(request.files.get("pan_document"), SUBCONTRACTOR_DOCS_DIR)
        if existing:
            photo = photo or existing["photo"]
            id_document = id_document or existing["id_document"]
            pan_document = pan_document or existing["pan_document"]
            subcontractor_code = existing["subcontractor_code"]
            subcontractor_id = existing["id"]
            db.execute(
                "UPDATE subcontractors SET "
                "subcontractor_name=?, date_of_birth=?, id_number=?, id_document=?, photo=?, "
                "mobile=?, pan_number=?, pan_document=?, bank_account=?, bank_name=?, ifsc_code=?, "
                "branch_name=?, rate_type=?, id_proof=?, status=? WHERE id=?",
                (
                    subcontractor_name, date_of_birth, id_number, id_document, photo,
                    mobile, pan_number, pan_document, bank_account, bank_name, ifsc_code,
                    branch_name, rate_type, id_document, status, subcontractor_id,
                ),
            )
        else:
            subcontractor_code = generate_subcontractor_code(db, subcontractor_name)
            cursor = db.execute(
                "INSERT INTO subcontractors("
                "subcontractor_code, subcontractor_name, date_of_birth, id_number, id_document, photo, "
                "mobile, pan_number, pan_document, bank_account, bank_name, ifsc_code, branch_name, "
                "rate_type, id_proof, status"
                ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    subcontractor_code, subcontractor_name, date_of_birth, id_number, id_document, photo,
                    mobile, pan_number, pan_document, bank_account, bank_name, ifsc_code, branch_name,
                    rate_type, id_document, status,
                ),
            )
            subcontractor_id = cursor.lastrowid

        rate_error = _sync_subcontractor_rates(
            db, subcontractor_id, rate_type, is_update=bool(existing)
        )
        if rate_error:
            flash(rate_error)
            if existing:
                return redirect(url_for("subcontractors", edit=subcontractor_id) + "#add-subcontractor")
            return redirect(url_for("subcontractors") + "#add-subcontractor")

        db.commit()
        if existing:
            flash(f"Subcontractor updated: {subcontractor_code or subcontractor_id}")
        else:
            flash(f"Subcontractor saved. Sub Contractor ID: {subcontractor_code}")
        return redirect(url_for("subcontractors"))

    rows = query_db(
        "SELECT s.*, "
        "(SELECT COUNT(*) FROM subcontractor_manpower_rates m WHERE m.subcontractor_id=s.id) AS manpower_rate_count, "
        "(SELECT COUNT(*) FROM subcontractor_boq_rates b WHERE b.subcontractor_id=s.id) AS boq_rate_count "
        "FROM subcontractors s ORDER BY s.id DESC"
    )
    return render_template(
        "subcontractors.html",
        rows=rows,
        projects=projects,
        manpower_trades=MANPOWER_TRADES,
        rate_types=SUBCONTRACTOR_RATE_TYPES,
        editing_subcontractor=editing_subcontractor,
        editing_manpower_rates=editing_manpower_rates,
        editing_boq_rates=editing_boq_rates,
        editing_boq_project_id=editing_boq_project_id,
    )


@app.route("/api/subcontractors/preview-code")
@login_required
def api_subcontractor_preview_code():
    name = request.args.get("name", "").strip()
    if not name:
        return jsonify({"code": ""})
    db = get_db()
    return jsonify({"code": generate_subcontractor_code(db, name)})


@app.route("/api/subcontractors/<int:subcontractor_id>/manpower-rates")
@login_required
def api_subcontractor_manpower_rates(subcontractor_id):
    rows = query_db(
        "SELECT trade_name, rate_unit, working_hours, rate_amount, salary_amount "
        "FROM subcontractor_manpower_rates WHERE subcontractor_id=? "
        "ORDER BY trade_name",
        (subcontractor_id,),
    )
    return jsonify([dict(row) for row in rows])


@app.route("/api/projects/<int:project_id>/boq-items")
@login_required
def api_project_boq_items(project_id):
    rows = query_db(
        "SELECT bi.id, bi.line_no, "
        "COALESCE(bi.item_description, '') AS item_description, "
        "COALESCE(bi.quantity, 0) AS quantity, "
        "COALESCE(bi.unit, '') AS unit, "
        "COALESCE(bi.rate, 0) AS rate, "
        "COALESCE(bi.amount, 0) AS amount, "
        "COALESCE(bm.boq_number, '') AS boq_number "
        "FROM boq_items bi "
        "LEFT JOIN boq_master bm ON bi.boq_id = bm.id "
        "WHERE COALESCE(bi.project_id, bm.project_id)=? "
        "ORDER BY bm.id DESC, bi.line_no, bi.id",
        (project_id,),
    )
    return jsonify([dict(row) for row in rows])


@app.route("/clients", methods=["GET", "POST"])
@login_required
def clients():
    db = get_db()
    if request.method == "POST":
        if _create_client_from_form():
            flash("Client saved.")
        return redirect(url_for("clients"))
    rows = query_db("SELECT * FROM clients ORDER BY id DESC")
    next_client_code = generate_client_code(db)
    return render_template("clients.html", rows=rows, next_client_code=next_client_code)


def _create_client_from_form():
    company_name = request.form.get("company_name", "").strip()
    contact_person = request.form.get("contact_person", "").strip()
    client_name = request.form.get("client_name", "").strip() or company_name or contact_person
    mobile = request.form.get("mobile", "").strip()
    email = request.form.get("email", "").strip()
    address = request.form.get("address", "").strip()
    gst_number = request.form.get("gst_number", "").strip()
    pan_number = request.form.get("pan_number", "").strip()
    status = request.form.get("status", "Active").strip()
    if not company_name:
        flash("Company name is required.")
        return None
    db = get_db()
    client_code = generate_client_code(db)
    cursor = db.execute(
        "INSERT INTO clients(client_code, client_name, company_name, contact_person, mobile, email, "
        "address, gst_number, pan_number, status) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            client_code, client_name, company_name, contact_person, mobile, email,
            address, gst_number, pan_number, status,
        ),
    )
    db.commit()
    return cursor.lastrowid


@app.route("/api/staff/<int:staff_id>")
@login_required
def api_staff_detail(staff_id):
    row = query_db(
        "SELECT s.*, d.designation_name FROM staff s "
        "LEFT JOIN designations d ON s.designation_id = d.id WHERE s.id=?",
        (staff_id,),
        one=True,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(dict(row))


@app.route("/projects", methods=["GET", "POST"])
@login_required
def projects():
    db = get_db()
    clients = query_db(
        "SELECT id, client_name, company_name, contact_person FROM clients ORDER BY company_name, client_name"
    )
    edit_id = request.args.get("edit", type=int)
    editing_project = None
    if edit_id:
        editing_project = query_db(
            "SELECT p.*, c.client_name, c.company_name FROM projects p "
            "LEFT JOIN clients c ON p.client_id = c.id WHERE p.id=?",
            (edit_id,),
            one=True,
        )
        if not editing_project:
            flash("Project record not found.")
            return redirect(url_for("projects"))

    if request.method == "POST":
        if request.form.get("form_action") == "create_client":
            new_client_id = _create_client_from_form()
            if new_client_id:
                flash("Client saved. It has been selected in the project form.")
                return redirect(
                    url_for("projects", select_client=new_client_id) + "#add-project"
                )
            return redirect(url_for("projects") + "#add-project")

        project_id = request.form.get("project_id", "").strip()
        existing_project = None
        if project_id:
            existing_project = db.execute(
                "SELECT * FROM projects WHERE id=?", (project_id,)
            ).fetchone()
            if not existing_project:
                flash("Project record not found.")
                return redirect(url_for("projects"))

        project_type = request.form.get("project_type", "Private").strip()
        project_name = request.form.get("project_name", "").strip()
        client_id = request.form.get("client_id", "") or None
        private_client_name = request.form.get("private_client_name", "").strip()
        location = request.form.get("location", "").strip()
        start_date = request.form.get("start_date", "").strip()
        end_date = request.form.get("end_date", "").strip()
        approved_total_amount = request.form.get("approved_total_amount", "0").strip()
        status = request.form.get("status", "Active").strip()
        gov_department = request.form.get("gov_department", "").strip()
        agreement_number = request.form.get("agreement_number", "").strip()
        agreement_date = request.form.get("agreement_date", "").strip()
        completion_time = request.form.get("completion_time", "").strip()
        quoted_amount = request.form.get("quoted_amount", "0").strip()
        security_deposit_pct = request.form.get("security_deposit_pct", "0").strip()
        guarantee_type = request.form.get("guarantee_type", "").strip()
        bank_guarantee_number = request.form.get("bank_guarantee_number", "").strip()
        bank_guarantee_issued_date = request.form.get("bank_guarantee_issued_date", "").strip()
        bank_guarantee_expiry_date = request.form.get("bank_guarantee_expiry_date", "").strip()
        bank_guarantee_amount = request.form.get("bank_guarantee_amount", "0").strip()
        treasury_deposit_number = request.form.get("treasury_deposit_number", "").strip()
        security_deposit_amount = request.form.get("security_deposit_amount", "0").strip()
        security_deposit_issued_date = request.form.get("security_deposit_issued_date", "").strip()
        security_deposit_maturity_date = request.form.get("security_deposit_maturity_date", "").strip()
        work_order_number = request.form.get("work_order_number", "").strip()
        work_order_date = request.form.get("work_order_date", "").strip()
        work_order_amount = request.form.get("work_order_amount", "0").strip()
        project_contact_person = request.form.get("project_contact_person", "").strip()

        if not project_name:
            flash("Project name is required.")
            return redirect(url_for("projects"))

        try:
            approved_total_val = float(approved_total_amount or 0)
            quoted_val = float(quoted_amount or 0)
            sd_pct_val = float(security_deposit_pct or 0)
            bg_amount_val = float(bank_guarantee_amount or 0)
            sd_amount_val = float(security_deposit_amount or 0)
            wo_amount_val = float(work_order_amount or 0)
        except ValueError:
            flash("Enter valid numeric amounts.")
            return redirect(url_for("projects"))

        agreement_document = save_file(request.files.get("agreement_document"), PROJECT_DOCS_DIR)
        bank_guarantee_document = save_file(
            request.files.get("bank_guarantee_document"), PROJECT_DOCS_DIR
        )
        security_deposit_document = save_file(
            request.files.get("security_deposit_document"), PROJECT_DOCS_DIR
        )
        work_order_document = save_file(request.files.get("work_order_document"), PROJECT_DOCS_DIR)

        project_code = (
            existing_project["project_code"] if existing_project else generate_project_code(db)
        )
        if project_type == "Government":
            private_client_name = ""
            client_id = None
            work_order_number = ""
            work_order_date = ""
            wo_amount_val = 0
            work_order_document = ""
            project_contact_person = ""
            if existing_project:
                agreement_document = agreement_document or existing_project["agreement_document"] or ""
                bank_guarantee_document = (
                    bank_guarantee_document or existing_project["bank_guarantee_document"] or ""
                )
                security_deposit_document = (
                    security_deposit_document or existing_project["security_deposit_document"] or ""
                )
            else:
                agreement_document = agreement_document or ""
                bank_guarantee_document = bank_guarantee_document or ""
                security_deposit_document = security_deposit_document or ""
        else:
            gov_department = ""
            agreement_number = ""
            agreement_date = ""
            completion_time = ""
            quoted_val = wo_amount_val or approved_total_val
            sd_pct_val = 0
            guarantee_type = ""
            bank_guarantee_number = ""
            bank_guarantee_issued_date = ""
            bank_guarantee_expiry_date = ""
            bg_amount_val = 0
            treasury_deposit_number = ""
            sd_amount_val = 0
            security_deposit_issued_date = ""
            security_deposit_maturity_date = ""
            agreement_document = ""
            bank_guarantee_document = ""
            security_deposit_document = ""
            if existing_project:
                work_order_document = (
                    work_order_document or existing_project["work_order_document"] or ""
                )
            else:
                work_order_document = work_order_document or ""

        project_values = (
            project_name, project_type, client_id, private_client_name, location,
            start_date, end_date, "", approved_total_val, approved_total_val, status, gov_department,
            agreement_number, agreement_date, completion_time, quoted_val, sd_pct_val,
            guarantee_type, bank_guarantee_number, bank_guarantee_issued_date,
            bank_guarantee_expiry_date, bg_amount_val, treasury_deposit_number, sd_amount_val,
            security_deposit_issued_date, security_deposit_maturity_date, agreement_document,
            bank_guarantee_document, security_deposit_document, work_order_number,
            work_order_date, wo_amount_val, project_contact_person, work_order_document,
        )
        if existing_project:
            db.execute(
                "UPDATE projects SET project_name=?, project_type=?, client_id=?, private_client_name=?, "
                "location=?, start_date=?, end_date=?, project_manager=?, budget=?, approved_total_amount=?, "
                "status=?, gov_department=?, agreement_number=?, agreement_date=?, completion_time=?, "
                "quoted_amount=?, security_deposit_pct=?, guarantee_type=?, bank_guarantee_number=?, "
                "bank_guarantee_issued_date=?, bank_guarantee_expiry_date=?, bank_guarantee_amount=?, "
                "treasury_deposit_number=?, security_deposit_amount=?, security_deposit_issued_date=?, "
                "security_deposit_maturity_date=?, agreement_document=?, bank_guarantee_document=?, "
                "security_deposit_document=?, work_order_number=?, work_order_date=?, work_order_amount=?, "
                "project_contact_person=?, work_order_document=? WHERE id=?",
                project_values + (project_id,),
            )
            db.commit()
            flash(f"Project updated. Project Number: {project_code}")
            return redirect(url_for("projects", edit=project_id) + "#add-project")

        db.execute(
            "INSERT INTO projects("
            "project_code, project_name, project_type, client_id, private_client_name, location, "
            "start_date, end_date, project_manager, budget, approved_total_amount, status, "
            "gov_department, agreement_number, "
            "agreement_date, completion_time, quoted_amount, security_deposit_pct, guarantee_type, "
            "bank_guarantee_number, bank_guarantee_issued_date, bank_guarantee_expiry_date, "
            "bank_guarantee_amount, treasury_deposit_number, security_deposit_amount, "
            "security_deposit_issued_date, security_deposit_maturity_date, agreement_document, "
            "bank_guarantee_document, security_deposit_document, work_order_number, work_order_date, "
            "work_order_amount, project_contact_person, work_order_document"
            ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (project_code,) + project_values,
        )
        db.commit()
        flash(f"Project saved. Project Number: {project_code}")
        return redirect(url_for("projects"))

    rows = query_db(
        "SELECT p.*, c.client_name, c.company_name FROM projects p "
        "LEFT JOIN clients c ON p.client_id = c.id ORDER BY p.id DESC"
    )
    next_project_code = generate_project_code(db) or "104"
    selected_client_id = request.args.get("select_client", type=int)
    if editing_project and not selected_client_id:
        selected_client_id = editing_project.get("client_id")
    return render_template(
        "projects.html",
        rows=rows,
        clients=clients,
        gov_departments=GOV_DEPARTMENTS,
        guarantee_types=GUARANTEE_TYPES,
        next_project_code=next_project_code,
        selected_client_id=selected_client_id,
        editing_project=editing_project,
    )


def _worker_dependent_counts(db, worker_id):
    attendance = db.execute(
        "SELECT COUNT(*) AS c FROM attendance "
        "WHERE worker_id=? AND COALESCE(worker_source, 'worker')='worker'",
        (worker_id,),
    ).fetchone()["c"]
    salary = db.execute(
        "SELECT COUNT(*) AS c FROM salary WHERE worker_id=?",
        (worker_id,),
    ).fetchone()["c"]
    dpr_count = 0
    if _table_exists(db, "dpr_manpower"):
        dpr_count = db.execute(
            "SELECT COUNT(*) AS c FROM dpr_manpower WHERE worker_id=?",
            (worker_id,),
        ).fetchone()["c"]
    return int(attendance or 0), int(salary or 0), int(dpr_count or 0)


def get_subcontractor_manpower_rate(subcontractor_id, trade_name):
    """Look up salary and hours for a subcontractor trade."""
    trade_name = (trade_name or "").strip()
    if not subcontractor_id or not trade_name:
        return None
    return query_db(
        "SELECT trade_name, rate_unit, working_hours, rate_amount, salary_amount "
        "FROM subcontractor_manpower_rates "
        "WHERE subcontractor_id=? AND trade_name=?",
        (subcontractor_id, trade_name),
        one=True,
    )


@app.route("/workers", methods=["GET", "POST"])
@login_required
def workers():
    db = get_db()
    prepare_workers_page_db(db)
    subcontractors = query_db(
        "SELECT id, subcontractor_name, subcontractor_code FROM subcontractors "
        "ORDER BY subcontractor_name"
    )
    edit_id = request.args.get("edit", type=int)
    editing_worker = None
    if edit_id:
        editing_worker = query_db(
            "SELECT * FROM workers WHERE id=? "
            "AND COALESCE(worker_category, 'Company Staff') = 'Sub Contractor Staff'",
            (edit_id,),
            one=True,
        )
        if not editing_worker:
            flash("Subcontractor worker record not found.")
            return redirect(url_for("workers"))

    if request.method == "POST":
        form_action = request.form.get("form_action", "save").strip()
        if form_action == "delete":
            worker_id = request.form.get("worker_id", type=int)
            if not worker_id:
                flash("Invalid worker.")
                return redirect(url_for("workers"))
            existing = query_db(
                "SELECT id, worker_name FROM workers WHERE id=? "
                "AND COALESCE(worker_category, 'Company Staff') = 'Sub Contractor Staff'",
                (worker_id,),
                one=True,
            )
            if not existing:
                flash("Worker record not found.")
                return redirect(url_for("workers"))
            att_count, sal_count, dpr_count = _worker_dependent_counts(db, worker_id)
            if att_count or sal_count or dpr_count:
                parts = []
                if att_count:
                    parts.append(f"{att_count} attendance record(s)")
                if sal_count:
                    parts.append(f"{sal_count} salary record(s)")
                if dpr_count:
                    parts.append(f"{dpr_count} DPR manpower link(s)")
                flash(
                    f"Cannot delete {existing['worker_name']} — linked to "
                    f"{', '.join(parts)}. Set status to Inactive instead."
                )
                return redirect(url_for("workers"))
            db.execute("DELETE FROM workers WHERE id=?", (worker_id,))
            db.commit()
            flash(f"Worker {existing['worker_name']} deleted.")
            return redirect(url_for("workers"))

        worker_name = request.form.get("worker_name", "").strip()
        mobile = request.form.get("mobile", "").strip()
        aadhaar_number = request.form.get("aadhaar_number", "").strip()
        pan_number = request.form.get("pan_number", "").strip()
        trade_name = request.form.get("trade_name", "").strip()
        subcontractor_id = request.form.get("subcontractor_id", "").strip()
        joining_date = request.form.get("joining_date", "").strip()
        status = request.form.get("status", "Active").strip()
        worker_category = "Sub Contractor Staff"

        worker_id_raw = request.form.get("worker_id", "").strip()
        existing = None
        if worker_id_raw.isdigit():
            existing = query_db(
                "SELECT * FROM workers WHERE id=? "
                "AND COALESCE(worker_category, 'Company Staff') = 'Sub Contractor Staff'",
                (int(worker_id_raw),),
                one=True,
            )
            if not existing:
                flash("Worker record not found.")
                return redirect(url_for("workers"))

        if not worker_name:
            flash("Worker name is required.")
            if existing:
                return redirect(url_for("workers", edit=existing["id"]) + "#add-worker")
            return redirect(url_for("workers") + "#add-worker")
        if not subcontractor_id or not str(subcontractor_id).isdigit():
            flash("Select a valid subcontractor first.")
            if existing:
                return redirect(url_for("workers", edit=existing["id"]) + "#add-worker")
            return redirect(url_for("workers") + "#add-worker")
        subcontractor_id_int = int(subcontractor_id)
        if not trade_name:
            flash("Select a trade from the subcontractor manpower rates.")
            if existing:
                return redirect(url_for("workers", edit=existing["id"]) + "#add-worker")
            return redirect(url_for("workers") + "#add-worker")

        rate_row = get_subcontractor_manpower_rate(subcontractor_id_int, trade_name)
        if not rate_row:
            flash("Selected trade is not configured on the subcontractor manpower rates.")
            if existing:
                return redirect(url_for("workers", edit=existing["id"]) + "#add-worker")
            return redirect(url_for("workers") + "#add-worker")

        rate_row = dict(rate_row)
        designation = trade_name
        rate_unit = (rate_row.get("rate_unit") or "Day").strip()
        salary_type = "Daily" if rate_unit == "Day" else "Hourly"
        salary_amount_val = float(rate_row.get("salary_amount") or 0)
        working_hours_val = float(rate_row.get("working_hours") or 0)

        try:
            photo = save_file(request.files.get("photo"), PHOTOS_DIR)
            id_proof = save_file(request.files.get("id_proof"), WORKER_DOCS_DIR)
            aadhaar_document = save_file(request.files.get("aadhaar_document"), WORKER_DOCS_DIR)
            pan_document = save_file(request.files.get("pan_document"), WORKER_DOCS_DIR)

            if existing:
                existing_row = dict(existing)
                photo = photo or existing_row.get("photo")
                id_proof = id_proof or existing_row.get("id_proof")
                aadhaar_document = aadhaar_document or existing_row.get("aadhaar_document")
                pan_document = pan_document or existing_row.get("pan_document")
                worker_code = existing_row.get("worker_code")
                db.execute(
                    "UPDATE workers SET worker_code=?, worker_name=?, mobile=?, aadhaar_number=?, pan_number=?, "
                    "photo=?, id_proof=?, aadhaar_document=?, pan_document=?, worker_category=?, designation=?, "
                    "salary_type=?, salary_amount=?, ot_applicable=?, working_hours=?, subcontractor_id=?, "
                    "joining_date=?, status=? WHERE id=?",
                    (
                        worker_code, worker_name, mobile, aadhaar_number, pan_number,
                        photo, id_proof, aadhaar_document, pan_document,
                        worker_category, designation, salary_type, salary_amount_val,
                        "No", working_hours_val, subcontractor_id_int, joining_date, status,
                        existing_row["id"],
                    ),
                )
                flash(f"Worker updated: {worker_code or existing_row['id']}")
            else:
                worker_code = generate_worker_code(db, worker_category, subcontractor_id_int)
                db.execute(
                    "INSERT INTO workers(worker_code, worker_name, mobile, aadhaar_number, pan_number, "
                    "photo, id_proof, aadhaar_document, pan_document, worker_category, designation, "
                    "salary_type, salary_amount, ot_applicable, working_hours, subcontractor_id, "
                    "joining_date, status) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        worker_code, worker_name, mobile, aadhaar_number, pan_number,
                        photo, id_proof, aadhaar_document, pan_document,
                        worker_category, designation, salary_type, salary_amount_val,
                        "No", working_hours_val, subcontractor_id_int, joining_date, status,
                    ),
                )
                flash(f"Worker saved. Worker ID: {worker_code}")

            db.commit()
        except sqlite3.OperationalError as exc:
            db.rollback()
            flash(f"Could not save worker — database needs an update. Contact admin. ({exc})")
            if existing:
                return redirect(url_for("workers", edit=existing["id"]) + "#add-worker")
            return redirect(url_for("workers") + "#add-worker")
        except (TypeError, ValueError) as exc:
            db.rollback()
            flash(f"Could not save worker — check salary/rate values. ({exc})")
            return redirect(url_for("workers") + "#add-worker")
        return redirect(url_for("workers"))

    rows = query_db(
        "SELECT w.*, s.subcontractor_name, s.subcontractor_code FROM workers w "
        "LEFT JOIN subcontractors s ON w.subcontractor_id = s.id "
        "WHERE COALESCE(w.worker_category, 'Company Staff') = 'Sub Contractor Staff' "
        "ORDER BY w.id DESC"
    )
    subcontractor_options = []
    for item in subcontractors:
        subcontractor_options.append({
            "id": item["id"],
            "subcontractor_name": item["subcontractor_name"],
            "subcontractor_code": item["subcontractor_code"],
            "next_worker_code": generate_worker_code(db, "Sub Contractor Staff", item["id"]),
        })
    default_sub_code = ""
    if subcontractor_options:
        default_sub_code = subcontractor_options[0]["next_worker_code"]
    return render_template(
        "workers.html",
        rows=rows,
        subcontractors=subcontractor_options,
        next_worker_code=default_sub_code,
        editing_worker=editing_worker,
    )


@app.route("/attendance", methods=["GET", "POST"])
@login_required
def attendance():
    module_id, table, endpoint = "daily_timesheet", "attendance", "attendance"
    record_sql = (
        "SELECT a.*, "
        "COALESCE(w.worker_name, s.staff_name) AS worker_name, "
        "COALESCE(w.worker_code, s.employee_code) AS worker_code, "
        "p.project_name, p.project_code "
        "FROM attendance a "
        f"{ATTENDANCE_WORKER_JOIN_SQL} "
        "LEFT JOIN projects p ON a.project_id = p.id WHERE a.id=?"
    )
    attendance_workers = get_attendance_form_worker_data()
    projects = get_attendance_project_options()
    view_id = request.args.get("view")
    edit_id = request.args.get("edit")
    view_record = edit_record = None
    edit_worker_ctx = {"staff_type": "", "subcontractor_id": ""}
    wf_ctx = {}
    if view_id:
        view_record = query_db(record_sql, (view_id,), one=True)
        if view_record:
            wf_ctx = _workflow_view_context(
                module_id, view_record["id"], table, view_record["approval_status"]
            )
    elif edit_id:
        edit_record = query_db(record_sql, (edit_id,), one=True)
        if edit_record:
            edit_role = get_edit_role_for_user(
                get_db(), session.get("user_id"), module_id,
                edit_record["approval_status"], is_admin_user(),
            )
            if not edit_role:
                flash("This record is locked and cannot be edited.")
                return redirect(url_for(endpoint, view=edit_id))
            wf_ctx = {"edit_role": edit_role}
            edit_worker_ctx = get_attendance_edit_worker_context(edit_record)
    if request.method == "POST":
        worker_ref = request.form.get("worker_id", "")
        worker_id, worker_source = parse_attendance_worker_ref(worker_ref)
        project_id = request.form.get("project_id", "")
        attendance_date = request.form.get("attendance_date", "").strip()
        in_time = request.form.get("in_time", "").strip()
        out_time = request.form.get("out_time", "").strip()
        break_hours = request.form.get("break_hours", "0").strip()
        status = request.form.get("status", "Present").strip()
        record_id = request.form.get("record_id", "").strip()
        try:
            start_dt = datetime.strptime(in_time, "%H:%M")
            end_dt = datetime.strptime(out_time, "%H:%M")
            break_hours_val = float(break_hours or 0)
            total_hours = (end_dt - start_dt).seconds / 3600 - break_hours_val
            if total_hours < 0:
                total_hours += 24
            ot_hours = max(total_hours - 8, 0)
        except Exception:
            flash("Enter valid attendance time values.")
            return redirect(url_for(endpoint))
        db = get_db()
        if record_id:
            ctx = _module_edit_context(module_id, table, endpoint)
            if ctx[0] == "redirect":
                return redirect(ctx[1])
            rid, edit_role = ctx
            db.execute(
                "UPDATE attendance SET worker_id=?, worker_source=?, project_id=?, attendance_date=?, "
                "in_time=?, out_time=?, break_hours=?, total_hours=?, ot_hours=?, status=? WHERE id=?",
                (
                    worker_id, worker_source, project_id or None, attendance_date,
                    in_time, out_time, break_hours_val, total_hours, ot_hours, status, rid,
                ),
            )
            _complete_module_save(db, module_id, table, rid, edit_role)
            return redirect(url_for(endpoint))
        db.execute(
            "INSERT INTO attendance(worker_id, worker_source, project_id, attendance_date, in_time, out_time, break_hours, total_hours, ot_hours, status, approval_status) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                worker_id, worker_source, project_id or None, attendance_date,
                in_time, out_time, break_hours_val, total_hours, ot_hours, status, "Pending Checker",
            ),
        )
        record_id_new = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        create_approval_request(
            db, module_id, record_id_new, table,
            session.get("username", ""), session.get("user_id")
        )
        db.commit()
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db(
        "SELECT a.*, "
        "COALESCE(w.worker_name, s.staff_name) AS worker_name, "
        "COALESCE(w.worker_code, s.employee_code) AS worker_code, "
        "p.project_name, p.project_code "
        "FROM attendance a "
        f"{ATTENDANCE_WORKER_JOIN_SQL} "
        "LEFT JOIN projects p ON a.project_id = p.id ORDER BY a.id DESC"
    )
    return render_template(
        "attendance.html",
        rows=rows,
        company_staff=attendance_workers["company_staff"],
        subcontractors=attendance_workers["subcontractors"],
        subcontractor_workers=attendance_workers["subcontractor_workers"],
        projects=projects,
        view_record=view_record,
        edit_record=edit_record,
        edit_staff_type=edit_worker_ctx["staff_type"],
        edit_subcontractor_id=edit_worker_ctx["subcontractor_id"],
        history=wf_ctx.get("history"),
        edit_role=wf_ctx.get("edit_role"),
        can_reopen=wf_ctx.get("can_reopen", False),
        approval_id=wf_ctx.get("approval_id"),
    )


@app.route("/petty_cash", methods=["GET", "POST"])
@login_required
def petty_cash():
    projects = query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    view_id = request.args.get("view")
    edit_id = request.args.get("edit")
    view_record = None
    edit_record = None
    if view_id:
        view_record = query_db(
            "SELECT p.*, pr.project_name FROM petty_cash p "
            "LEFT JOIN projects pr ON p.project_id = pr.id WHERE p.id=?",
            (view_id,), one=True,
        )
    if edit_id:
        edit_record = query_db(
            "SELECT p.*, pr.project_name FROM petty_cash p "
            "LEFT JOIN projects pr ON p.project_id = pr.id WHERE p.id=?",
            (edit_id,), one=True,
        )
    if request.method == "POST":
        project_id = request.form.get("project_id", "")
        expense_date = request.form.get("expense_date", "").strip()
        expense_type = request.form.get("expense_type", "").strip()
        amount = request.form.get("amount", "0").strip()
        payment_mode = request.form.get("payment_mode", "Cash").strip()
        remarks = request.form.get("remarks", "").strip()
        record_id = request.form.get("record_id", "").strip()
        created_by = session.get("username", "")
        try:
            amount_val = float(amount or 0)
        except ValueError:
            flash("Enter a valid amount.")
            return redirect(url_for("petty_cash"))
        db = get_db()
        if record_id:
            existing = db.execute(
                "SELECT approval_status FROM petty_cash WHERE id=?", (record_id,)
            ).fetchone()
            if not existing:
                flash("Record not found.")
                return redirect(url_for("petty_cash"))
            edit_role = get_edit_role_for_user(
                db, session.get("user_id"), "petty_cash",
                existing["approval_status"], is_admin_user(),
            )
            if not edit_role:
                flash("This record is locked and cannot be edited.")
                return redirect(url_for("petty_cash"))
            db.execute(
                "UPDATE petty_cash SET project_id=?, expense_date=?, expense_type=?, "
                "amount=?, payment_mode=?, remarks=? WHERE id=?",
                (project_id or None, expense_date, expense_type, amount_val, payment_mode,
                 remarks, record_id),
            )
            if edit_role == "maker":
                db.execute(
                    "UPDATE petty_cash SET approval_status=? WHERE id=?",
                    ("Pending Checker", record_id),
                )
                resubmit_record(db, "petty_cash", int(record_id), "petty_cash", session.get("user_id"))
            db.commit()
            if edit_role != "maker":
                flash("Changes saved. Record remains locked at current workflow stage.")
            else:
                flash("Saved. Status: Pending Checker.")
        else:
            db.execute(
                "INSERT INTO petty_cash(project_id, expense_date, expense_type, amount, "
                "payment_mode, remarks, created_by, approval_status) VALUES(?,?,?,?,?,?,?,?)",
                (project_id or None, expense_date, expense_type, amount_val, payment_mode,
                 remarks, created_by, "Pending Checker"),
            )
            new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            create_approval_request(
                db, "petty_cash", new_id, "petty_cash", created_by, session.get("user_id")
            )
            db.commit()
            flash("Saved. Status: Pending Checker.")
        return redirect(url_for("petty_cash"))
    rows = query_db(
        "SELECT p.*, pr.project_name FROM petty_cash p LEFT JOIN projects pr ON p.project_id = pr.id ORDER BY p.id DESC"
    )
    workflow = get_workflow_for_module(get_db(), "petty_cash")
    wf_ctx = {}
    if view_record:
        wf_ctx = _workflow_view_context(
            "petty_cash", view_record["id"], "petty_cash", view_record["approval_status"]
        )
    elif edit_record:
        edit_role = get_edit_role_for_user(
            get_db(), session.get("user_id"), "petty_cash",
            edit_record["approval_status"], is_admin_user(),
        )
        if not edit_role:
            flash("This record is locked and cannot be edited.")
            return redirect(url_for("petty_cash", view=edit_id))
        wf_ctx = {"edit_role": edit_role}
    return render_template(
        "petty_cash.html", rows=rows, projects=projects, workflow=workflow,
        view_record=view_record, edit_record=edit_record,
        history=wf_ctx.get("history"),
        edit_role=wf_ctx.get("edit_role"),
        can_reopen=wf_ctx.get("can_reopen", False),
        approval_id=wf_ctx.get("approval_id"),
        is_admin=is_admin_user(),
    )


@app.route("/salary", methods=["GET", "POST"])
@login_required
def salary():
    module_id, table, endpoint = "payroll", "salary", "salary"
    record_sql = (
        "SELECT s.*, w.worker_name FROM salary s "
        "LEFT JOIN workers w ON s.worker_id = w.id WHERE s.id=?"
    )
    workers = query_db("SELECT id, worker_name FROM workers ORDER BY worker_name")
    view_id = request.args.get("view")
    edit_id = request.args.get("edit")
    view_record = edit_record = None
    wf_ctx = {}
    if view_id:
        view_record = query_db(record_sql, (view_id,), one=True)
        if view_record:
            wf_ctx = _workflow_view_context(
                module_id, view_record["id"], table, view_record["approval_status"]
            )
    elif edit_id:
        edit_record = query_db(record_sql, (edit_id,), one=True)
        if edit_record:
            edit_role = get_edit_role_for_user(
                get_db(), session.get("user_id"), module_id,
                edit_record["approval_status"], is_admin_user(),
            )
            if not edit_role:
                flash("This record is locked and cannot be edited.")
                return redirect(url_for(endpoint, view=edit_id))
            wf_ctx = {"edit_role": edit_role}
    if request.method == "POST":
        worker_id = request.form.get("worker_id", "")
        month = request.form.get("month", "").strip()
        total_days = request.form.get("total_days", "0").strip()
        normal_wage = request.form.get("normal_wage", "0").strip()
        ot_amount = request.form.get("ot_amount", "0").strip()
        advance_deduction = request.form.get("advance_deduction", "0").strip()
        payment_status = request.form.get("payment_status", "Pending").strip()
        record_id = request.form.get("record_id", "").strip()
        try:
            total_days_val = int(total_days or 0)
            normal_wage_val = float(normal_wage or 0)
            ot_amount_val = float(ot_amount or 0)
            advance_deduction_val = float(advance_deduction or 0)
            final_salary = normal_wage_val + ot_amount_val - advance_deduction_val
        except ValueError:
            flash("Enter valid numeric salary values.")
            return redirect(url_for(endpoint))
        db = get_db()
        if record_id:
            ctx = _module_edit_context(module_id, table, endpoint)
            if ctx[0] == "redirect":
                return redirect(ctx[1])
            rid, edit_role = ctx
            db.execute(
                "UPDATE salary SET worker_id=?, month=?, total_days=?, normal_wage=?, "
                "ot_amount=?, advance_deduction=?, final_salary=?, payment_status=? WHERE id=?",
                (
                    worker_id or None, month, total_days_val, normal_wage_val,
                    ot_amount_val, advance_deduction_val, final_salary, payment_status, rid,
                ),
            )
            _complete_module_save(db, module_id, table, rid, edit_role)
            return redirect(url_for(endpoint))
        db.execute(
            "INSERT INTO salary(worker_id, month, total_days, normal_wage, ot_amount, advance_deduction, final_salary, payment_status, approval_status) VALUES(?,?,?,?,?,?,?,?,?)",
            (worker_id or None, month, total_days_val, normal_wage_val, ot_amount_val, advance_deduction_val, final_salary, payment_status, "Pending Checker")
        )
        record_id_new = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        create_approval_request(
            db, module_id, record_id_new, table,
            session.get("username", ""), session.get("user_id")
        )
        db.commit()
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db(
        "SELECT s.*, w.worker_name FROM salary s LEFT JOIN workers w ON s.worker_id = w.id ORDER BY s.id DESC"
    )
    return render_template(
        "salary.html", rows=rows, workers=workers,
        view_record=view_record, edit_record=edit_record,
        history=wf_ctx.get("history"),
        edit_role=wf_ctx.get("edit_role"),
        can_reopen=wf_ctx.get("can_reopen", False),
        approval_id=wf_ctx.get("approval_id"),
    )


@app.route("/reports", methods=["GET", "POST"])
@login_required
def reports():
    workers = query_db("SELECT id, worker_name FROM workers ORDER BY worker_name")
    report_rows = None
    file_url = None
    if request.method == "POST":
        report_type = request.form.get("report_type", "attendance")
        worker_ref = request.form.get("worker_id", "")
        worker_id, worker_source = parse_attendance_worker_ref(worker_ref)
        from_date = request.form.get("from_date", "").strip()
        to_date = request.form.get("to_date", "").strip()
        try:
            if report_type == "attendance":
                query = (
                    "SELECT a.attendance_date, "
                    "COALESCE(w.worker_name, s.staff_name) AS worker_name, "
                    "p.project_name, a.in_time, a.out_time, a.break_hours, a.total_hours, a.ot_hours, a.status "
                    f"FROM attendance a {ATTENDANCE_WORKER_JOIN_SQL} "
                    "LEFT JOIN projects p ON a.project_id = p.id "
                    "WHERE a.worker_id = ? AND COALESCE(a.worker_source, 'worker') = ? "
                    "AND a.attendance_date BETWEEN ? AND ?"
                )
                df = pd.read_sql_query(
                    query, get_db(), params=(worker_id, worker_source, from_date, to_date)
                )
            else:
                query = (
                    "SELECT s.month, w.worker_name, s.total_days, s.normal_wage, s.ot_amount, s.advance_deduction, s.final_salary, s.payment_status "
                    "FROM salary s LEFT JOIN workers w ON s.worker_id = w.id "
                    "WHERE s.worker_id = ? AND s.month = ?"
                )
                df = pd.read_sql_query(query, get_db(), params=(worker_id or None, from_date))
            if df.empty:
                flash("No records found for the selected criteria.")
            else:
                filename = f"{report_type}_report_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.xlsx"
                file_path = os.path.join(REPORTS_DIR, filename)
                df.to_excel(file_path, index=False)
                file_url = url_for("download_report", filename=filename)
                report_rows = df.to_dict(orient="records")
        except Exception as exc:
            flash(f"Unable to generate report: {exc}")
    return render_template("reports.html", workers=workers, report_rows=report_rows, file_url=file_url)


@app.route("/reports/download/<filename>")
@login_required
def download_report(filename):
    return send_from_directory(REPORTS_DIR, filename, as_attachment=True)


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    db = get_db()
    ensure_app_settings_table(db)
    ensure_department_master(db)
    if request.method == "POST":
        form_type = request.form.get("form_type", "department").strip()
        if form_type == "company":
            timezone = request.form.get("timezone", "Asia/Kolkata").strip()
            valid_tz = {tz for tz, _ in APP_TIMEZONE_OPTIONS}
            if timezone not in valid_tz:
                flash("Select a valid timezone.")
                return redirect(url_for("settings") + "#company-settings")
            set_app_setting(db, "timezone", timezone)
            flash("Company settings updated.")
            return redirect(url_for("settings") + "#company-settings")
        department_name = request.form.get("department_name", "").strip()
        description = request.form.get("description", "").strip()
        status = request.form.get("status", "Active").strip()
        if not department_name:
            flash("Department name is required.")
            return redirect(url_for("settings") + "#department-master")
        try:
            db.execute(
                "INSERT INTO departments(department_name, description, status) VALUES(?,?,?)",
                (department_name, description, status),
            )
            db.commit()
            flash("Department created.")
        except sqlite3.IntegrityError:
            flash("Department already exists.")
        return redirect(url_for("settings") + "#department-master")
    departments = query_db("SELECT * FROM departments ORDER BY department_name")
    current_timezone = get_app_setting(db, "timezone", "Asia/Kolkata")
    return render_template(
        "settings.html",
        departments=departments,
        timezone_options=APP_TIMEZONE_OPTIONS,
        current_timezone=current_timezone,
        app_now_display=format_app_datetime(db=db),
    )


@app.route("/settings/users", methods=["GET", "POST"])
@admin_required
def user_settings():
    db = get_db()
    designations = query_db(
        "SELECT id, designation_name FROM designations WHERE status='Active' ORDER BY designation_name"
    )
    departments = get_departments()
    workflow_roles = ["Maker", "Checker", "Approver", "Administrator"]
    system_roles = ["Maker", "Checker", "Approver", "Admin"]

    if request.method == "POST":
        action = request.form.get("action", "save")
        user_id = request.form.get("user_id", "").strip()
        if action == "toggle" and user_id:
            row = db.execute("SELECT status FROM users WHERE id=?", (user_id,)).fetchone()
            if row:
                new_status = "Inactive" if row["status"] == "Active" else "Active"
                db.execute("UPDATE users SET status=? WHERE id=?", (new_status, user_id))
                db.commit()
                flash(f"User status updated to {new_status}.")
            return redirect(url_for("user_settings"))

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        staff_id = request.form.get("staff_id", "") or None
        employee_name = request.form.get("employee_name", "").strip()
        department = request.form.get("department", "").strip()
        designation_id = request.form.get("designation_id") or None
        role = request.form.get("role", "Maker").strip()
        workflow_role = request.form.get("workflow_role", "Maker").strip()
        status = request.form.get("status", "Active").strip()
        maker_departments = request.form.getlist("maker_department[]")
        maker_modules = request.form.getlist("maker_module[]")
        maker_statuses = request.form.getlist("maker_status[]")

        if staff_id and not employee_name:
            srow = db.execute(
                "SELECT staff_name FROM staff WHERE id=?", (staff_id,)
            ).fetchone()
            if srow:
                employee_name = srow["staff_name"]

        if not username or not employee_name:
            flash("Select employee from master and ensure username is set.")
            return redirect(url_for("user_settings"))

        saved_user_id = user_id
        if user_id:
            if password:
                db.execute(
                    "UPDATE users SET username=?, password=?, staff_id=?, employee_name=?, department=?, "
                    "designation_id=?, role=?, workflow_role=?, status=? WHERE id=?",
                    (username, password, staff_id, employee_name, department, designation_id,
                     role, workflow_role, status, user_id),
                )
            else:
                db.execute(
                    "UPDATE users SET username=?, staff_id=?, employee_name=?, department=?, "
                    "designation_id=?, role=?, workflow_role=?, status=? WHERE id=?",
                    (username, staff_id, employee_name, department, designation_id,
                     role, workflow_role, status, user_id),
                )
            saved_user_id = user_id
            flash("User updated successfully.")
        else:
            if not password:
                flash("Password is required for new users.")
                return redirect(url_for("user_settings"))
            try:
                cur = db.execute(
                    "INSERT INTO users(username, password, staff_id, employee_name, department, "
                    "designation_id, role, workflow_role, status) VALUES(?,?,?,?,?,?,?,?,?)",
                    (username, password, staff_id, employee_name, department, designation_id,
                     role, workflow_role, status),
                )
                saved_user_id = cur.lastrowid
                flash("User created successfully.")
            except sqlite3.IntegrityError:
                flash("Username already exists.")
                return redirect(url_for("user_settings"))

        if saved_user_id and workflow_role == "Maker":
            save_user_maker_assignments(
                db, saved_user_id, maker_departments, maker_modules, maker_statuses
            )
        elif saved_user_id:
            ensure_user_maker_assignments_table(db)
            db.execute("DELETE FROM user_maker_assignments WHERE user_id=?", (saved_user_id,))

        db.commit()
        return redirect(url_for("user_settings"))

    edit_id = request.args.get("edit")
    edit_user = None
    maker_assignments = []
    if edit_id:
        edit_user = query_db(
            "SELECT u.*, d.designation_name FROM users u "
            "LEFT JOIN designations d ON u.designation_id = d.id WHERE u.id=?",
            (edit_id,),
            one=True,
        )
        if edit_user:
            maker_assignments = get_user_maker_assignments(db, edit_id)

    staff_rows = query_db(
        "SELECT s.id, s.employee_code, s.staff_name, s.department, s.designation_id, "
        "d.designation_name FROM staff s "
        "LEFT JOIN designations d ON s.designation_id = d.id "
        "WHERE s.status='Active' ORDER BY s.staff_name"
    )
    workflow_modules = get_workflow_modules()

    rows = query_db(
        "SELECT u.*, d.designation_name FROM users u "
        "LEFT JOIN designations d ON u.designation_id = d.id ORDER BY u.id DESC"
    )
    enriched = []
    for row in rows:
        r = dict(row)
        r["workflow_access"] = get_workflow_access_label(
            db, r.get("designation_id"), r.get("workflow_role")
        )
        if r.get("workflow_role"):
            r["workflow_access"] = r["workflow_role"]
        enriched.append(r)

    return render_template(
        "users.html",
        rows=enriched,
        designations=designations,
        departments=departments,
        workflow_roles=workflow_roles,
        system_roles=system_roles,
        edit_user=edit_user,
        staff_rows=staff_rows,
        workflow_modules=workflow_modules,
        maker_assignments=maker_assignments,
        max_maker_slots=MAX_MAKER_ASSIGNMENTS,
    )


@app.route("/settings/workflow", methods=["GET", "POST"])
@app.route("/settings/workflow-matrix", methods=["GET", "POST"])
@login_required
def workflow_settings():
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action", "save")
        if action == "add_designation":
            name = request.form.get("designation_name", "").strip()
            if name:
                try:
                    db.execute(
                        "INSERT INTO designations(designation_name, status) VALUES(?, 'Active')",
                        (name,),
                    )
                    db.commit()
                    flash(f"Designation '{name}' added.")
                except sqlite3.IntegrityError:
                    flash("Designation already exists.")
        else:
            module_id = request.form.get("module_id", "").strip()
            maker_id = request.form.get("maker_designation_id", "")
            checker_id = request.form.get("checker_designation_id", "")
            approver_id = request.form.get("approver_designation_id", "")
            maker_name = db.execute(
                "SELECT designation_name FROM designations WHERE id=?", (maker_id,)
            ).fetchone()
            checker_name = db.execute(
                "SELECT designation_name FROM designations WHERE id=?", (checker_id,)
            ).fetchone()
            approver_name = db.execute(
                "SELECT designation_name FROM designations WHERE id=?", (approver_id,)
            ).fetchone()
            flow = f"{maker_name['designation_name'] if maker_name else 'Maker'} → {checker_name['designation_name'] if checker_name else 'Checker'} → {approver_name['designation_name'] if approver_name else 'Approver'}"
            db.execute(
                "UPDATE workflow_master SET maker_designation_id=?, checker_designation_id=?, "
                "approver_designation_id=?, workflow_role_mapping=? WHERE module_id=?",
                (maker_id or None, checker_id or None, approver_id or None, flow, module_id),
            )
            db.commit()
            flash("Workflow configuration saved.")
        return redirect(url_for("workflow_settings"))

    workflows = query_db(
        "SELECT wm.*, "
        "dm.designation_name AS maker_designation, "
        "dc.designation_name AS checker_designation, "
        "da.designation_name AS approver_designation "
        "FROM workflow_master wm "
        "LEFT JOIN designations dm ON wm.maker_designation_id = dm.id "
        "LEFT JOIN designations dc ON wm.checker_designation_id = dc.id "
        "LEFT JOIN designations da ON wm.approver_designation_id = da.id "
        "ORDER BY wm.module_name"
    )
    designations = query_db(
        "SELECT * FROM designations WHERE status='Active' ORDER BY designation_name"
    )
    return render_template(
        "workflow_settings.html", workflows=workflows, designations=designations
    )


@app.route("/reports/workflow-audit")
@login_required
def workflow_audit_report():
    db = get_db()
    module_id = request.args.get("module_id", "")
    status_key = request.args.get("status", "")
    modules = query_db(
        "SELECT module_id, module_name FROM workflow_master ORDER BY module_name"
    )
    rows = get_workflow_audit_report(
        db,
        module_id=module_id or None,
        status_filter=status_key or None,
    )
    export = request.args.get("export")
    if export == "xlsx" and rows:
        df = pd.DataFrame(rows)
        filename = f"workflow_audit_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.xlsx"
        file_path = os.path.join(REPORTS_DIR, filename)
        df.to_excel(file_path, index=False)
        return send_from_directory(REPORTS_DIR, filename, as_attachment=True)
    return render_template(
        "workflow_audit_report.html",
        rows=rows,
        modules=modules,
        selected_module=module_id,
        selected_status=status_key,
    )


@app.route("/approvals")
@app.route("/approvals/<role>")
@login_required
def approvals(role="checker"):
    db = get_db()
    user_id = session.get("user_id")
    admin = is_admin_user()
    caps = user_workflow_capabilities(db, user_id, admin)
    if role == "maker" and not caps.get("can_create") and not admin:
        role = "checker"
    if role == "checker" and not caps.get("can_verify") and not admin:
        role = "approver" if caps.get("can_approve") else "maker"
    if role == "approver" and not caps.get("can_approve") and not admin:
        role = "checker" if caps.get("can_verify") else "maker"
    counts = get_pending_counts(db, user_id, admin)
    if role == "maker":
        items = _enrich_approval_items(
            db,
            get_pending_items(db, user_id, role, admin),
        )
    else:
        items = _enrich_approval_items(db, get_pending_items(db, user_id, role, admin))
    return render_template(
        "approvals.html", role=role, counts=counts, items=items, module_routes=MODULE_ROUTES
    )


@app.route("/approvals/action", methods=["POST"])
@login_required
def approval_action():
    approval_id = request.form.get("approval_id", "")
    action = request.form.get("action", "")
    comments = request.form.get("comments", "")
    ok, message = advance_approval(
        get_db(),
        int(approval_id),
        session.get("user_id"),
        action,
        comments,
        is_admin_user(),
    )
    get_db().commit()
    flash(message, "success" if ok else "warning")
    role = request.form.get("role") or request.args.get("role") or "checker"
    return redirect(request.referrer or url_for("approvals", role=role))


@app.route("/workflow/reopen", methods=["POST"])
@login_required
def workflow_reopen():
    if not is_admin_user():
        flash("Only System Administrator can reopen transactions.")
        return redirect(request.referrer or url_for("dashboard"))
    approval_id = request.form.get("approval_id", "")
    reason = request.form.get("reason", "")
    ok, message = reopen_transaction(
        get_db(), int(approval_id), session.get("user_id"), reason, True
    )
    get_db().commit()
    flash(message, "success" if ok else "warning")
    return redirect(request.referrer or url_for("approvals"))


@app.route("/workflow/delete", methods=["POST"])
@login_required
def workflow_delete_record():
    table = request.form.get("table", "").strip()
    record_id = request.form.get("record_id", "").strip()
    module_id = request.form.get("module_id", "").strip()
    redirect_to = request.form.get("redirect_to", "dashboard").strip()
    if redirect_to not in MODULE_ROUTES.values() and redirect_to not in (
        "dashboard", "attendance", "timesheet", "approvals", "notifications",
    ):
        redirect_to = "dashboard"
    if not table or not record_id or not module_id:
        flash("Invalid delete request.")
        return redirect(url_for(redirect_to))
    db = get_db()
    ok, message = delete_workflow_record(
        db, table, record_id, module_id,
        session.get("user_id"), is_admin_user(),
    )
    if ok:
        db.commit()
        flash(message, "success")
    else:
        flash(message, "warning")
    return redirect(url_for(redirect_to))


@app.route("/notifications")
@login_required
def notifications():
    db = get_db()
    user_id = session.get("user_id")
    items = get_notifications(db, user_id, limit=50)
    return render_template("notifications.html", items=items)


@app.route("/notifications/read", methods=["POST"])
@login_required
def notifications_read():
    mark_notifications_read(get_db(), session.get("user_id"))
    get_db().commit()
    return redirect(request.referrer or url_for("notifications"))


def _submit_module_request(module_id, table, fields_sql, values):
    db = get_db()
    db.execute(f"INSERT INTO {table}({fields_sql}) VALUES({','.join('?' * len(values))})", values)
    record_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    create_approval_request(
        db, module_id, record_id, table,
        session.get("username", ""), session.get("user_id")
    )
    db.commit()


def _module_edit_context(module_id, table, endpoint):
    record_id = request.form.get("record_id", "").strip()
    if not record_id:
        return None, None
    db = get_db()
    existing = db.execute(
        f"SELECT approval_status FROM {table} WHERE id=?", (record_id,)
    ).fetchone()
    if not existing:
        flash("Record not found.")
        return "redirect", url_for(endpoint)
    edit_role = get_edit_role_for_user(
        db, session.get("user_id"), module_id,
        existing["approval_status"], is_admin_user(),
    )
    if not edit_role:
        flash("This record is locked and cannot be edited.")
        return "redirect", url_for(endpoint)
    return int(record_id), edit_role


def _complete_module_save(db, module_id, table, record_id, edit_role):
    if edit_role == "maker":
        db.execute(
            f"UPDATE {table} SET approval_status=? WHERE id=?",
            ("Pending Checker", record_id),
        )
        resubmit_record(db, module_id, record_id, table, session.get("user_id"))
        flash("Saved. Status: Pending Checker.")
    else:
        flash("Changes saved. Record remains locked at current workflow stage.")
    db.commit()


def _module_page_state(module_id, table, endpoint, record_sql):
    view_id = request.args.get("view")
    edit_id = request.args.get("edit")
    view_record = edit_record = None
    wf_ctx = {}
    if view_id:
        view_record = query_db(record_sql, (view_id,), one=True)
        if view_record:
            wf_ctx = _workflow_view_context(
                module_id, view_record["id"], table, view_record["approval_status"]
            )
    elif edit_id:
        edit_record = query_db(record_sql, (edit_id,), one=True)
        if edit_record:
            edit_role = get_edit_role_for_user(
                get_db(), session.get("user_id"), module_id,
                edit_record["approval_status"], is_admin_user(),
            )
            if not edit_role:
                flash("This record is locked and cannot be edited.")
                return {"redirect": url_for(endpoint, view=edit_id)}
            wf_ctx = {"edit_role": edit_role}
    return {
        "view_record": view_record,
        "edit_record": edit_record,
        "history": wf_ctx.get("history"),
        "edit_role": wf_ctx.get("edit_role"),
        "can_reopen": wf_ctx.get("can_reopen", False),
        "approval_id": wf_ctx.get("approval_id"),
        "module_id": module_id,
    }


@app.route("/material-request", methods=["GET", "POST"])
@login_required
def material_request():
    module_id, table, endpoint = "material_request", "material_requests", "material_request"
    record_sql = (
        "SELECT m.*, p.project_name FROM material_requests m "
        "LEFT JOIN projects p ON m.project_id = p.id WHERE m.id=?"
    )
    projects = query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    workflow = get_workflow_for_module(get_db(), module_id)
    if request.method == "POST":
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        if record_id:
            db = get_db()
            db.execute(
                "UPDATE material_requests SET project_id=?, request_date=?, item_name=?, "
                "quantity=?, unit=?, remarks=? WHERE id=?",
                (
                    request.form.get("project_id") or None,
                    request.form.get("request_date", ""),
                    request.form.get("item_name", ""),
                    float(request.form.get("quantity") or 0),
                    request.form.get("unit", ""),
                    request.form.get("remarks", ""),
                    record_id,
                ),
            )
            _complete_module_save(db, module_id, table, record_id, edit_role)
            return redirect(url_for(endpoint))
        _submit_module_request(
            module_id, table,
            "project_id, request_date, item_name, quantity, unit, remarks, created_by, approval_status",
            (
                request.form.get("project_id") or None,
                request.form.get("request_date", ""),
                request.form.get("item_name", ""),
                float(request.form.get("quantity") or 0),
                request.form.get("unit", ""),
                request.form.get("remarks", ""),
                session.get("username", ""),
                "Pending Checker",
            ),
        )
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db(
        "SELECT m.*, p.project_name FROM material_requests m "
        "LEFT JOIN projects p ON m.project_id = p.id ORDER BY m.id DESC"
    )
    page = _module_page_state(module_id, table, endpoint, record_sql)
    if page.get("redirect"):
        return redirect(page["redirect"])
    return render_template(
        "module_request.html",
        module_title="Store / Material Request",
        workflow=workflow,
        form_fields=[
            {"name": "project_id", "label": "Project", "type": "select", "required": True,
             "options": [{"value": p["id"], "label": p["project_name"]} for p in projects]},
            {"name": "request_date", "label": "Request Date", "type": "date", "required": True},
            {"name": "item_name", "label": "Item Name", "type": "text", "required": True},
            {"name": "quantity", "label": "Quantity", "type": "number", "required": True},
            {"name": "unit", "label": "Unit", "type": "text", "required": False},
            {"name": "remarks", "label": "Remarks", "type": "textarea", "required": False},
        ],
        table_columns=["Date", "Project", "Item", "Qty", "By"],
        row_keys=["request_date", "project_name", "item_name", "quantity", "created_by"],
        rows=[dict(r) for r in rows],
        module_endpoint=endpoint,
        delete_table=table,
        **page,
    )


@app.route("/purchase-request", methods=["GET", "POST"])
@login_required
def purchase_request():
    module_id, table, endpoint = "purchase_request", "purchase_requests", "purchase_request"
    record_sql = (
        "SELECT pr.*, p.project_name FROM purchase_requests pr "
        "LEFT JOIN projects p ON pr.project_id = p.id WHERE pr.id=?"
    )
    projects = query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    workflow = get_workflow_for_module(get_db(), module_id)
    if request.method == "POST":
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        if record_id:
            db = get_db()
            db.execute(
                "UPDATE purchase_requests SET project_id=?, request_date=?, item_description=?, "
                "quantity=?, estimated_cost=?, remarks=? WHERE id=?",
                (
                    request.form.get("project_id") or None,
                    request.form.get("request_date", ""),
                    request.form.get("item_description", ""),
                    float(request.form.get("quantity") or 0),
                    float(request.form.get("estimated_cost") or 0),
                    request.form.get("remarks", ""),
                    record_id,
                ),
            )
            _complete_module_save(db, module_id, table, record_id, edit_role)
            return redirect(url_for(endpoint))
        _submit_module_request(
            module_id, table,
            "project_id, request_date, item_description, quantity, estimated_cost, remarks, created_by, approval_status",
            (
                request.form.get("project_id") or None,
                request.form.get("request_date", ""),
                request.form.get("item_description", ""),
                float(request.form.get("quantity") or 0),
                float(request.form.get("estimated_cost") or 0),
                request.form.get("remarks", ""),
                session.get("username", ""),
                "Pending Checker",
            ),
        )
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db(
        "SELECT pr.*, p.project_name FROM purchase_requests pr "
        "LEFT JOIN projects p ON pr.project_id = p.id ORDER BY pr.id DESC"
    )
    page = _module_page_state(module_id, table, endpoint, record_sql)
    if page.get("redirect"):
        return redirect(page["redirect"])
    return render_template(
        "module_request.html",
        module_title="Purchase Request",
        workflow=workflow,
        form_fields=[
            {"name": "project_id", "label": "Project", "type": "select", "required": True,
             "options": [{"value": p["id"], "label": p["project_name"]} for p in projects]},
            {"name": "request_date", "label": "Request Date", "type": "date", "required": True},
            {"name": "item_description", "label": "Item Description", "type": "text", "required": True},
            {"name": "quantity", "label": "Quantity", "type": "number", "required": True},
            {"name": "estimated_cost", "label": "Estimated Cost", "type": "number", "required": True},
            {"name": "remarks", "label": "Remarks", "type": "textarea", "required": False},
        ],
        table_columns=["Date", "Project", "Description", "Cost", "By"],
        row_keys=["request_date", "project_name", "item_description", "estimated_cost", "created_by"],
        rows=[dict(r) for r in rows],
        module_endpoint=endpoint,
        delete_table=table,
        **page,
    )


@app.route("/project-expenses", methods=["GET", "POST"])
@login_required
def project_expenses():
    module_id, table, endpoint = "project_expenses", "project_expenses", "project_expenses"
    record_sql = (
        "SELECT e.*, p.project_name FROM project_expenses e "
        "LEFT JOIN projects p ON e.project_id = p.id WHERE e.id=?"
    )
    projects = query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    workflow = get_workflow_for_module(get_db(), module_id)
    if request.method == "POST":
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        if record_id:
            db = get_db()
            db.execute(
                "UPDATE project_expenses SET project_id=?, expense_date=?, expense_category=?, "
                "amount=?, description=? WHERE id=?",
                (
                    request.form.get("project_id") or None,
                    request.form.get("expense_date", ""),
                    request.form.get("expense_category", ""),
                    float(request.form.get("amount") or 0),
                    request.form.get("description", ""),
                    record_id,
                ),
            )
            _complete_module_save(db, module_id, table, record_id, edit_role)
            return redirect(url_for(endpoint))
        _submit_module_request(
            module_id, table,
            "project_id, expense_date, expense_category, amount, description, created_by, approval_status",
            (
                request.form.get("project_id") or None,
                request.form.get("expense_date", ""),
                request.form.get("expense_category", ""),
                float(request.form.get("amount") or 0),
                request.form.get("description", ""),
                session.get("username", ""),
                "Pending Checker",
            ),
        )
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db(
        "SELECT e.*, p.project_name FROM project_expenses e "
        "LEFT JOIN projects p ON e.project_id = p.id "
        + ("WHERE e.dpr_measurement_id=?" if request.args.get("dpr_measurement_id", type=int) else "")
        + " ORDER BY e.id DESC",
        ((request.args.get("dpr_measurement_id", type=int),) if request.args.get("dpr_measurement_id", type=int) else ()),
    )
    page = _module_page_state(module_id, table, endpoint, record_sql)
    if page.get("redirect"):
        return redirect(page["redirect"])
    return render_template(
        "module_request.html",
        module_title="Project Expenses",
        workflow=workflow,
        form_fields=[
            {"name": "project_id", "label": "Project", "type": "select", "required": True,
             "options": [{"value": p["id"], "label": p["project_name"]} for p in projects]},
            {"name": "expense_date", "label": "Expense Date", "type": "date", "required": True},
            {"name": "expense_category", "label": "Category", "type": "text", "required": True},
            {"name": "amount", "label": "Amount", "type": "number", "required": True},
            {"name": "description", "label": "Description", "type": "textarea", "required": False},
        ],
        table_columns=["Date", "Project", "Category", "Amount", "DPR", "By"],
        row_keys=["expense_date", "project_name", "expense_category", "amount", "dpr_measurement_id", "created_by"],
        rows=[dict(r) for r in rows],
        module_endpoint=endpoint,
        delete_table=table,
        **page,
    )


@app.route("/head-office-expenses", methods=["GET", "POST"])
@login_required
def head_office_expenses():
    module_id, table, endpoint = "head_office_expenses", "head_office_expenses", "head_office_expenses"
    record_sql = "SELECT * FROM head_office_expenses WHERE id=?"
    workflow = get_workflow_for_module(get_db(), module_id)
    if request.method == "POST":
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        if record_id:
            db = get_db()
            db.execute(
                "UPDATE head_office_expenses SET expense_date=?, expense_category=?, "
                "amount=?, department=?, description=? WHERE id=?",
                (
                    request.form.get("expense_date", ""),
                    request.form.get("expense_category", ""),
                    float(request.form.get("amount") or 0),
                    request.form.get("department", ""),
                    request.form.get("description", ""),
                    record_id,
                ),
            )
            _complete_module_save(db, module_id, table, record_id, edit_role)
            return redirect(url_for(endpoint))
        _submit_module_request(
            module_id, table,
            "expense_date, expense_category, amount, department, description, created_by, approval_status",
            (
                request.form.get("expense_date", ""),
                request.form.get("expense_category", ""),
                float(request.form.get("amount") or 0),
                request.form.get("department", ""),
                request.form.get("description", ""),
                session.get("username", ""),
                "Pending Checker",
            ),
        )
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db("SELECT * FROM head_office_expenses ORDER BY id DESC")
    page = _module_page_state(module_id, table, endpoint, record_sql)
    if page.get("redirect"):
        return redirect(page["redirect"])
    return render_template(
        "module_request.html",
        module_title="Head Office Expenses",
        workflow=workflow,
        form_fields=[
            {"name": "expense_date", "label": "Expense Date", "type": "date", "required": True},
            {"name": "expense_category", "label": "Category", "type": "text", "required": True},
            {"name": "amount", "label": "Amount", "type": "number", "required": True},
            {"name": "department", "label": "Department", "type": "text", "required": True},
            {"name": "description", "label": "Description", "type": "textarea", "required": False},
        ],
        table_columns=["Date", "Category", "Amount", "Department", "By"],
        row_keys=["expense_date", "expense_category", "amount", "department", "created_by"],
        rows=[dict(r) for r in rows],
        module_endpoint=endpoint,
        delete_table=table,
        **page,
    )


@app.route("/subcontract-request", methods=["GET", "POST"])
@login_required
def subcontract_request():
    module_id, table, endpoint = "subcontract", "subcontract_requests", "subcontract_request"
    record_sql = (
        "SELECT s.*, p.project_name, sc.subcontractor_name FROM subcontract_requests s "
        "LEFT JOIN projects p ON s.project_id = p.id "
        "LEFT JOIN subcontractors sc ON s.subcontractor_id = sc.id WHERE s.id=?"
    )
    projects = query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    subcontractors = query_db("SELECT id, subcontractor_name FROM subcontractors ORDER BY subcontractor_name")
    workflow = get_workflow_for_module(get_db(), module_id)
    if request.method == "POST":
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        if record_id:
            db = get_db()
            db.execute(
                "UPDATE subcontract_requests SET project_id=?, subcontractor_id=?, work_description=?, "
                "contract_amount=?, start_date=?, remarks=? WHERE id=?",
                (
                    request.form.get("project_id") or None,
                    request.form.get("subcontractor_id") or None,
                    request.form.get("work_description", ""),
                    float(request.form.get("contract_amount") or 0),
                    request.form.get("start_date", ""),
                    request.form.get("remarks", ""),
                    record_id,
                ),
            )
            _complete_module_save(db, module_id, table, record_id, edit_role)
            return redirect(url_for(endpoint))
        _submit_module_request(
            module_id, table,
            "project_id, subcontractor_id, work_description, contract_amount, start_date, remarks, created_by, approval_status",
            (
                request.form.get("project_id") or None,
                request.form.get("subcontractor_id") or None,
                request.form.get("work_description", ""),
                float(request.form.get("contract_amount") or 0),
                request.form.get("start_date", ""),
                request.form.get("remarks", ""),
                session.get("username", ""),
                "Pending Checker",
            ),
        )
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db(
        "SELECT s.*, p.project_name, sc.subcontractor_name FROM subcontract_requests s "
        "LEFT JOIN projects p ON s.project_id = p.id "
        "LEFT JOIN subcontractors sc ON s.subcontractor_id = sc.id ORDER BY s.id DESC"
    )
    page = _module_page_state(module_id, table, endpoint, record_sql)
    if page.get("redirect"):
        return redirect(page["redirect"])
    return render_template(
        "module_request.html",
        module_title="Subcontract",
        workflow=workflow,
        form_fields=[
            {"name": "project_id", "label": "Project", "type": "select", "required": True,
             "options": [{"value": p["id"], "label": p["project_name"]} for p in projects]},
            {"name": "subcontractor_id", "label": "Subcontractor", "type": "select", "required": True,
             "options": [{"value": s["id"], "label": s["subcontractor_name"]} for s in subcontractors]},
            {"name": "work_description", "label": "Work Description", "type": "text", "required": True},
            {"name": "contract_amount", "label": "Contract Amount", "type": "number", "required": True},
            {"name": "start_date", "label": "Start Date", "type": "date", "required": True},
            {"name": "remarks", "label": "Remarks", "type": "textarea", "required": False},
        ],
        table_columns=["Project", "Subcontractor", "Amount", "Start", "By"],
        row_keys=["project_name", "subcontractor_name", "contract_amount", "start_date", "created_by"],
        rows=[dict(r) for r in rows],
        module_endpoint=endpoint,
        delete_table=table,
        **page,
    )


def _project_options():
    return [
        {"value": project["id"], "label": project["project_name"]}
        for project in query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    ]


def _render_standard_module(module_id, table, endpoint, module_title, form_fields,
                            table_columns, row_keys, record_sql, rows_sql,
                            insert_fields, value_getter, update_sql, update_getter):
    workflow = get_workflow_for_module(get_db(), module_id)
    if request.method == "POST":
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        if record_id:
            db = get_db()
            db.execute(update_sql, (*update_getter(), record_id))
            _complete_module_save(db, module_id, table, record_id, edit_role)
            return redirect(url_for(endpoint))
        _submit_module_request(
            module_id, table, insert_fields,
            (*value_getter(), session.get("username", ""), "Pending Checker"),
        )
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db(rows_sql)
    page = _module_page_state(module_id, table, endpoint, record_sql)
    if page.get("redirect"):
        return redirect(page["redirect"])
    return render_template(
        "module_request.html",
        module_title=module_title,
        workflow=workflow,
        form_fields=form_fields,
        table_columns=table_columns,
        row_keys=row_keys,
        rows=[dict(r) for r in rows],
        module_endpoint=endpoint,
        delete_table=table,
        **page,
    )


def _insert_boq_lines(db, boq_id, project_id, lines, created_by):
    for line in lines:
        db.execute(
            "INSERT INTO boq_items(boq_id, line_no, project_id, item_description, quantity, unit, "
            "rate, amount, created_by, approval_status) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                boq_id, line["line_no"], project_id, line["item_description"],
                line["quantity"], line["unit"], line["rate"], line["amount"],
                created_by, RECORD_PENDING_CHECKER,
            ),
        )


@app.route("/boq-management", methods=["GET", "POST"])
@login_required
def boq_management():
    db = get_db()
    ensure_boq_master_table(db)

    if request.method == "POST":
        project_id = request.form.get("project_id", "").strip()
        boq_id = request.form.get("boq_id", "").strip()
        lines, parse_error = _parse_boq_line_items()

        if not project_id:
            flash("Select a project.")
            return redirect(url_for("boq_management") + "#boq-form")
        if parse_error:
            flash(parse_error)
            return redirect(url_for("boq_management") + "#boq-form")
        if not lines:
            flash("Add at least one BOQ line item with a description.")
            return redirect(url_for("boq_management") + "#boq-form")
        if len(lines) > MAX_BOQ_LINES:
            flash(f"Maximum {MAX_BOQ_LINES} line items allowed per BOQ.")
            return redirect(url_for("boq_management") + "#boq-form")

        total_amount = round(sum(line["amount"] for line in lines), 2)
        created_by = session.get("username", "")
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if boq_id:
            existing_boq = query_db(
                "SELECT * FROM boq_master WHERE id=?", (boq_id,), one=True
            )
            if not existing_boq:
                flash("BOQ record not found.")
                return redirect(url_for("boq_management") + "#boq-form")
            boq_number = existing_boq["boq_number"]
            db.execute(
                "UPDATE boq_master SET project_id=?, total_amount=?, line_count=? WHERE id=?",
                (project_id, total_amount, len(lines), boq_id),
            )
            db.execute("DELETE FROM boq_items WHERE boq_id=?", (boq_id,))
            _insert_boq_lines(db, boq_id, project_id, lines, created_by)
            db.commit()
            flash(
                f"BOQ {boq_number} updated — {len(lines)} item(s), total amount {total_amount:,.2f}."
            )
            return redirect(url_for("boq_management", view=boq_id))

        boq_number = generate_boq_number(db)
        db.execute(
            "INSERT INTO boq_master(boq_number, project_id, total_amount, line_count, "
            "created_by, approval_status, created_at) VALUES(?,?,?,?,?,?,?)",
            (
                boq_number,
                project_id,
                total_amount,
                len(lines),
                created_by,
                RECORD_PENDING_CHECKER,
                created_at,
            ),
        )
        new_boq_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        _insert_boq_lines(db, new_boq_id, project_id, lines, created_by)

        create_approval_request(
            db, "boq", new_boq_id, "boq_master", created_by, session.get("user_id")
        )
        db.commit()
        flash(
            f"BOQ {boq_number} saved — {len(lines)} item(s), total amount {total_amount:,.2f}."
        )
        return redirect(
            url_for(
                "boq_management",
                continue_prompt=1,
                saved=boq_number,
                project_id=project_id,
            )
            + "#boq-form"
        )

    edit_id = request.args.get("edit", type=int)
    editing_boq = None
    editing_lines = []
    if edit_id:
        editing_boq = query_db(
            "SELECT m.*, p.project_code, p.project_name FROM boq_master m "
            "LEFT JOIN projects p ON m.project_id = p.id WHERE m.id=?",
            (edit_id,),
            one=True,
        )
        if not editing_boq:
            flash("BOQ record not found.")
            return redirect(url_for("boq_management"))
        editing_lines = query_db(
            "SELECT * FROM boq_items WHERE boq_id=? ORDER BY line_no, id",
            (edit_id,),
        )

    view_id = request.args.get("view", type=int) if not edit_id else None
    view_boq = None
    view_lines = []
    if view_id:
        view_boq = query_db(
            "SELECT m.*, p.project_code, p.project_name FROM boq_master m "
            "LEFT JOIN projects p ON m.project_id = p.id WHERE m.id=?",
            (view_id,),
            one=True,
        )
        if view_boq:
            view_lines = query_db(
                "SELECT * FROM boq_items WHERE boq_id=? ORDER BY line_no, id",
                (view_id,),
            )

    projects = get_project_options_for_boq()
    next_boq_number = generate_boq_number(db)
    rows = query_db(
        "SELECT m.*, p.project_code, p.project_name FROM boq_master m "
        "LEFT JOIN projects p ON m.project_id = p.id ORDER BY m.id DESC"
    )

    show_continue_prompt = request.args.get("continue_prompt") == "1"
    saved_boq_number = request.args.get("saved", "").strip()
    continue_project_id = (
        request.args.get("project_id", type=int) if show_continue_prompt else None
    )

    return render_template(
        "boq.html",
        projects=projects,
        next_boq_number=next_boq_number,
        boq_units=BOQ_UNITS,
        max_boq_lines=MAX_BOQ_LINES,
        rows=[dict(r) for r in rows],
        view_boq=dict(view_boq) if view_boq else None,
        view_lines=[dict(line) for line in view_lines],
        editing_boq=dict(editing_boq) if editing_boq else None,
        editing_lines=[dict(line) for line in editing_lines],
        show_continue_prompt=show_continue_prompt and bool(saved_boq_number),
        saved_boq_number=saved_boq_number,
        continue_project_id=continue_project_id,
    )


@app.route("/api/steel-shapes", methods=["GET", "POST"])
@login_required
def api_steel_shapes():
    db = get_db()
    ensure_dpr_measurement_tables(db)
    if request.method == "POST":
        shape_name = request.form.get("shape_name", "").strip()
        try:
            side_count = int(request.form.get("side_count") or 1)
        except ValueError:
            side_count = 1
        formula_type = request.form.get("formula_type", "perimeter").strip() or "perimeter"
        if not shape_name:
            return jsonify({"error": "Shape name is required."}), 400
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            "INSERT INTO steel_shapes(shape_name, side_count, formula_type, created_by, created_at) "
            "VALUES(?,?,?,?,?)",
            (shape_name, max(1, side_count), formula_type, session.get("username", ""), now),
        )
        db.commit()
        row = query_db("SELECT * FROM steel_shapes ORDER BY id DESC LIMIT 1", one=True)
        return jsonify(dict(row))
    rows = query_db("SELECT * FROM steel_shapes ORDER BY shape_name, id")
    return jsonify([dict(r) for r in rows])


@app.route("/api/subcontractors/<int:subcontractor_id>/workers")
@login_required
def api_subcontractor_workers(subcontractor_id):
    rows = query_db(
        "SELECT id, worker_code, worker_name, designation FROM workers "
        "WHERE subcontractor_id=? AND (status IS NULL OR status = 'Active') "
        "ORDER BY worker_name",
        (subcontractor_id,),
    )
    return jsonify([dict(r) for r in rows])


def _save_dpr_measurement_from_form():
    project_id = request.form.get("project_id", "").strip()
    report_date = request.form.get("report_date", "").strip()
    boq_item_id = request.form.get("boq_item_id", "").strip()
    boq_number = request.form.get("boq_number", "").strip()
    boq_description = request.form.get("boq_description", "").strip()
    unit = request.form.get("unit", "").strip()
    work_description = request.form.get("work_description", "").strip()
    bill_client = 1 if _is_truthy(request.form.get("bill_client")) else 0
    for_costing = 1 if _is_truthy(request.form.get("for_costing")) else 0
    payload_raw = request.form.get("measurement_payload", "{}")
    manpower_raw = request.form.get("manpower_payload", "[]")
    materials_raw = request.form.get("materials_payload", "[]")
    equipment_raw = request.form.get("equipment_payload", "[]")
    additional_details = request.form.get("additional_details", "").strip()

    if not project_id:
        flash("Select a project.")
        return None
    if not report_date:
        flash("Report date is required.")
        return None
    if not boq_item_id:
        flash("Select a BOQ line item.")
        return None

    try:
        payload = json.loads(payload_raw or "{}")
    except json.JSONDecodeError:
        flash("Invalid measurement data.")
        return None
    try:
        manpower_rows = json.loads(manpower_raw or "[]")
    except json.JSONDecodeError:
        manpower_rows = []
    try:
        materials_rows = json.loads(materials_raw or "[]")
    except json.JSONDecodeError:
        materials_rows = []
    try:
        equipment_rows = json.loads(equipment_raw or "[]")
    except json.JSONDecodeError:
        equipment_rows = []

    parsed = _parse_dpr_measurement_payload(payload, unit)
    if parsed["quantity"] <= 0:
        flash("Enter valid measurements — calculated quantity is zero.")
        return None

    if not bill_client and not for_costing:
        for_costing = 1

    measurement_store = dict(parsed["data"])
    if materials_rows:
        measurement_store["materials"] = materials_rows
    if equipment_rows:
        measurement_store["equipment"] = equipment_rows
    if additional_details:
        measurement_store["additional_details"] = additional_details

    db = get_db()
    prepare_dpr_page_db(db)
    created_by = session.get("username", "")
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    billing_status = "pending" if bill_client else "none"
    costing_status = "pending" if for_costing else "none"

    db.execute(
        "INSERT INTO dpr_measurements(project_id, report_date, boq_item_id, boq_number, "
        "boq_description, unit, calculated_quantity, measurement_type, bill_client, for_costing, "
        "billing_status, costing_status, measurement_data, work_description, created_by, approval_status, created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            project_id,
            report_date,
            boq_item_id,
            boq_number,
            boq_description,
            unit,
            parsed["quantity"],
            parsed["type"],
            bill_client,
            for_costing,
            billing_status,
            costing_status,
            json.dumps(measurement_store),
            work_description,
            created_by,
            RECORD_PENDING_CHECKER,
            created_at,
        ),
    )
    measurement_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    if parsed["type"] == "steel":
        for line in parsed["data"].get("lines") or []:
            db.execute(
                "INSERT INTO dpr_steel_lines(measurement_id, line_description, num_bars, cutting_length, "
                "diameter_mm, shape_id, side_measurements, quantity) VALUES(?,?,?,?,?,?,?,?)",
                (
                    measurement_id,
                    line.get("description", ""),
                    int(line.get("num_bars") or 0),
                    float(line.get("cutting_length_m") or 0),
                    float(line.get("diameter_mm") or 0),
                    line.get("shape_id") or None,
                    json.dumps(line.get("side_measurements") or []),
                    float(line.get("quantity") or 0),
                ),
            )

    if for_costing and manpower_rows:
        for mp in manpower_rows:
            db.execute(
                "INSERT INTO dpr_manpower(measurement_id, subcontractor_id, worker_id, worker_name, "
                "trade_name, hours_worked, remarks) VALUES(?,?,?,?,?,?,?)",
                (
                    measurement_id,
                    mp.get("subcontractor_id") or None,
                    mp.get("worker_id") or None,
                    mp.get("worker_name", ""),
                    mp.get("trade_name", ""),
                    float(mp.get("hours_worked") or 0),
                    mp.get("remarks", ""),
                ),
            )

    create_approval_request(
        db, "dpr", measurement_id, "dpr_measurements", created_by, session.get("user_id")
    )
    db.commit()
    return {
        "id": measurement_id,
        "quantity": parsed["quantity"],
        "project_id": project_id,
        "boq_number": boq_number,
        "boq_description": boq_description,
        "bill_client": bill_client,
    }


@app.route("/dpr-entry", methods=["GET", "POST"])
@login_required
def dpr_entry():
    db = get_db()
    prepare_dpr_page_db(db)

    if request.method == "POST":
        saved = _save_dpr_measurement_from_form()
        if not saved:
            return redirect(url_for("dpr_entry") + "#dpr-form")

        flash(
            f"DPR measurement saved — qty {saved['quantity']:,.4f} for {saved['boq_description']}."
            + (
                " Sent to Client Bill Pending."
                if saved.get("bill_client")
                else " Recorded for costing / quantity."
            )
        )
        return redirect(
            url_for(
                "dpr_entry",
                continue_prompt=1,
                project_id=saved["project_id"],
                boq_number=saved["boq_number"],
                saved_qty=saved["quantity"],
            )
            + "#dpr-form"
        )

    projects = get_project_options_for_boq()
    subcontractors = query_db(
        "SELECT id, subcontractor_name, subcontractor_code FROM subcontractors "
        "WHERE status IS NULL OR status = 'Active' ORDER BY subcontractor_name"
    )
    steel_shapes = query_db("SELECT * FROM steel_shapes ORDER BY shape_name, id")
    records = query_db(
        "SELECT m.*, p.project_code, p.project_name FROM dpr_measurements m "
        "LEFT JOIN projects p ON m.project_id = p.id ORDER BY m.id DESC LIMIT 100"
    )

    show_continue_prompt = request.args.get("continue_prompt") == "1"
    continue_project_id = request.args.get("project_id", type=int) if show_continue_prompt else None
    continue_boq_number = request.args.get("boq_number", "").strip() if show_continue_prompt else ""
    saved_qty = request.args.get("saved_qty", "")

    return render_template(
        "dpr.html",
        projects=[dict(p) for p in projects],
        subcontractors=[dict(s) for s in subcontractors],
        steel_shapes=[dict(s) for s in steel_shapes],
        steel_diameters=STEEL_DIAMETERS_MM,
        records=[dict(r) for r in records],
        show_continue_prompt=show_continue_prompt,
        continue_project_id=continue_project_id,
        continue_boq_number=continue_boq_number,
        saved_qty=saved_qty,
        active_tab="entry",
    )


@app.route("/dpr-client-bill-pending", methods=["GET", "POST"])
@login_required
def dpr_client_bill_pending():
    db = get_db()
    prepare_dpr_page_db(db)

    if request.method == "POST" and request.form.get("form_action") == "mark_billed":
        bill_id = request.form.get("measurement_id", type=int)
        if bill_id:
            db.execute(
                "UPDATE dpr_measurements SET billing_status='billed' WHERE id=?",
                (bill_id,),
            )
            db.commit()
            flash("Measurement marked as billed to client.")

    pending_bills = _fetch_client_bill_rows()
    projects = get_project_options_for_boq()
    subcontractors = query_db(
        "SELECT id, subcontractor_name FROM subcontractors "
        "WHERE status IS NULL OR status = 'Active' ORDER BY subcontractor_name"
    )
    steel_shapes = query_db("SELECT * FROM steel_shapes ORDER BY shape_name, id")

    return render_template(
        "dpr.html",
        projects=[dict(p) for p in projects],
        subcontractors=[dict(s) for s in subcontractors],
        steel_shapes=[dict(s) for s in steel_shapes],
        steel_diameters=STEEL_DIAMETERS_MM,
        records=[],
        pending_bills=[dict(r) for r in pending_bills],
        show_continue_prompt=False,
        continue_project_id=None,
        continue_boq_number="",
        saved_qty="",
        active_tab="client_bill",
    )


@app.route("/dpr-costing-pending", methods=["GET", "POST"])
@login_required
def dpr_costing_pending():
    db = get_db()
    prepare_dpr_page_db(db)

    if request.method == "POST" and request.form.get("form_action") == "mark_costed":
        rec_id = request.form.get("measurement_id", type=int)
        if rec_id:
            db.execute(
                "UPDATE dpr_measurements SET costing_status='completed' WHERE id=?",
                (rec_id,),
            )
            db.commit()
            flash("Measurement marked as costed.")
    elif request.method == "POST" and request.form.get("form_action") == "push_to_costing":
        rec_id = request.form.get("measurement_id", type=int)
        if rec_id:
            ok, message = _push_dpr_to_project_costing(db, rec_id)
            if ok:
                flash(f"{message} View in Project Costing.")
            else:
                flash(message)

    costing_pending = query_db(
        "SELECT m.*, p.project_code, p.project_name FROM dpr_measurements m "
        "LEFT JOIN projects p ON m.project_id = p.id "
        "WHERE m.for_costing=1 AND m.costing_status IN ('pending', 'linked') "
        "ORDER BY m.report_date DESC, m.id DESC"
    )
    costing_ids = [row["id"] for row in costing_pending]
    manpower_map = {}
    if costing_ids:
        placeholders = ",".join("?" * len(costing_ids))
        mp_rows = query_db(
            f"SELECT mp.*, s.subcontractor_name FROM dpr_manpower mp "
            f"LEFT JOIN subcontractors s ON mp.subcontractor_id = s.id "
            f"WHERE mp.measurement_id IN ({placeholders})",
            costing_ids,
        )
        for row in mp_rows:
            manpower_map.setdefault(row["measurement_id"], []).append(dict(row))

    resources_map = {}
    for row in costing_pending:
        try:
            data = json.loads(row["measurement_data"] or "{}")
        except (json.JSONDecodeError, TypeError):
            data = {}
        resources_map[row["id"]] = {
            "materials": data.get("materials") or [],
            "equipment": data.get("equipment") or [],
            "additional": data.get("additional_details") or "",
        }

    projects = get_project_options_for_boq()
    subcontractors = query_db(
        "SELECT id, subcontractor_name FROM subcontractors "
        "WHERE status IS NULL OR status = 'Active' ORDER BY subcontractor_name"
    )
    steel_shapes = query_db("SELECT * FROM steel_shapes ORDER BY shape_name, id")

    return render_template(
        "dpr.html",
        projects=[dict(p) for p in projects],
        subcontractors=[dict(s) for s in subcontractors],
        steel_shapes=[dict(s) for s in steel_shapes],
        steel_diameters=STEEL_DIAMETERS_MM,
        records=[],
        costing_pending=[dict(r) for r in costing_pending],
        manpower_map=manpower_map,
        resources_map=resources_map,
        show_continue_prompt=False,
        continue_project_id=None,
        continue_boq_number="",
        saved_qty="",
        active_tab="costing",
    )


@app.route("/dpr-client-bill-print")
@login_required
def dpr_client_bill_print():
    ids_param = request.args.get("ids", "").strip()
    measurement_ids = None
    if ids_param:
        measurement_ids = [int(x) for x in ids_param.split(",") if x.strip().isdigit()]
    pending_only = not measurement_ids
    rows = _fetch_client_bill_rows(measurement_ids=measurement_ids, pending_only=pending_only)
    if measurement_ids and not rows:
        rows = _fetch_client_bill_rows(measurement_ids=measurement_ids, pending_only=False)
    bills = [dict(r) for r in rows]
    total_amount = round(sum(float(b.get("bill_amount") or 0) for b in bills), 2)
    return render_template(
        "dpr_client_bill_print.html",
        bills=bills,
        total_amount=total_amount,
        autoprint=request.args.get("print") == "1",
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/dpr-client-bill-print/<int:measurement_id>")
@login_required
def dpr_client_bill_print_one(measurement_id):
    rows = _fetch_client_bill_rows(measurement_ids=[measurement_id], pending_only=False)
    bills = [dict(r) for r in rows]
    if not bills:
        flash("Client bill measurement not found.")
        return redirect(url_for("dpr_client_bill_pending"))
    total_amount = round(sum(float(b.get("bill_amount") or 0) for b in bills), 2)
    return render_template(
        "dpr_client_bill_print.html",
        bills=bills,
        total_amount=total_amount,
        autoprint=request.args.get("print") == "1",
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/dpr-client-bill-export")
@login_required
def dpr_client_bill_export():
    rows = _fetch_client_bill_rows()
    if not rows:
        flash("No pending client bills to export.")
        return redirect(url_for("dpr_client_bill_pending"))
    records = []
    for row in rows:
        row = dict(row)
        client_name = row["company_name"] or row["client_name"] or row["private_client_name"] or ""
        records.append({
            "Date": row["report_date"],
            "Project Code": row["project_code"] or row["project_id"],
            "Project Name": row["project_name"],
            "Client": client_name,
            "BOQ No": row["boq_number"],
            "Description": row["boq_description"],
            "Work Description": row.get("work_description") or "",
            "Unit": row["unit"],
            "Quantity": row["calculated_quantity"],
            "Rate": row["boq_rate"],
            "Amount": row["bill_amount"],
            "GST No": row["gst_number"] or "",
        })
    df = pd.DataFrame(records)
    filename = f"client_bill_pending_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    file_path = os.path.join(REPORTS_DIR, filename)
    df.to_excel(file_path, index=False)
    return send_from_directory(REPORTS_DIR, filename, as_attachment=True)


@app.route("/dpr-entry-legacy", methods=["GET", "POST"])
@login_required
def dpr_entry_legacy():
    fields = [
        {"name": "project_id", "label": "Project", "type": "select", "required": True, "options": _project_options()},
        {"name": "report_date", "label": "Report Date", "type": "date", "required": True},
        {"name": "prepared_by", "label": "Prepared By", "type": "text", "required": True},
        {"name": "work_done", "label": "Work Done", "type": "textarea", "required": True},
        {"name": "manpower_count", "label": "Manpower Count", "type": "number", "required": False},
        {"name": "material_used", "label": "Material Used", "type": "textarea", "required": False},
        {"name": "issues", "label": "Issues / Delay Reasons", "type": "textarea", "required": False},
        {"name": "progress_percent", "label": "Progress %", "type": "number", "required": False},
    ]
    return _render_standard_module(
        "dpr", "dpr_entries", "dpr_entry", "DPR Entry", fields,
        ["Date", "Project", "Prepared By", "Manpower", "Progress %"],
        ["report_date", "project_name", "prepared_by", "manpower_count", "progress_percent"],
        "SELECT d.*, p.project_name FROM dpr_entries d LEFT JOIN projects p ON d.project_id = p.id WHERE d.id=?",
        "SELECT d.*, p.project_name FROM dpr_entries d LEFT JOIN projects p ON d.project_id = p.id ORDER BY d.id DESC",
        "project_id, report_date, prepared_by, work_done, manpower_count, material_used, issues, progress_percent, created_by, approval_status",
        lambda: (
            request.form.get("project_id") or None,
            request.form.get("report_date", ""),
            request.form.get("prepared_by", ""),
            request.form.get("work_done", ""),
            int(float(request.form.get("manpower_count") or 0)),
            request.form.get("material_used", ""),
            request.form.get("issues", ""),
            float(request.form.get("progress_percent") or 0),
        ),
        "UPDATE dpr_entries SET project_id=?, report_date=?, prepared_by=?, work_done=?, manpower_count=?, material_used=?, issues=?, progress_percent=? WHERE id=?",
        lambda: (
            request.form.get("project_id") or None,
            request.form.get("report_date", ""),
            request.form.get("prepared_by", ""),
            request.form.get("work_done", ""),
            int(float(request.form.get("manpower_count") or 0)),
            request.form.get("material_used", ""),
            request.form.get("issues", ""),
            float(request.form.get("progress_percent") or 0),
        ),
    )


@app.route("/manager-tool", methods=["GET", "POST"])
@login_required
def manager_tool():
    fields = [
        {"name": "project_id", "label": "Project", "type": "select", "required": False, "options": _project_options()},
        {"name": "task_date", "label": "Task Date", "type": "date", "required": True},
        {"name": "manager_name", "label": "Manager Name", "type": "text", "required": True},
        {"name": "action_item", "label": "Action Item", "type": "textarea", "required": True},
        {"name": "priority", "label": "Priority", "type": "select", "required": True,
         "options": [{"value": "High", "label": "High"}, {"value": "Medium", "label": "Medium"}, {"value": "Low", "label": "Low"}]},
        {"name": "target_date", "label": "Target Date", "type": "date", "required": False},
        {"name": "remarks", "label": "Remarks", "type": "textarea", "required": False},
    ]
    return _render_standard_module(
        "manager_tool", "manager_tasks", "manager_tool", "Manager Action Items", fields,
        ["Date", "Project", "Manager", "Priority", "Target"],
        ["task_date", "project_name", "manager_name", "priority", "target_date"],
        "SELECT m.*, p.project_name FROM manager_tasks m LEFT JOIN projects p ON m.project_id = p.id WHERE m.id=?",
        "SELECT m.*, p.project_name FROM manager_tasks m LEFT JOIN projects p ON m.project_id = p.id ORDER BY m.id DESC",
        "project_id, task_date, manager_name, action_item, priority, target_date, remarks, created_by, approval_status",
        lambda: (
            request.form.get("project_id") or None,
            request.form.get("task_date", ""),
            request.form.get("manager_name", ""),
            request.form.get("action_item", ""),
            request.form.get("priority", ""),
            request.form.get("target_date", ""),
            request.form.get("remarks", ""),
        ),
        "UPDATE manager_tasks SET project_id=?, task_date=?, manager_name=?, action_item=?, priority=?, target_date=?, remarks=? WHERE id=?",
        lambda: (
            request.form.get("project_id") or None,
            request.form.get("task_date", ""),
            request.form.get("manager_name", ""),
            request.form.get("action_item", ""),
            request.form.get("priority", ""),
            request.form.get("target_date", ""),
            request.form.get("remarks", ""),
        ),
    )


def _account_transaction_page(transaction_type, module_id, endpoint, title):
    fields = [
        {"name": "project_id", "label": "Project", "type": "select", "required": False, "options": _project_options()},
        {"name": "transaction_date", "label": "Date", "type": "date", "required": True},
        {"name": "party_name", "label": "Party Name", "type": "text", "required": True},
        {"name": "account_head", "label": "Account Head", "type": "text", "required": True},
        {"name": "amount", "label": "Amount", "type": "number", "required": True},
        {"name": "payment_mode", "label": "Payment Mode", "type": "select", "required": True,
         "options": [{"value": "Cash", "label": "Cash"}, {"value": "Bank", "label": "Bank"}, {"value": "UPI", "label": "UPI"}, {"value": "Cheque", "label": "Cheque"}]},
        {"name": "reference_no", "label": "Reference No", "type": "text", "required": False},
        {"name": "tax_percent", "label": "Tax %", "type": "number", "required": False},
        {"name": "remarks", "label": "Remarks", "type": "textarea", "required": False},
    ]
    return _render_standard_module(
        module_id, "account_transactions", endpoint, title, fields,
        ["Date", "Project", "Party", "Head", "Amount"],
        ["transaction_date", "project_name", "party_name", "account_head", "amount"],
        "SELECT a.*, p.project_name FROM account_transactions a LEFT JOIN projects p ON a.project_id = p.id WHERE a.id=?",
        "SELECT a.*, p.project_name FROM account_transactions a LEFT JOIN projects p ON a.project_id = p.id "
        f"WHERE a.transaction_type='{transaction_type}' ORDER BY a.id DESC",
        "transaction_type, project_id, transaction_date, party_name, account_head, amount, payment_mode, reference_no, tax_percent, remarks, created_by, approval_status",
        lambda: (
            transaction_type,
            request.form.get("project_id") or None,
            request.form.get("transaction_date", ""),
            request.form.get("party_name", ""),
            request.form.get("account_head", ""),
            float(request.form.get("amount") or 0),
            request.form.get("payment_mode", ""),
            request.form.get("reference_no", ""),
            float(request.form.get("tax_percent") or 0),
            request.form.get("remarks", ""),
        ),
        "UPDATE account_transactions SET transaction_type=?, project_id=?, transaction_date=?, party_name=?, account_head=?, amount=?, payment_mode=?, reference_no=?, tax_percent=?, remarks=? WHERE id=?",
        lambda: (
            transaction_type,
            request.form.get("project_id") or None,
            request.form.get("transaction_date", ""),
            request.form.get("party_name", ""),
            request.form.get("account_head", ""),
            float(request.form.get("amount") or 0),
            request.form.get("payment_mode", ""),
            request.form.get("reference_no", ""),
            float(request.form.get("tax_percent") or 0),
            request.form.get("remarks", ""),
        ),
    )


@app.route("/accounts/receipts", methods=["GET", "POST"])
@login_required
def account_receipts():
    return _account_transaction_page("Receipt", "account_receipt", "account_receipts", "Accounts Receipts")


@app.route("/accounts/payments", methods=["GET", "POST"])
@login_required
def account_payments():
    return _account_transaction_page("Payment", "account_payment", "account_payments", "Accounts Payments")


@app.route("/accounts/gst", methods=["GET", "POST"])
@login_required
def account_gst():
    return _account_transaction_page("GST", "account_gst", "account_gst", "GST Entries")


@app.route("/accounts/tds", methods=["GET", "POST"])
@login_required
def account_tds():
    return _account_transaction_page("TDS", "account_tds", "account_tds", "TDS Entries")


def _accounts_book(title, payment_mode=None):
    params = []
    where = "WHERE a.approval_status='Approved'"
    if payment_mode:
        where += " AND a.payment_mode=?"
        params.append(payment_mode)
    rows = query_db(
        "SELECT a.*, p.project_name FROM account_transactions a "
        "LEFT JOIN projects p ON a.project_id = p.id "
        f"{where} ORDER BY a.transaction_date DESC, a.id DESC",
        tuple(params),
    )
    receipts = sum(float(row["amount"] or 0) for row in rows if row["transaction_type"] == "Receipt")
    payments = sum(float(row["amount"] or 0) for row in rows if row["transaction_type"] != "Receipt")
    return render_template(
        "accounts_book.html",
        page_title=title,
        rows=rows,
        receipts=receipts,
        payments=payments,
        balance=receipts - payments,
    )


@app.route("/accounts/cash-book")
@login_required
def cash_book():
    return _accounts_book("Cash Book", "Cash")


@app.route("/accounts/bank-book")
@login_required
def bank_book():
    return _accounts_book("Bank Book", "Bank")


@app.route("/accounts/ledger")
@login_required
def ledger():
    return _accounts_book("Ledger")


@app.route("/leave-request", methods=["GET", "POST"])
@login_required
def leave_request():
    module_id, table, endpoint = "leave_request", "leave_requests", "leave_request"
    record_sql = "SELECT * FROM leave_requests WHERE id=?"
    workflow = get_workflow_for_module(get_db(), module_id)
    if request.method == "POST":
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        if record_id:
            db = get_db()
            db.execute(
                "UPDATE leave_requests SET employee_name=?, leave_type=?, from_date=?, "
                "to_date=?, days=?, reason=? WHERE id=?",
                (
                    request.form.get("employee_name", ""),
                    request.form.get("leave_type", ""),
                    request.form.get("from_date", ""),
                    request.form.get("to_date", ""),
                    float(request.form.get("days") or 0),
                    request.form.get("reason", ""),
                    record_id,
                ),
            )
            _complete_module_save(db, module_id, table, record_id, edit_role)
            return redirect(url_for(endpoint))
        _submit_module_request(
            module_id, table,
            "employee_name, leave_type, from_date, to_date, days, reason, created_by, approval_status",
            (
                request.form.get("employee_name", ""),
                request.form.get("leave_type", ""),
                request.form.get("from_date", ""),
                request.form.get("to_date", ""),
                float(request.form.get("days") or 0),
                request.form.get("reason", ""),
                session.get("username", ""),
                "Pending Checker",
            ),
        )
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db("SELECT * FROM leave_requests ORDER BY id DESC")
    page = _module_page_state(module_id, table, endpoint, record_sql)
    if page.get("redirect"):
        return redirect(page["redirect"])
    return render_template(
        "module_request.html",
        module_title="Leave Request",
        workflow=workflow,
        form_fields=[
            {"name": "employee_name", "label": "Employee Name", "type": "text", "required": True},
            {"name": "leave_type", "label": "Leave Type", "type": "text", "required": True},
            {"name": "from_date", "label": "From Date", "type": "date", "required": True},
            {"name": "to_date", "label": "To Date", "type": "date", "required": True},
            {"name": "days", "label": "Days", "type": "number", "required": True},
            {"name": "reason", "label": "Reason", "type": "textarea", "required": False},
        ],
        table_columns=["Employee", "Type", "From", "To", "Days"],
        row_keys=["employee_name", "leave_type", "from_date", "to_date", "days"],
        rows=[dict(r) for r in rows],
        module_endpoint=endpoint,
        delete_table=table,
        **page,
    )


@app.route("/store-issue", methods=["GET", "POST"])
@login_required
def store_issue():
    module_id, table, endpoint = "store_issue", "store_issues", "store_issue"
    record_sql = (
        "SELECT s.*, p.project_name FROM store_issues s "
        "LEFT JOIN projects p ON s.project_id = p.id WHERE s.id=?"
    )
    projects = query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    workflow = get_workflow_for_module(get_db(), module_id)
    if request.method == "POST":
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        if record_id:
            db = get_db()
            db.execute(
                "UPDATE store_issues SET project_id=?, issue_date=?, item_name=?, "
                "quantity=?, unit=?, issued_to=?, remarks=? WHERE id=?",
                (
                    request.form.get("project_id") or None,
                    request.form.get("issue_date", ""),
                    request.form.get("item_name", ""),
                    float(request.form.get("quantity") or 0),
                    request.form.get("unit", ""),
                    request.form.get("issued_to", ""),
                    request.form.get("remarks", ""),
                    record_id,
                ),
            )
            _complete_module_save(db, module_id, table, record_id, edit_role)
            return redirect(url_for(endpoint))
        _submit_module_request(
            module_id, table,
            "project_id, issue_date, item_name, quantity, unit, issued_to, remarks, created_by, approval_status",
            (
                request.form.get("project_id") or None,
                request.form.get("issue_date", ""),
                request.form.get("item_name", ""),
                float(request.form.get("quantity") or 0),
                request.form.get("unit", ""),
                request.form.get("issued_to", ""),
                request.form.get("remarks", ""),
                session.get("username", ""),
                "Pending Checker",
            ),
        )
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db(
        "SELECT s.*, p.project_name FROM store_issues s "
        "LEFT JOIN projects p ON s.project_id = p.id ORDER BY s.id DESC"
    )
    page = _module_page_state(module_id, table, endpoint, record_sql)
    if page.get("redirect"):
        return redirect(page["redirect"])
    return render_template(
        "module_request.html",
        module_title="Store Issue",
        workflow=workflow,
        form_fields=[
            {"name": "project_id", "label": "Project", "type": "select", "required": True,
             "options": [{"value": p["id"], "label": p["project_name"]} for p in projects]},
            {"name": "issue_date", "label": "Issue Date", "type": "date", "required": True},
            {"name": "item_name", "label": "Item Name", "type": "text", "required": True},
            {"name": "quantity", "label": "Quantity", "type": "number", "required": True},
            {"name": "unit", "label": "Unit", "type": "text", "required": False},
            {"name": "issued_to", "label": "Issued To", "type": "text", "required": True},
            {"name": "remarks", "label": "Remarks", "type": "textarea", "required": False},
        ],
        table_columns=["Date", "Project", "Item", "Qty", "Issued To", "By"],
        row_keys=["issue_date", "project_name", "item_name", "quantity", "issued_to", "created_by"],
        rows=[dict(r) for r in rows],
        module_endpoint=endpoint,
        delete_table=table,
        **page,
    )


@app.route("/store-receipt", methods=["GET", "POST"])
@login_required
def store_receipt():
    module_id, table, endpoint = "store_receipt", "store_receipts", "store_receipt"
    record_sql = (
        "SELECT s.*, p.project_name FROM store_receipts s "
        "LEFT JOIN projects p ON s.project_id = p.id WHERE s.id=?"
    )
    projects = query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    workflow = get_workflow_for_module(get_db(), module_id)
    if request.method == "POST":
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        if record_id:
            db = get_db()
            db.execute(
                "UPDATE store_receipts SET project_id=?, receipt_date=?, item_name=?, "
                "quantity=?, unit=?, supplier=?, remarks=? WHERE id=?",
                (
                    request.form.get("project_id") or None,
                    request.form.get("receipt_date", ""),
                    request.form.get("item_name", ""),
                    float(request.form.get("quantity") or 0),
                    request.form.get("unit", ""),
                    request.form.get("supplier", ""),
                    request.form.get("remarks", ""),
                    record_id,
                ),
            )
            _complete_module_save(db, module_id, table, record_id, edit_role)
            return redirect(url_for(endpoint))
        _submit_module_request(
            module_id, table,
            "project_id, receipt_date, item_name, quantity, unit, supplier, remarks, created_by, approval_status",
            (
                request.form.get("project_id") or None,
                request.form.get("receipt_date", ""),
                request.form.get("item_name", ""),
                float(request.form.get("quantity") or 0),
                request.form.get("unit", ""),
                request.form.get("supplier", ""),
                request.form.get("remarks", ""),
                session.get("username", ""),
                "Pending Checker",
            ),
        )
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db(
        "SELECT s.*, p.project_name FROM store_receipts s "
        "LEFT JOIN projects p ON s.project_id = p.id ORDER BY s.id DESC"
    )
    page = _module_page_state(module_id, table, endpoint, record_sql)
    if page.get("redirect"):
        return redirect(page["redirect"])
    return render_template(
        "module_request.html",
        module_title="Store Receipt",
        workflow=workflow,
        form_fields=[
            {"name": "project_id", "label": "Project", "type": "select", "required": True,
             "options": [{"value": p["id"], "label": p["project_name"]} for p in projects]},
            {"name": "receipt_date", "label": "Receipt Date", "type": "date", "required": True},
            {"name": "item_name", "label": "Item Name", "type": "text", "required": True},
            {"name": "quantity", "label": "Quantity", "type": "number", "required": True},
            {"name": "unit", "label": "Unit", "type": "text", "required": False},
            {"name": "supplier", "label": "Supplier", "type": "text", "required": True},
            {"name": "remarks", "label": "Remarks", "type": "textarea", "required": False},
        ],
        table_columns=["Date", "Project", "Item", "Qty", "Supplier", "By"],
        row_keys=["receipt_date", "project_name", "item_name", "quantity", "supplier", "created_by"],
        rows=[dict(r) for r in rows],
        module_endpoint=endpoint,
        delete_table=table,
        **page,
    )


@app.route("/timesheet")
@login_required
def timesheet():
    rows = query_db(
        "SELECT a.id, a.attendance_date, a.in_time AS start_time, a.out_time AS end_time, "
        "a.break_hours, a.total_hours AS worked_hours, a.ot_hours AS overtime, "
        "a.approval_status, "
        "COALESCE(w.worker_name, s.staff_name) AS worker_name, "
        "COALESCE(w.worker_code, s.employee_code) AS worker_code, "
        "p.project_name, p.project_code "
        "FROM attendance a "
        f"{ATTENDANCE_WORKER_JOIN_SQL} "
        "LEFT JOIN projects p ON a.project_id = p.id "
        "ORDER BY a.id DESC LIMIT 50"
    )
    return render_template("timesheet.html", rows=rows)


@app.route("/accounts")
@login_required
def accounts():
    return redirect(url_for("head_office_expenses"))


@app.route("/store")
@login_required
def store():
    return redirect(url_for("material_request"))


@app.route("/purchase")
@login_required
def purchase():
    return redirect(url_for("purchase_request"))


@app.route("/inventory")
@login_required
def inventory():
    return render_template(
        "module_placeholder.html",
        page_title="Inventory",
        breadcrumb_section="Operations",
        module_description="Stock levels, batch tracking, and warehouse balances will appear here.",
    )


if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True)
