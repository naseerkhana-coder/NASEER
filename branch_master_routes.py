"""Branch Master API routes — export, import, audit, reports, AI, Android."""

from __future__ import annotations

from typing import Callable

from flask import Response, jsonify, request, send_file, session

from branch_import_service import save_branch_import, validate_branch_import
from branch_master_service import (
    ai_validate_branch,
    branch_import_template,
    branch_report,
    export_branches_csv,
    export_branches_excel,
    export_branches_pdf,
    get_branch_master,
    list_branch_audit_trail,
    list_branches_master,
    user_can_branch_master,
)
from bulk_import_service import parse_upload
from import_audit_service import log_import


def register_branch_master_routes(
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
        if not user_can_branch_master(db, _user_id(), action, is_admin=is_admin_user()):
            return jsonify({"error": f"Permission denied: {action}"}), 403
        return None

    @app.route("/api/branch-master/export")
    @login_required
    def branch_master_export():
        denied = _require("export")
        if denied:
            return denied
        fmt = (request.args.get("format") or "xlsx").lower().strip()
        db = get_db()
        filters = {
            "include_deleted": request.args.get("include_deleted") == "1",
            "company_id": request.args.get("company_id", type=int),
            "status": request.args.get("status") or "",
            "country": request.args.get("country") or "",
        }
        clean_filters = {k: v for k, v in filters.items() if v not in (None, "", False) or k == "include_deleted"}
        report = request.args.get("report", "")
        if report:
            title = report.replace("_", " ").title()
            buf = export_branches_pdf(db, report_title=title, **clean_filters)
            return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name=f"branches_{report}.pdf")
        if fmt in ("xlsx", "excel"):
            buf = export_branches_excel(db, **clean_filters)
            return send_file(
                buf,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name="branches.xlsx",
            )
        if fmt == "csv":
            csv_text = export_branches_csv(db, **clean_filters)
            return Response(
                csv_text,
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment; filename=branches.csv"},
            )
        if fmt == "pdf":
            buf = export_branches_pdf(db, **clean_filters)
            return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name="branches.pdf")
        return jsonify({"error": "Unsupported format. Use xlsx, csv, or pdf."}), 400

    @app.route("/api/branch-master/import/template")
    @login_required
    def branch_master_import_template():
        denied = _require("import")
        if denied:
            return denied
        buf = branch_import_template()
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="branch_master_template.xlsx",
        )

    @app.route("/api/branch-master/import/validate", methods=["POST"])
    @login_required
    def branch_master_import_validate():
        denied = _require("import")
        if denied:
            return denied
        db = get_db()
        upload = request.files.get("file")
        rows, parse_err = parse_upload(upload)
        if parse_err:
            return jsonify({"ok": False, "errors": [{"row": "—", "column": "File", "error": parse_err}]}), 400
        return jsonify(validate_branch_import(db, rows))

    @app.route("/api/branch-master/import/save", methods=["POST"])
    @login_required
    def branch_master_import_save():
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
        val = validate_branch_import(db, rows)
        if not val.get("ok"):
            return jsonify(val), 400
        try:
            result = save_branch_import(
                db,
                val["parsed_rows"],
                username=_username(),
                filename=(upload.filename if upload else "") or "import.json",
                customer_id=session.get("customer_id"),
            )
            log_import(
                db,
                module_key="branches",
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

    @app.route("/api/branch-master/<int:branch_id>/audit")
    @login_required
    def branch_master_audit(branch_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify({"items": list_branch_audit_trail(db, branch_id), "branch_id": branch_id})

    @app.route("/api/branch-master/reports/<report_key>")
    @login_required
    def branch_master_report_route(report_key: str):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        rows = branch_report(
            db,
            report_key,
            company_id=request.args.get("company_id", type=int),
            country=request.args.get("country") or "",
        )
        if isinstance(rows, dict):
            return jsonify(rows)
        return jsonify({"report": report_key, "count": len(rows), "items": rows})

    @app.route("/api/branch-master/ai/validate", methods=["POST"])
    @login_required
    def branch_master_ai_validate():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or {}
        branch_id = payload.get("branch_id") or request.form.get("branch_id", type=int)
        form = payload.get("form") or request.form.to_dict(flat=True)
        return jsonify(ai_validate_branch(db, branch_id=branch_id, form=form or None))

    @app.route("/api/mobile/branches", methods=["GET"])
    @login_required
    def api_mobile_list_branches():
        db = get_db()
        if not user_can_branch_master(db, _user_id(), "view", is_admin=is_admin_user()):
            return jsonify({"error": "Permission denied"}), 403
        company_id = request.args.get("company_id", type=int) or session.get("company_id")
        listing = list_branches_master(db, company_id=company_id, status="Active", per_page=500)
        items = [
            {
                "id": b["id"],
                "branch_code": b.get("branch_code"),
                "branch_name": b.get("branch_name"),
                "city": b.get("city"),
                "company_code": b.get("company_code"),
                "company_name": b.get("company_name"),
            }
            for b in listing["items"]
        ]
        return jsonify({"items": items, "count": len(items)})

    @app.route("/api/mobile/branches/<int:branch_id>", methods=["GET"])
    @login_required
    def api_mobile_get_branch(branch_id: int):
        db = get_db()
        if not user_can_branch_master(db, _user_id(), "view", is_admin=is_admin_user()):
            return jsonify({"error": "Permission denied"}), 403
        row = get_branch_master(db, branch_id)
        if not row:
            return jsonify({"error": "Branch not found"}), 404
        return jsonify(
            {
                "id": row["id"],
                "branch_code": row.get("branch_code"),
                "branch_name": row.get("branch_name"),
                "branch_type": row.get("branch_type"),
                "company_code": row.get("company_code"),
                "company_name": row.get("company_name"),
                "country": row.get("country"),
                "city": row.get("city"),
                "state_region": row.get("state_region"),
                "phone": row.get("phone"),
                "email": row.get("email"),
                "status": row.get("status"),
            }
        )
