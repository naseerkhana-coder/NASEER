"""Company Master API routes — export, import, audit."""

from __future__ import annotations

import json
from typing import Any, Callable

from flask import Response, jsonify, request, send_file, session

from company_import_service import save_company_import, validate_company_import
from company_master_service import (
    company_import_template,
    export_companies_csv,
    export_companies_excel,
    export_companies_pdf,
    list_company_audit_trail,
    user_can_company_master,
)
from bulk_import_service import parse_upload
from import_audit_service import log_import


def register_company_master_routes(
    app,
    *,
    login_required: Callable,
    admin_required: Callable,
    get_db: Callable,
    is_admin_user: Callable,
) -> None:
    def _user_id() -> int | None:
        return session.get("user_id")

    def _username() -> str:
        return str(session.get("username") or "")

    def _require(action: str):
        db = get_db()
        if not user_can_company_master(db, _user_id(), action, is_admin=is_admin_user()):
            return jsonify({"error": f"Permission denied: {action}"}), 403
        return None

    @app.route("/api/company-master/export")
    @login_required
    def company_master_export():
        denied = _require("export")
        if denied:
            return denied
        fmt = (request.args.get("format") or "xlsx").lower().strip()
        include_deleted = request.args.get("include_deleted") == "1"
        db = get_db()
        if fmt in ("xlsx", "excel"):
            buf = export_companies_excel(db, include_deleted=include_deleted)
            return send_file(
                buf,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name="companies.xlsx",
            )
        if fmt == "csv":
            csv_text = export_companies_csv(db, include_deleted=include_deleted)
            return Response(
                csv_text,
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment; filename=companies.csv"},
            )
        if fmt == "pdf":
            buf = export_companies_pdf(db, include_deleted=include_deleted)
            return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name="companies.pdf")
        return jsonify({"error": "Unsupported format. Use xlsx, csv, or pdf."}), 400

    @app.route("/api/company-master/import/template")
    @login_required
    def company_master_import_template():
        denied = _require("import")
        if denied:
            return denied
        buf = company_import_template()
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="company_master_template.xlsx",
        )

    @app.route("/api/company-master/import/validate", methods=["POST"])
    @login_required
    def company_master_import_validate():
        denied = _require("import")
        if denied:
            return denied
        db = get_db()
        upload = request.files.get("file")
        rows, parse_err = parse_upload(upload)
        if parse_err:
            return jsonify({"ok": False, "errors": [{"row": "—", "column": "File", "error": parse_err}]}), 400
        result = validate_company_import(db, rows)
        return jsonify(result)

    @app.route("/api/company-master/import/save", methods=["POST"])
    @login_required
    def company_master_import_save():
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
        val = validate_company_import(db, rows)
        if not val.get("ok"):
            return jsonify(val), 400
        try:
            result = save_company_import(
                db,
                val["parsed_rows"],
                username=_username(),
                filename=(upload.filename if upload else "") or "import.json",
            )
            log_import(
                db,
                module_key="companies",
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

    @app.route("/api/company-master/<int:company_id>/audit")
    @login_required
    def company_master_audit(company_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        rows = list_company_audit_trail(db, company_id)
        return jsonify({"items": rows, "company_id": company_id})
