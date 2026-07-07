"""Flask routes for bulk import — template download, validate, save."""

from __future__ import annotations

import json
from typing import Any, Callable

from flask import Response, jsonify, request, send_file, session

from bulk_import_service import (
    build_xlsx_template,
    error_row,
    parse_upload,
    validate_account,
    validate_date_value,
    validate_duplicates,
    validate_gst,
    validate_pan,
    validate_required,
    validate_unit,
    validation_result,
)
try:
    from accounts_import_service import (
        customer_import_template,
        save_customer_import,
        validate_customer_import,
        validate_customer_import_rows,
    )
except ImportError:
    customer_import_template = None
    save_customer_import = None
    validate_customer_import = None
    validate_customer_import_rows = None

from vendor_import_service import (
    save_vendor_import,
    validate_vendor_import,
    validate_vendor_import_rows,
)
from vendor_master_service import vendor_import_template
from boq_import_service import (
    boq_import_template,
    save_boq_import,
    validate_boq_import,
)
from import_audit_service import log_import

try:
    from company_import_service import save_company_import, validate_company_import_rows
except ImportError:
    save_company_import = None
    validate_company_import_rows = None

try:
    from branch_import_service import save_branch_import, validate_branch_import_rows
except ImportError:
    save_branch_import = None
    validate_branch_import_rows = None

try:
    from department_import_service import save_department_import, validate_department_import_rows
except ImportError:
    save_department_import = None
    validate_department_import_rows = None

try:
    from user_import_service import save_user_import, validate_user_import_rows
except ImportError:
    save_user_import = None
    validate_user_import_rows = None

try:
    from designation_import_service import save_designation_import, validate_designation_import_rows
except ImportError:
    save_designation_import = None
    validate_designation_import_rows = None

try:
    from client_import_service import save_client_import, validate_client_import_rows
except ImportError:
    save_client_import = None
    validate_client_import_rows = None

try:
    from employee_import_service import save_employee_import, validate_employee_import_rows
except ImportError:
    save_employee_import = None
    validate_employee_import_rows = None

try:
    from project_import_service import save_project_import, validate_project_import_rows
except ImportError:
    save_project_import = None
    validate_project_import_rows = None

try:
    from subcontractor_import_service import (
        save_subcontractor_import,
        validate_subcontractor_import,
        validate_subcontractor_import_rows,
    )
except ImportError:
    save_subcontractor_import = None
    validate_subcontractor_import = None
    validate_subcontractor_import_rows = None

try:
    from worker_import_service import (
        save_worker_import,
        validate_worker_import,
        validate_worker_import_rows,
    )
except ImportError:
    save_worker_import = None
    validate_worker_import = None
    validate_worker_import_rows = None

try:
    from roles_permissions_import_service import save_roles_import, validate_roles_import_rows
except ImportError:
    save_roles_import = None
    validate_roles_import_rows = None

try:
    from document_import_service import save_document_import, validate_document_import_rows
except ImportError:
    save_document_import = None
    validate_document_import_rows = None


def _username(session_obj) -> str:
    return str(session_obj.get("username") or "")


def _validate_vendors_rows(db, rows: list[dict]) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    errors.extend(validate_duplicates(rows, "vendor_code", "Vendor Code"))
    errors.extend(validate_duplicates(rows, "code", "Vendor Code"))
    parsed: list[dict] = []
    for row in rows:
        code = str(row.get("vendor_code") or row.get("code") or "").strip()
        name = str(row.get("name") or row.get("vendor_name") or "").strip()
        if not code and not name:
            continue
        row_num = row.get("_row_num", "?")
        errors.extend(validate_required(row, [("name", "Name")]))
        if not code:
            errors.append(error_row(row_num, "Vendor Code", "Vendor Code is required.", "Enter a unique code."))
        errors.extend(validate_gst(str(row.get("gstin") or row.get("gst") or ""), "GSTIN", row_num))
        errors.extend(validate_pan(str(row.get("pan") or ""), "PAN", row_num))
        parsed.append(row)
    return parsed, errors


