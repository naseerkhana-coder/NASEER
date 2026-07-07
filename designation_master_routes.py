"""Designation Master API routes — export, import, audit, reports, AI, mobile."""

from __future__ import annotations

from typing import Callable

from flask import Response, jsonify, request, send_file, session

from bulk_import_service import parse_upload
from designation_import_service import save_designation_import, validate_designation_import
from designation_master_service import (
    ai_validate_designation,
    designation_import_template,
    designation_report,
    export_designations_csv,
    export_designations_excel,
    export_designations_pdf,
    get_designation_master,
    list_designation_audit_trail,
    list_designations_master,
    user_can_designation_master,
)
from import_audit_service import log_import


def register_designation_master_routes(
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
        if not user_can_designation_master(db, _user_id(), action, is_admin=is_admin_user()):
            return jsonify({"error": f"Permission denied: {action}"}), 403
        return None

    @app.route("/api/designation-master/export")
    @login_required
    def designation_master_export():
        denied = _require("export")
        if denied:
            return denied
        fmt = (request.args.get("format") or "xlsx").lower().strip()
        db = get_db()
        filters = {
            "include_deleted": request.args.get("include_deleted") == "1",
            "company_id": request.args.get("company_id", type=int),
            "department_id": request.args.get("department_id", type=int),
            "status": request.args.get("status") or "",
        }
        clean_filters = {k: v for k, v in filters.items() if v not in (None, "", False) or k == "include_deleted"}
        report = request.args.get("report", "")
        if report:
            title = report.replace("_", " ").title()
            buf = export_designations_pdf(db, report_title=title, **clean_filters)
            return send_file(
                buf, mimetype="application/pdf", as_attachment=True, download_name=f"designations_{report}.pdf"
            )
        if fmt in ("xlsx", "excel"):
            buf = export_designations_excel(db, **clean_filters)
            return send_file(
                buf,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name="designations.xlsx",
            )
        if fmt == "csv":
            csv_text = export_designations_csv(db, **clean_filters)
            return Response(
                csv_text,
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment; filename=designations.csv"},
            )
        if fmt == "pdf":
            buf = export_designations_pdf(db, **clean_filters)
            return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name="designations.pdf")
        return jsonify({"error": "Unsupported format. Use xlsx, csv, or pdf."}), 400

    @app.route("/api/designation-master/import/template")
    @login_required
    def designation_master_import_template():
        denied = _require("import")
        if denied:
            return denied
        buf = designation_import_template()
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="designation_master_template.xlsx",
        )

    @app.route("/api/designation-master/import/validate", methods=["POST"])
    @login_required
    def designation_master_import_validate():
        denied = _require("import")
        if denied:
            return denied
        db = get_db()
        upload = request.files.get("file")
        rows, parse_err = parse_upload(upload)
        if parse_err:
            return jsonify({"ok": False, "errors": [{"row": "—", "column": "File", "error": parse_err}]}), 400
        return jsonify(validate_designation_import(db, rows))

    @app.route("/api/designation-master/import/save", methods=["POST"])
    @login_required
    def designation_master_import_save():
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
        val = validate_designation_import(db, rows)
        if not val.get("ok"):
            return jsonify(val), 400
        try:
            result = save_designation_import(
                db,
                val["parsed_rows"],
                username=_username(),
                filename=(upload.filename if upload else "") or "import.json",
                customer_id=session.get("customer_id"),
            )
            log_import(
                db,
                module_key="designations",
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

    @app.route("/api/designation-master/<int:designation_id>/audit")
    @login_required
    def designation_master_audit(designation_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify({"items": list_designation_audit_trail(db, designation_id), "designation_id": designation_id})

    @app.route("/api/designation-master/reports/<report_key>")
    @login_required
    def designation_master_report_route(report_key: str):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        rows = designation_report(
            db,
            report_key,
            company_id=request.args.get("company_id", type=int),
            department_id=request.args.get("department_id", type=int),
        )
        return jsonify({"report": report_key, "count": len(rows), "items": rows})

    @app.route("/api/designation-master/ai/validate", methods=["POST"])
    @login_required
    def designation_master_ai_validate():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or {}
        designation_id = payload.get("designation_id") or request.form.get("designation_id", type=int)
        form = payload.get("form") or request.form.to_dict(flat=True)
        return jsonify(ai_validate_designation(db, designation_id=designation_id, form=form or None))

    @app.route("/api/mobile/designations", methods=["GET"])
    @login_required
    def api_mobile_list_designations():
        db = get_db()
        if not user_can_designation_master(db, _user_id(), "view", is_admin=is_admin_user()):
            return jsonify({"error": "Permission denied"}), 403
        company_id = request.args.get("company_id", type=int) or session.get("company_id")
        listing = list_designations_master(
            db,
            company_id=company_id,
            status="Active",
            per_page=500,
        )
        items = [
            {
                "id": d["id"],
                "designation_code": d.get("designation_code"),
                "designation_name": d.get("designation_name"),
                "designation_short_name": d.get("designation_short_name"),
                "workflow_role_default": d.get("workflow_role_default"),
                "company_code": d.get("company_code"),
                "department_name": d.get("department_name"),
            }
            for d in listing["items"]
        ]
        return jsonify({"items": items, "count": len(items)})

    @app.route("/api/mobile/designations/<int:designation_id>", methods=["GET"])
    @login_required
    def api_mobile_get_designation(designation_id: int):
        db = get_db()
        if not user_can_designation_master(db, _user_id(), "view", is_admin=is_admin_user()):
            return jsonify({"error": "Permission denied"}), 403
        row = get_designation_master(db, designation_id)
        if not row:
            return jsonify({"error": "Designation not found"}), 404
        return jsonify(
            {
                "id": row["id"],
                "designation_code": row.get("designation_code"),
                "designation_name": row.get("designation_name"),
                "designation_short_name": row.get("designation_short_name"),
                "grade_level": row.get("grade_level"),
                "workflow_role_default": row.get("workflow_role_default"),
                "description": row.get("description"),
                "company_code": row.get("company_code"),
                "company_name": row.get("company_name"),
                "department_code": row.get("department_code"),
                "department_name": row.get("department_name"),
                "status": row.get("status"),
            }
        )
