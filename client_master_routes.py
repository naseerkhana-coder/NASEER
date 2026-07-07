"""Client Master API routes — export, import, audit, reports, AI, mobile."""

from __future__ import annotations

from typing import Callable

from flask import Response, jsonify, request, send_file, session

from bulk_import_service import parse_upload
from client_import_service import save_client_import, validate_client_import
from client_master_service import (
    ai_validate_client,
    client_import_template,
    client_report,
    export_clients_csv,
    export_clients_excel,
    export_clients_pdf,
    get_client_master,
    list_client_audit_trail,
    list_clients_master,
    user_can_client_master,
)
from import_audit_service import log_import


def register_client_master_routes(
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
        if not user_can_client_master(db, _user_id(), action, is_admin=is_admin_user()):
            return jsonify({"error": f"Permission denied: {action}"}), 403
        return None

    @app.route("/api/client-master/export")
    @login_required
    def client_master_export():
        denied = _require("export")
        if denied:
            return denied
        fmt = (request.args.get("format") or "xlsx").lower().strip()
        db = get_db()
        filters = {
            "include_deleted": request.args.get("include_deleted") == "1",
            "company_id": request.args.get("company_id", type=int),
            "client_type": request.args.get("client_type") or "",
            "status": request.args.get("status") or "",
            "industry": request.args.get("industry") or "",
            "search": request.args.get("q") or "",
        }
        clean_filters = {
            k: v for k, v in filters.items() if v not in (None, "", False) or k == "include_deleted"
        }
        report = request.args.get("report", "")
        if report:
            title = report.replace("_", " ").title()
            buf = export_clients_pdf(db, report_title=title, **clean_filters)
            return send_file(
                buf, mimetype="application/pdf", as_attachment=True, download_name=f"clients_{report}.pdf"
            )
        if fmt in ("xlsx", "excel"):
            buf = export_clients_excel(db, **clean_filters)
            return send_file(
                buf,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name="clients.xlsx",
            )
        if fmt == "csv":
            csv_text = export_clients_csv(db, **clean_filters)
            return Response(
                csv_text,
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment; filename=clients.csv"},
            )
        if fmt == "pdf":
            buf = export_clients_pdf(db, **clean_filters)
            return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name="clients.pdf")
        return jsonify({"error": "Unsupported format. Use xlsx, csv, or pdf."}), 400

    @app.route("/api/client-master/import/template")
    @login_required
    def client_master_import_template():
        denied = _require("import")
        if denied:
            return denied
        buf = client_import_template()
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="client_master_template.xlsx",
        )

    @app.route("/api/client-master/import/validate", methods=["POST"])
    @login_required
    def client_master_import_validate():
        denied = _require("import")
        if denied:
            return denied
        db = get_db()
        upload = request.files.get("file")
        rows, parse_err = parse_upload(upload)
        if parse_err:
            return jsonify({"ok": False, "errors": [{"row": "—", "column": "File", "error": parse_err}]}), 400
        return jsonify(validate_client_import(db, rows))

    @app.route("/api/client-master/import/save", methods=["POST"])
    @login_required
    def client_master_import_save():
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
        val = validate_client_import(db, rows)
        if not val.get("ok"):
            return jsonify(val), 400
        try:
            result = save_client_import(
                db,
                val["parsed_rows"],
                username=_username(),
                filename=(upload.filename if upload else "") or "import.json",
                customer_id=session.get("customer_id"),
            )
            log_import(
                db,
                module_key="clients",
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

    @app.route("/api/client-master/<int:client_id>/audit")
    @login_required
    def client_master_audit(client_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify({"items": list_client_audit_trail(db, client_id), "client_id": client_id})

    @app.route("/api/client-master/reports/<report_key>")
    @login_required
    def client_master_report_route(report_key: str):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        rows = client_report(
            db,
            report_key,
            company_id=request.args.get("company_id", type=int),
            client_type=request.args.get("client_type") or "",
            status=request.args.get("status") or "",
        )
        return jsonify({"report": report_key, "count": len(rows), "items": rows})

    @app.route("/api/client-master/ai/validate", methods=["POST"])
    @login_required
    def client_master_ai_validate():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or {}
        client_id = payload.get("client_id") or request.form.get("client_id", type=int)
        form = payload.get("form") or request.form.to_dict(flat=True)
        return jsonify(ai_validate_client(db, client_id=client_id, form=form or None))

    @app.route("/api/mobile/clients", methods=["GET"])
    @login_required
    def api_mobile_list_clients():
        db = get_db()
        if not user_can_client_master(db, _user_id(), "view", is_admin=is_admin_user()):
            return jsonify({"error": "Permission denied"}), 403
        search = request.args.get("q", "")
        listing = list_clients_master(
            db,
            search=search,
            status=request.args.get("status") or "Active",
            per_page=min(request.args.get("limit", 500, type=int), 500),
        )
        items = [
            {
                "id": c["id"],
                "client_code": c.get("client_code"),
                "client_name": c.get("client_name"),
                "company_name": c.get("company_name"),
                "gst_number": c.get("gst_number"),
                "city": c.get("city"),
                "status": c.get("status"),
            }
            for c in listing["items"]
        ]
        return jsonify({"items": items, "count": len(items)})

    @app.route("/api/mobile/clients/<int:client_id>", methods=["GET"])
    @login_required
    def api_mobile_get_client(client_id: int):
        db = get_db()
        if not user_can_client_master(db, _user_id(), "view", is_admin=is_admin_user()):
            return jsonify({"error": "Permission denied"}), 403
        row = get_client_master(db, client_id)
        if not row:
            return jsonify({"error": "Client not found"}), 404
        return jsonify(
            {
                "id": row["id"],
                "client_code": row.get("client_code"),
                "client_name": row.get("client_name"),
                "legal_name": row.get("legal_name"),
                "company_name": row.get("company_name"),
                "client_type": row.get("client_type"),
                "industry": row.get("industry"),
                "gst_number": row.get("gst_number"),
                "pan_number": row.get("pan_number"),
                "email": row.get("email"),
                "phone": row.get("phone"),
                "mobile": row.get("mobile"),
                "billing_address": row.get("billing_address"),
                "site_address": row.get("site_address"),
                "city": row.get("city"),
                "state": row.get("state"),
                "status": row.get("status"),
                "contacts": row.get("contacts") or [],
                "addresses": row.get("addresses") or [],
                "project_count": row.get("project_count", 0),
            }
        )