def _validate_employees_rows(db, rows: list[dict]) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    errors.extend(validate_duplicates(rows, "employee_code", "Employee Code"))
    errors.extend(validate_duplicates(rows, "code", "Employee Code"))
    parsed: list[dict] = []
    for row in rows:
        code = str(row.get("employee_code") or row.get("code") or "").strip()
        name = str(row.get("name") or row.get("employee_name") or "").strip()
        if not code and not name:
            continue
        row_num = row.get("_row_num", "?")
        errors.extend(validate_required(row, [("name", "Name")]))
        if not code:
            errors.append(error_row(row_num, "Employee Code", "Employee Code is required.", "Enter employee code."))
        errors.extend(validate_date_value(str(row.get("join_date") or ""), "Join Date", row_num))
        errors.extend(validate_pan(str(row.get("pan") or ""), "PAN", row_num))
        parsed.append(row)
    return parsed, errors


def _validate_materials_rows(db, rows: list[dict]) -> tuple[list[dict], list[dict]]:
    material_units = ["Nos", "Kg", "MT", "Bag", "Cum", "Sqm", "Ltr", "Rmt", "Set", "LS"]
    errors: list[dict] = []
    errors.extend(validate_duplicates(rows, "code", "Code"))
    parsed: list[dict] = []
    for row in rows:
        code = str(row.get("code") or "").strip()
        name = str(row.get("name") or "").strip()
        if not code and not name:
            continue
        row_num = row.get("_row_num", "?")
        errors.extend(validate_required(row, [("code", "Code"), ("name", "Name")]))
        errors.extend(validate_unit(str(row.get("unit") or "Nos"), "Unit", row_num, material_units))
        parsed.append(row)
    return parsed, errors


def _validate_coa_rows(db, rows: list[dict]) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    errors.extend(validate_duplicates(rows, "account_code", "Account Code"))
    errors.extend(validate_duplicates(rows, "code", "Account Code"))
    parsed: list[dict] = []
    for row in rows:
        code = str(row.get("account_code") or row.get("code") or "").strip()
        name = str(row.get("account_name") or row.get("name") or "").strip()
        if not code and not name:
            continue
        row_num = row.get("_row_num", "?")
        errors.extend(validate_required(row, [("account_name", "Account Name")]))
        if not code:
            errors.append(error_row(row_num, "Account Code", "Account Code is required.", "Enter ledger code."))
        parsed.append(row)
    return parsed, errors


def _validate_opening_balance_rows(db, rows: list[dict]) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    parsed: list[dict] = []
    for row in rows:
        acct = str(row.get("account_code") or row.get("account") or "").strip()
        if not acct:
            continue
        row_num = row.get("_row_num", "?")
        errors.extend(validate_required(row, [("account_code", "Account Code")]))
        errors.extend(validate_account(acct, "Account Code", row_num))
        errors.extend(validate_date_value(str(row.get("as_on_date") or ""), "As On Date", row_num))
        parsed.append(row)
    return parsed, errors


MODULE_TEMPLATES: dict[str, Callable[[], Any]] = {
    "boq": boq_import_template,
    "vendors": vendor_import_template,
    "employees": lambda: __import__("employee_master_service").employee_import_template(),
    "materials": lambda: build_xlsx_template(
        ["Code", "Name", "Category", "Unit", "HSN Code", "GST %", "Reorder Level"],
        ["MAT001", "Cement OPC 53", "Civil", "Bag", "2523", "18", "100"],
    ),
    "coa": lambda: build_xlsx_template(
        ["Account Code", "Account Name", "Account Type", "Parent Code", "GST Applicable"],
        ["11001", "Cash in Hand", "Asset", "", "No"],
    ),
    "opening_balances": lambda: build_xlsx_template(
        ["Account Code", "Debit", "Credit", "As On Date"],
        ["11001", "50000", "0", "2026-04-01"],
    ),
    "bank_accounts": lambda: build_xlsx_template(
        ["Bank Name", "Account Number", "IFSC", "Branch", "Opening Balance", "As On Date"],
        ["Sample Bank", "1234567890", "SBIN0001234", "Main Branch", "100000", "2026-04-01"],
    ),
    "companies": lambda: __import__("company_master_service").company_import_template(),
    "branches": lambda: __import__("branch_master_service").branch_import_template(),
    "departments": lambda: __import__("department_master_service").department_import_template(),
    "designations": lambda: __import__("designation_master_service").designation_import_template(),
    "clients": lambda: __import__("client_master_service").client_import_template(),
    "projects": lambda: __import__("project_master_service").project_import_template(),
    "subcontractors": lambda: __import__("subcontractor_master_service").subcontractor_import_template(),
    "workers": lambda: __import__("worker_master_service").worker_import_template(),
    "roles": lambda: __import__("roles_permissions_service").roles_import_template(),
    "users": lambda: __import__("user_management_service").user_import_template(),
    "documents": lambda: __import__("document_import_service").document_import_template(),
}
if customer_import_template is not None:
    MODULE_TEMPLATES["customers"] = customer_import_template

