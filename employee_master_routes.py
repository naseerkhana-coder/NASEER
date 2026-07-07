"""Employee Master API routes — export, import, audit, reports, AI, mobile."""

from __future__ import annotations

from typing import Callable

from flask import Response, jsonify, request, send_file, session

from bulk_import_service import parse_upload
from employee_import_service import save_employee_import, validate_employee_import
from employee_master_service import (
    ai_validate_employee,
    employee_import_template,
    employee_report,
    export_employees_csv,
    export_employees_excel,
    export_employees_pdf,
    get_employee_master,
    list_employee_audit_trail,
    list_employees_master,
    user_can_employee_master,
)
from import_audit_service import log_import


def register_employee_master_routes(
    app,
    *,
    login_required: Callable,
    get_db: Callable,
    is_admin_user: Callable,
) -> None:
    def _user_id() -> int | None:
        return session.get("user_id")

    def _username() -> str:
        return str(session.get("username") or "")

    def _require(action: str):
        db = get_db()
        if not user_can_employee_master(db, _user_id(), action, is_admin=is_admin_user()):
            return jsonify({"error": f"Permission denied: {action}"}), 403
        return None

    @app.route("/api/employee-master/export")
    @login_required
    def employee_master_export():
        denied = _require("export")
        if denied:
            return denied
        fmt = (request.args.get("format") or "xlsx").lower().strip()
        db = get_db()
        filters = {
            "include_deleted": request.args.get("include_deleted") == "1",
            "company_id": request.args.get("company_id", type=int),
            "branch_id": request.args.get("branch_id", type=int),
            "department_id": request.args.get("department_id", type=int),
            "designation_id": request.args.get("designation_id", type=int),
            "status": request.args.get("status") or "",
            "employment_status": request.args.get("employment_status") or "",
            "employee_type": request.args.get("employee_type") or "",
            "search": request.args.get("q") or "",
        }
        clean_filters = {
            k: v for k, v in filters.items() if v not in (None, "", False) or k == "include_deleted"
        }
        report = request.args.get("report", "")
        if report:
            title = report.replace("_", " ").title()
            buf = export_employees_pdf(db, report_title=title, **clean_filters)
            return send_file(
                buf,
                mimetype="application/pdf",
                as_attachment=True,
                download_name=f"employees_{report}.pdf",
            )
        if fmt in ("xlsx", "excel"):
            buf = export_employees_excel(db, **clean_filters)
            return send_file(
                buf,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name="employees.xlsx",
            )
        if fmt == "csv":
            csv_text = export_employees_csv(db, **clean_filters)
            return Response(
                csv_text,
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment; filename=employees.csv"},
            )
        if fmt == "pdf":
            buf = export_employees_pdf(db, **clean_filters)
            return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name="employees.pdf")
        return jsonify({"error": "Unsupported format. Use xlsx, csv, or pdf."}), 400

    @app.route("/api/employee-master/import/template")
    @login_required
    def employee_master_import_template_route():
        denied = _require("import")
        if denied:
            return denied
        buf = employee_import_template()
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="employee_master_template.xlsx",
        )

    @app.route("/api/employee-master/import/validate", methods=["POST"])
    @login_required
    def employee_master_import_validate():
        denied = _require("import")
        if denied:
            return denied
        db = get_db()
        upload = request.files.get("file")
        rows, parse_err = parse_upload(upload)
        if parse_err:
            return jsonify({"ok": False, "errors": [{"row": "—", "column": "File", "error": parse_err}]}), 400
        return jsonify(validate_employee_import(db, rows))

    @app.route("/api/employee-master/import/save", methods=["POST"])
    @login_required
    def employee_master_import_save():
        denied = _require("import")
        if denied:
            return denied
        db = get_db()
        upload = request.files.get("file")
        rows, parse_err = parse_upload(upload) if upload else ([], None)
        if not rows:
            payload = request.get_json(silent=True) or {}
            rows = payload.get("parsed_rows") or payload.get("rows") or []
        if parse_err and not rows:
            return jsonify({"ok": False, "error": parse_err}), 400
        val = validate_employee_import(db, rows)
        if not val.get("ok"):
            return jsonify(val), 400
        try:
            result = save_employee_import(
                db,
                val["parsed_rows"],
                username=_username(),
                filename=(upload.filename if upload else "") or "import.json",
                customer_id=session.get("customer_id"),
            )
            log_import(
                db,
                module_key="employees",
                imported_by=_username(),
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

    @app.route("/api/employee-master/<int:staff_id>/audit")
    @login_required
    def employee_master_audit(staff_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify({"items": list_employee_audit_trail(db, staff_id), "staff_id": staff_id})

    @app.route("/api/employee-master/reports/<report_key>")
    @login_required
    def employee_master_report_route(report_key: str):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        rows = employee_report(
            db,
            report_key,
            company_id=request.args.get("company_id", type=int),
            department_id=request.args.get("department_id", type=int),
            designation_id=request.args.get("designation_id", type=int),
            status=request.args.get("status") or "",
        )
        return jsonify({"report": report_key, "count": len(rows), "items": rows})

    @app.route("/api/employee-master/ai/validate", methods=["POST"])
    @login_required
    def employee_master_ai_validate():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or {}
        staff_id = payload.get("staff_id") or request.form.get("staff_id", type=int)
        form = payload.get("form") or request.form.to_dict(flat=True)
        return jsonify(ai_validate_employee(db, staff_id=staff_id, form=form or None))

    @app.route("/api/mobile/employees", methods=["GET"])
    @login_required
    def api_mobile_list_employees():
        db = get_db()
        if not user_can_employee_master(db, _user_id(), "view", is_admin=is_admin_user()):
            return jsonify({"error": "Permission denied"}), 403
        listing = list_employees_master(
            db,
            search=request.args.get("q") or "",
            company_id=request.args.get("company_id", type=int),
            department_id=request.args.get("department_id", type=int),
            status=request.args.get("status") or "Active",
            page=request.args.get("page", 1, type=int),
            per_page=min(request.args.get("per_page", 50, type=int), 100),
        )
        items = []
        for row in listing["items"]:
            items.append(
                {
                    "id": row.get("id"),
                    "employee_code": row.get("employee_code"),
                    "name": row.get("staff_name"),
                    "department": row.get("dept_master_name") or row.get("department"),
                    "designation": row.get("desig_master_name") or row.get("designation"),
                    "mobile": row.get("mobile"),
                    "email": row.get("official_email") or row.get("email"),
                    "status": row.get("status"),
                    "profile_photo": row.get("profile_photo") or row.get("photo"),
                }
            )
        return jsonify({"count": listing["total"], "items": items, "page": listing["page"]})

    @app.route("/api/mobile/employees/<int:staff_id>", methods=["GET"])
    @login_required
    def api_mobile_employee_profile(staff_id: int):
        db = get_db()
        if not user_can_employee_master(db, _user_id(), "view", is_admin=is_admin_user()):
            return jsonify({"error": "Permission denied"}), 403
        row = get_employee_master(db, staff_id)
        if not row:
            return jsonify({"error": "Employee not found"}), 404
        return jsonify(
            {
                "id": row.get("id"),
                "employee_code": row.get("employee_code"),
                "name": row.get("staff_name"),
                "first_name": row.get("first_name"),
                "last_name": row.get("last_name"),
                "department": row.get("dept_master_name") or row.get("department"),
                "designation": row.get("desig_master_name") or row.get("designation"),
                "company_code": row.get("company_code"),
                "branch_name": row.get("branch_name"),
                "mobile": row.get("mobile"),
                "email": row.get("official_email") or row.get("email"),
                "joining_date": row.get("joining_date"),
                "status": row.get("status"),
                "employment_status": row.get("employment_status"),
                "profile_photo": row.get("profile_photo") or row.get("photo"),
                "reporting_manager": row.get("reporting_manager_name"),
                "emergency_contacts": row.get("emergency_contacts") or [],
            }
        )