MODULE_VALIDATORS: dict[str, Callable] = {
    "vendors": validate_vendor_import_rows,
    "employees": _validate_employees_rows,
    "materials": _validate_materials_rows,
    "coa": _validate_coa_rows,
    "opening_balances": _validate_opening_balance_rows,
    "bank_accounts": _validate_opening_balance_rows,
}
if validate_customer_import_rows is not None:
    MODULE_VALIDATORS["customers"] = validate_customer_import_rows
if validate_company_import_rows is not None:
    MODULE_VALIDATORS["companies"] = validate_company_import_rows
if validate_branch_import_rows is not None:
    MODULE_VALIDATORS["branches"] = validate_branch_import_rows
if validate_department_import_rows is not None:
    MODULE_VALIDATORS["departments"] = validate_department_import_rows
if validate_designation_import_rows is not None:
    MODULE_VALIDATORS["designations"] = validate_designation_import_rows
if validate_client_import_rows is not None:
    MODULE_VALIDATORS["clients"] = validate_client_import_rows
if validate_employee_import_rows is not None:
    MODULE_VALIDATORS["employees"] = validate_employee_import_rows
if validate_project_import_rows is not None:
    MODULE_VALIDATORS["projects"] = validate_project_import_rows
if validate_subcontractor_import_rows is not None:
    MODULE_VALIDATORS["subcontractors"] = validate_subcontractor_import_rows
if validate_worker_import_rows is not None:
    MODULE_VALIDATORS["workers"] = validate_worker_import_rows
if validate_roles_import_rows is not None:
    MODULE_VALIDATORS["roles"] = validate_roles_import_rows
if validate_user_import_rows is not None:
    MODULE_VALIDATORS["users"] = validate_user_import_rows
if validate_document_import_rows is not None:
    MODULE_VALIDATORS["documents"] = validate_document_import_rows

PHASE2_SAVE_MODULES = frozenset(
    {"coa", "opening_balances", "bank_accounts", "sales", "purchase", "payments", "bank_statement"}
)


def register_bulk_import_routes(
    app,
    *,
    login_required,
    get_db,
    boq_units: list[str],
    generate_boq_number,
    generate_client_code,
    create_approval_request,
    record_pending_checker: str,
):
    @app.route("/api/bulk-import/<module_key>/template")
    @login_required
    def bulk_import_template(module_key: str):
        key = module_key.lower().strip()
        factory = MODULE_TEMPLATES.get(key)
        if not factory:
            return jsonify({"error": f"Unknown import module: {module_key}"}), 404
        buf = factory()
        filename = f"maxek_import_{key}_template.xlsx"
        return send_file(buf, as_attachment=True, download_name=filename, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @app.route("/api/bulk-import/<module_key>/validate", methods=["POST"])
    @login_required
    def bulk_import_validate(module_key: str):
        key = module_key.lower().strip()
        db = get_db()
        upload = request.files.get("file")
        rows, parse_err = parse_upload(upload)
        if parse_err:
            return jsonify({"ok": False, "errors": [error_row("—", "File", parse_err, "Upload a valid spreadsheet.")]}), 400

        if key == "boq":
            project_id = request.form.get("project_id", type=int)
            result = validate_boq_import(db, rows, boq_units=boq_units, project_id=project_id)
            return jsonify(result)

        validator = MODULE_VALIDATORS.get(key)
        if not validator:
            return jsonify({"error": f"Validate not available for: {module_key}"}), 404

        parsed, errors = validator(db, rows)
        result = validation_result(parsed, errors)
        result["parsed_rows"] = parsed
        return jsonify(result)

    @app.route("/api/bulk-import/<module_key>/save", methods=["POST"])
    @login_required
    def bulk_import_save(module_key: str):
        key = module_key.lower().strip()
        db = get_db()
        username = _username(session)

        if key == "boq":
            project_id = request.form.get("project_id", type=int)
            if not project_id:
                return jsonify({"ok": False, "error": "project_id is required for BOQ import."}), 400
            payload = request.form.get("parsed_rows") or request.get_json(silent=True)
            if isinstance(payload, dict):
                parsed_rows = payload.get("parsed_rows") or payload.get("rows") or []
            elif isinstance(payload, str):
                try:
                    parsed_rows = json.loads(payload)
                except json.JSONDecodeError:
                    parsed_rows = []
            else:
                parsed_rows = payload or []

            if not parsed_rows:
                upload = request.files.get("file")
                rows, parse_err = parse_upload(upload)
                if parse_err:
                    return jsonify({"ok": False, "error": parse_err}), 400
                val = validate_boq_import(db, rows, boq_units=boq_units, project_id=project_id)
                if not val.get("ok"):
                    return jsonify(val), 400
                parsed_rows = val.get("parsed_rows") or []

            val = validate_boq_import(db, parsed_rows, boq_units=boq_units, project_id=project_id)
            if not val.get("ok"):
                return jsonify(val), 400

            filename = (request.files.get("file") or type("F", (), {"filename": ""})()).filename or "import.json"
            try:
                result = save_boq_import(
                    db,
                    val["parsed_rows"],
                    project_id=project_id,
                    username=username,
                    filename=filename,
                    generate_boq_number_fn=generate_boq_number,
                    insert_boq_lines_fn=None,
                    create_approval_request_fn=lambda d, m, rid, tbl, u, uid: create_approval_request(
                        d, m, rid, tbl, u, session.get("user_id")
                    ),
                    record_pending_checker=record_pending_checker,
                )
                db.commit()
                return jsonify(result)
            except ValueError as exc:
                db.rollback()
                return jsonify({"ok": False, "error": str(exc)}), 400

        if key == "customers" and save_customer_import is not None:
            upload = request.files.get("file")
            rows, parse_err = parse_upload(upload) if upload else ([], "No file uploaded.")
            if parse_err:
                return jsonify({"ok": False, "error": parse_err}), 400
            val = validate_customer_import(db, rows)
            if not val.get("ok"):
                return jsonify(val), 400
            try:
                result = save_customer_import(
                    db,
                    val["parsed_rows"],
                    username=username,
                    filename=(upload.filename if upload else "") or "import.json",
                    generate_client_code_fn=generate_client_code,
                )
                db.commit()
                return jsonify(result)
            except ValueError as exc:
                db.rollback()
                return jsonify({"ok": False, "error": str(exc)}), 400

        if key == "vendors":
            upload = request.files.get("file")
            rows, parse_err = parse_upload(upload) if upload else ([], "No file uploaded.")
            if parse_err:
                return jsonify({"ok": False, "error": parse_err}), 400
            val = validate_vendor_import(db, rows)
            if not val.get("ok"):
                return jsonify(val), 400
            try:
                result = save_vendor_import(
                    db,
                    val["parsed_rows"],
                    username=username,
                    filename=(upload.filename if upload else "") or "import.json",
                    customer_id=session.get("customer_id"),
                )
                log_import(
                    db,
                    module_key="vendors",
                    imported_by=username,
                    filename=(upload.filename if upload else "") or "import.json",
                    total_rows=len(val["parsed_rows"]),
                    success_rows=result.get("imported", 0),
                    failed_rows=0,
                )
                db.commit()
                return jsonify(result)
            except ValueError as exc:
                db.rollback()
                return jsonify({"ok": False, "error": str(exc)}), 400

        if key == "companies" and save_company_import is not None:
            upload = request.files.get("file")
            rows, parse_err = parse_upload(upload) if upload else ([], "No file uploaded.")
            if parse_err:
                return jsonify({"ok": False, "error": parse_err}), 400
            from company_import_service import validate_company_import

            val = validate_company_import(db, rows)
            if not val.get("ok"):
                return jsonify(val), 400
            try:
                result = save_company_import(
                    db,
                    val["parsed_rows"],
                    username=username,
                    filename=(upload.filename if upload else "") or "import.json",
                )
                log_import(
                    db,
                    module_key="companies",
                    imported_by=username,
                    filename=(upload.filename if upload else "") or "import.json",
                    total_rows=len(val["parsed_rows"]),
                    success_rows=result.get("imported", 0),
                    failed_rows=0,
                )
                db.commit()
                return jsonify(result)
            except ValueError as exc:
                db.rollback()
                return jsonify({"ok": False, "error": str(exc)}), 400

        if key == "branches" and save_branch_import is not None:
            upload = request.files.get("file")
            rows, parse_err = parse_upload(upload) if upload else ([], "No file uploaded.")
            if parse_err:
                return jsonify({"ok": False, "error": parse_err}), 400
            from branch_import_service import validate_branch_import

            val = validate_branch_import(db, rows)
            if not val.get("ok"):
                return jsonify(val), 400
            try:
                result = save_branch_import(
                    db,
                    val["parsed_rows"],
                    username=username,
                    filename=(upload.filename if upload else "") or "import.json",
                    customer_id=session.get("customer_id"),
                )
                log_import(
                    db,
                    module_key="branches",
                    imported_by=username,
                    filename=(upload.filename if upload else "") or "import.json",
                    total_rows=len(val["parsed_rows"]),
                    success_rows=result.get("imported", 0),
                    failed_rows=0,
                )
                db.commit()
                return jsonify(result)
            except ValueError as exc:
                db.rollback()
                return jsonify({"ok": False, "error": str(exc)}), 400

        if key == "departments" and save_department_import is not None:
            upload = request.files.get("file")
            rows, parse_err = parse_upload(upload) if upload else ([], "No file uploaded.")
            if parse_err:
                return jsonify({"ok": False, "error": parse_err}), 400
            from department_import_service import validate_department_import

            val = validate_department_import(db, rows)
            if not val.get("ok"):
                return jsonify(val), 400
            try:
                result = save_department_import(
                    db,
                    val["parsed_rows"],
                    username=username,
                    filename=(upload.filename if upload else "") or "import.json",
                    customer_id=session.get("customer_id"),
                )
                log_import(
                    db,
                    module_key="departments",
                    imported_by=username,
                    filename=(upload.filename if upload else "") or "import.json",
                    total_rows=len(val["parsed_rows"]),
                    success_rows=result.get("imported", 0),
                    failed_rows=0,
                )
                db.commit()
                return jsonify(result)
            except ValueError as exc:
                db.rollback()
                return jsonify({"ok": False, "error": str(exc)}), 400

        if key == "designations" and save_designation_import is not None:
            upload = request.files.get("file")
            rows, parse_err = parse_upload(upload) if upload else ([], "No file uploaded.")
            if parse_err:
                return jsonify({"ok": False, "error": parse_err}), 400
            from designation_import_service import validate_designation_import

            val = validate_designation_import(db, rows)
            if not val.get("ok"):
                return jsonify(val), 400
            try:
                result = save_designation_import(
                    db,
                    val["parsed_rows"],
                    username=username,
                    filename=(upload.filename if upload else "") or "import.json",
                    customer_id=session.get("customer_id"),
                )
                log_import(
                    db,
                    module_key="designations",
                    imported_by=username,
                    filename=(upload.filename if upload else "") or "import.json",
                    total_rows=len(val["parsed_rows"]),
                    success_rows=result.get("imported", 0),
                    failed_rows=0,
                )
                db.commit()
                return jsonify(result)
            except ValueError as exc:
                db.rollback()
                return jsonify({"ok": False, "error": str(exc)}), 400

        if key == "clients" and save_client_import is not None:
            upload = request.files.get("file")
            rows, parse_err = parse_upload(upload) if upload else ([], "No file uploaded.")
            if parse_err:
                return jsonify({"ok": False, "error": parse_err}), 400
            from client_import_service import validate_client_import

            val = validate_client_import(db, rows)
            if not val.get("ok"):
                return jsonify(val), 400
            try:
                result = save_client_import(
                    db,
                    val["parsed_rows"],
                    username=username,
                    filename=(upload.filename if upload else "") or "import.json",
                    customer_id=session.get("customer_id"),
                )
                log_import(
                    db,
                    module_key="clients",
                    imported_by=username,
                    filename=(upload.filename if upload else "") or "import.json",
                    total_rows=len(val["parsed_rows"]),
                    success_rows=result.get("imported", 0),
                    failed_rows=0,
                )
                db.commit()
                return jsonify(result)
            except ValueError as exc:
                db.rollback()
                return jsonify({"ok": False, "error": str(exc)}), 400

        if key == "projects" and save_project_import is not None:
            upload = request.files.get("file")
            rows, parse_err = parse_upload(upload) if upload else ([], "No file uploaded.")
            if parse_err:
                return jsonify({"ok": False, "error": parse_err}), 400
            from project_import_service import validate_project_import

            val = validate_project_import(db, rows)
            if not val.get("ok"):
                return jsonify(val), 400
            try:
                result = save_project_import(
                    db,
                    val["parsed_rows"],
                    username=username,
                    filename=(upload.filename if upload else "") or "import.json",
                    customer_id=session.get("customer_id"),
                )
                log_import(
                    db,
                    module_key="projects",
                    imported_by=username,
                    filename=(upload.filename if upload else "") or "import.json",
                    total_rows=len(val["parsed_rows"]),
                    success_rows=result.get("imported", 0),
                    failed_rows=0,
                )
                db.commit()
                return jsonify(result)
            except ValueError as exc:
                db.rollback()
                return jsonify({"ok": False, "error": str(exc)}), 400

        if key == "subcontractors" and save_subcontractor_import is not None:
            upload = request.files.get("file")
            rows, parse_err = parse_upload(upload) if upload else ([], "No file uploaded.")
            if parse_err:
                return jsonify({"ok": False, "error": parse_err}), 400
            val = validate_subcontractor_import(db, rows)
            if not val.get("ok"):
                return jsonify(val), 400
            try:
                result = save_subcontractor_import(
                    db,
                    val["parsed_rows"],
                    username=username,
                    filename=(upload.filename if upload else "") or "import.json",
                    customer_id=session.get("customer_id"),
                )
                log_import(
                    db,
                    module_key="subcontractors",
                    imported_by=username,
                    filename=(upload.filename if upload else "") or "import.json",
                    total_rows=len(val["parsed_rows"]),
                    success_rows=result.get("imported", 0),
                    failed_rows=0,
                )
                db.commit()
                return jsonify(result)
            except ValueError as exc:
                db.rollback()
                return jsonify({"ok": False, "error": str(exc)}), 400

        if key == "workers" and save_worker_import is not None:
            upload = request.files.get("file")
            rows, parse_err = parse_upload(upload) if upload else ([], "No file uploaded.")
            if parse_err:
                return jsonify({"ok": False, "error": parse_err}), 400
            val = validate_worker_import(db, rows)
            if not val.get("ok"):
                return jsonify(val), 400
            try:
                result = save_worker_import(
                    db,
                    val["parsed_rows"],
                    username=username,
                    filename=(upload.filename if upload else "") or "import.json",
                    customer_id=session.get("customer_id"),
                )
                log_import(
                    db,
                    module_key="workers",
                    imported_by=username,
                    filename=(upload.filename if upload else "") or "import.json",
                    total_rows=len(val["parsed_rows"]),
                    success_rows=result.get("imported", 0),
                    failed_rows=0,
                )
                db.commit()
                return jsonify(result)
            except ValueError as exc:
                db.rollback()
                return jsonify({"ok": False, "error": str(exc)}), 400

        if key == "documents" and save_document_import is not None:
            upload = request.files.get("file")
            rows, parse_err = parse_upload(upload) if upload else ([], "No file uploaded.")
            if parse_err:
                return jsonify({"ok": False, "error": parse_err}), 400
            from document_import_service import validate_document_import

            val = validate_document_import(db, rows)
            if not val.get("ok"):
                return jsonify(val), 400
            try:
                result = save_document_import(
                    db,
                    val["parsed_rows"],
                    username=username,
                    filename=(upload.filename if upload else "") or "import.json",
                )
                log_import(
                    db,
                    module_key="documents",
                    imported_by=username,
                    filename=(upload.filename if upload else "") or "import.json",
                    total_rows=len(val["parsed_rows"]),
                    success_rows=result.get("imported", 0),
                    failed_rows=result.get("skipped", 0),
                )
                db.commit()
                return jsonify(result)
            except ValueError as exc:
                db.rollback()
                return jsonify({"ok": False, "error": str(exc)}), 400

        if key == "roles" and save_roles_import is not None:
            upload = request.files.get("file")
            rows, parse_err = parse_upload(upload) if upload else ([], "No file uploaded.")
            if parse_err:
                return jsonify({"ok": False, "error": parse_err}), 400
            from roles_permissions_import_service import validate_roles_import

            val = validate_roles_import(db, rows)
            if not val.get("ok"):
                return jsonify(val), 400
            try:
                result = save_roles_import(
                    db,
                    val["parsed_rows"],
                    username=username,
                    filename=(upload.filename if upload else "") or "import.json",
                    customer_id=session.get("customer_id"),
                )
                log_import(
                    db,
                    module_key="roles",
                    imported_by=username,
                    filename=(upload.filename if upload else "") or "import.json",
                    total_rows=len(val["parsed_rows"]),
                    success_rows=result.get("imported", 0),
                    failed_rows=0,
                )
                db.commit()
                return jsonify(result)
            except ValueError as exc:
                db.rollback()
                return jsonify({"ok": False, "error": str(exc)}), 400

        if key == "users" and save_user_import is not None:
            upload = request.files.get("file")
            rows, parse_err = parse_upload(upload) if upload else ([], "No file uploaded.")
            if parse_err:
                return jsonify({"ok": False, "error": parse_err}), 400
            from user_import_service import validate_user_import

            val = validate_user_import(db, rows)
            if not val.get("ok"):
                return jsonify(val), 400
            try:
                from super_admin_service import assert_user_limit_not_exceeded

                result = save_user_import(
                    db,
                    val["parsed_rows"],
                    username=username,
                    filename=(upload.filename if upload else "") or "import.json",
                    customer_id=session.get("customer_id"),
                    assert_user_limit_fn=assert_user_limit_not_exceeded if session.get("customer_id") else None,
                )
                log_import(
                    db,
                    module_key="users",
                    imported_by=username,
                    filename=(upload.filename if upload else "") or "import.json",
                    total_rows=len(val["parsed_rows"]),
                    success_rows=result.get("imported", 0),
                    failed_rows=0,
                )
                db.commit()
                return jsonify(result)
            except ValueError as exc:
                db.rollback()
                return jsonify({"ok": False, "error": str(exc)}), 400

        if key == "employees" and save_employee_import is not None:
            upload = request.files.get("file")
            rows, parse_err = parse_upload(upload) if upload else ([], "No file uploaded.")
            if parse_err:
                return jsonify({"ok": False, "error": parse_err}), 400
            from employee_import_service import validate_employee_import

            val = validate_employee_import(db, rows)
            if not val.get("ok"):
                return jsonify(val), 400
            try:
                result = save_employee_import(
                    db,
                    val["parsed_rows"],
                    username=username,
                    filename=(upload.filename if upload else "") or "import.json",
                    customer_id=session.get("customer_id"),
                )
                log_import(
                    db,
                    module_key="employees",
                    imported_by=username,
                    filename=(upload.filename if upload else "") or "import.json",
                    total_rows=len(val["parsed_rows"]),
                    success_rows=result.get("imported", 0),
                    failed_rows=0,
                )
                db.commit()
                return jsonify(result)
            except ValueError as exc:
                db.rollback()
                return jsonify({"ok": False, "error": str(exc)}), 400

        if key == "materials":
            from store_service import import_materials_excel

            upload = request.files.get("file")
            if not upload:
                return jsonify({"ok": False, "error": "No file uploaded."}), 400
            rows, parse_err = parse_upload(upload)
            if parse_err:
                return jsonify({"ok": False, "error": parse_err}), 400
            parsed, errors = _validate_materials_rows(db, rows)
            val = validation_result(parsed, errors)
            if not val.get("ok"):
                return jsonify(val), 400
            count, import_errors = import_materials_excel(db, upload, username)
            log_import(
                db,
                module_key="materials",
                imported_by=username,
                filename=upload.filename or "",
                total_rows=len(parsed),
                success_rows=count,
                failed_rows=len(import_errors),
                notes="; ".join(import_errors[:5]),
            )
            db.commit()
            return jsonify({"ok": True, "imported": count, "errors": import_errors})

        if key in PHASE2_SAVE_MODULES:
            upload = request.files.get("file")
            rows, parse_err = parse_upload(upload) if upload else ([], None)
            validator = MODULE_VALIDATORS.get(key)
            if validator and rows:
                parsed, errors = validator(db, rows)
                val = validation_result(parsed, errors)
                if not val.get("ok"):
                    return jsonify(val), 400
            return jsonify(
                {
                    "ok": False,
                    "phase": 2,
                    "message": f"{key.replace('_', ' ').title()} import save is planned for Phase 2. "
                    "Validation and template download are available.",
                }
            ), 501

        return jsonify({"error": f"Unknown import module: {module_key}"}), 404

    @app.route("/boq-library", methods=["GET", "POST"])
    @login_required
    def boq_library():
        from flask import flash, redirect, render_template, url_for

        from standard_boq_library_service import (
            delete_standard_boq_item,
            ensure_standard_boq_library_schema,
            get_standard_boq_item,
            library_categories,
            list_standard_boq_library,
            save_standard_boq_item,
        )

        db = get_db()
        ensure_standard_boq_library_schema(db)
        username = _username(session)

        if request.method == "POST":
            action = (request.form.get("form_action") or "").strip()
            item_id = request.form.get("item_id", type=int)
            if action == "delete" and item_id:
                delete_standard_boq_item(db, item_id)
                db.commit()
                flash("Library item deleted.")
                return redirect(url_for("boq_library"))
            try:
                save_standard_boq_item(db, request.form, item_id=item_id, username=username)
                db.commit()
                flash("Standard BOQ library item saved.")
            except ValueError as exc:
                db.rollback()
                flash(str(exc))
            return redirect(url_for("boq_library"))

        search = request.args.get("q", "")
        edit_id = request.args.get("edit", type=int)
        edit_item = get_standard_boq_item(db, edit_id) if edit_id else None
        rows = list_standard_boq_library(db, search=search)
        return render_template(
            "boq_library.html",
            rows=rows,
            edit_item=edit_item,
            search=search,
            categories=library_categories(db),
            boq_units=boq_units,
        )

    @app.route("/api/boq-library/<int:item_id>")
    @login_required
    def api_boq_library_item(item_id: int):
        from standard_boq_library_service import get_standard_boq_item

        db = get_db()
        item = get_standard_boq_item(db, item_id)
        if not item:
            return jsonify({"error": "Not found"}), 404
        return jsonify(item)

    @app.route("/api/boq-templates/<int:template_id>/lines")
    @login_required
    def api_boq_template_lines(template_id: int):
        from library_service import get_boq_template_lines

        db = get_db()
        lines = get_boq_template_lines(db, template_id)
        return jsonify({"lines": lines})
