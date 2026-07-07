"""BOQ Management API routes — export, import, audit, reports, AI, mobile."""

from __future__ import annotations

from typing import Callable

from flask import Response, jsonify, request, send_file, session

from bulk_import_service import parse_upload
from boq_management_import_service import (
    boq_management_import_template,
    save_boq_management_import,
    validate_boq_management_import,
)
from boq_management_service import (
    boq_report,
    compare_boqs,
    detect_duplicate_items,
    export_boq_items_excel,
    export_boqs_csv,
    export_boqs_excel,
    export_boqs_pdf,
    get_boq_balance_summary,
    get_boq_items_for_project,
    get_boq_master,
    list_boq_audit_trail,
    list_boq_items,
    list_boqs_master,
    quantity_anomaly_check,
    user_can_boq_management,
    validate_boq,
)
from import_audit_service import log_import


def register_boq_management_routes(
    app,
    *,
    login_required: Callable,
    get_db: Callable,
    is_admin_user: Callable,
    boq_units: list[str] | None = None,
    create_approval_request: Callable | None = None,
    record_pending_checker: str = "Pending Checker",
) -> None:
    units = boq_units or []

    def _user_id() -> int | None:
        return session.get("user_id")

    def _username() -> str:
        return str(session.get("username") or "")

    def _require(action: str):
        db = get_db()
        if not user_can_boq_management(db, _user_id(), action, is_admin=is_admin_user()):
            return jsonify({"error": f"Permission denied: {action}"}), 403
        return None

    @app.route("/api/boq-management/export")
    @login_required
    def boq_management_export():
        denied = _require("export")
        if denied:
            return denied
        fmt = (request.args.get("format") or "xlsx").lower().strip()
        db = get_db()
        filters = {
            "include_deleted": request.args.get("include_deleted") == "1",
            "project_id": request.args.get("project_id", type=int),
            "status": request.args.get("status") or "",
            "approval_status": request.args.get("approval_status") or "",
            "current_only": request.args.get("current_only") == "1",
            "search": request.args.get("q") or "",
        }
        clean_filters = {
            k: v for k, v in filters.items() if v not in (None, "", False) or k in ("include_deleted", "current_only")
        }
        boq_id = request.args.get("boq_id", type=int)
        if boq_id and fmt in ("xlsx", "excel", "items"):
            buf = export_boq_items_excel(db, boq_id)
            return send_file(
                buf,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name=f"boq_items_{boq_id}.xlsx",
            )
        report = request.args.get("report", "")
        if report:
            title = report.replace("_", " ").title()
            buf = export_boqs_pdf(db, report_title=title, **clean_filters)
            return send_file(
                buf,
                mimetype="application/pdf",
                as_attachment=True,
                download_name=f"boq_{report}.pdf",
            )
        if fmt in ("xlsx", "excel"):
            buf = export_boqs_excel(db, **clean_filters)
            return send_file(
                buf,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name="boq_register.xlsx",
            )
        if fmt == "csv":
            csv_text = export_boqs_csv(db, **clean_filters)
            return Response(
                csv_text,
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment; filename=boq_register.csv"},
            )
        if fmt == "pdf":
            buf = export_boqs_pdf(db, **clean_filters)
            return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name="boq_register.pdf")
        return jsonify({"error": "Unsupported format. Use xlsx, csv, pdf, or items."}), 400

    @app.route("/api/boq-management/import/template")
    @login_required
    def boq_management_import_template_route():
        denied = _require("import")
        if denied:
            return denied
        buf = boq_management_import_template()
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="boq_management_template.xlsx",
        )

    @app.route("/api/boq-management/import/validate", methods=["POST"])
    @login_required
    def boq_management_import_validate():
        denied = _require("import")
        if denied:
            return denied
        db = get_db()
        upload = request.files.get("file")
        rows, parse_err = parse_upload(upload)
        if parse_err:
            return jsonify({"ok": False, "errors": [{"row": "—", "column": "File", "error": parse_err}]}), 400
        project_id = request.form.get("project_id", type=int) or request.args.get("project_id", type=int)
        return jsonify(
            validate_boq_management_import(
                db,
                rows,
                boq_units=units,
                project_id=project_id,
                boq_name=request.form.get("boq_name") or "",
            )
        )

    @app.route("/api/boq-management/import/save", methods=["POST"])
    @login_required
    def boq_management_import_save():
        denied = _require("import")
        if denied:
            return denied
        db = get_db()
        upload = request.files.get("file")
        rows, parse_err = parse_upload(upload) if upload else ([], None)
        if not rows:
            payload = request.get_json(silent=True) or {}
            rows = payload.get("parsed_rows") or payload.get("rows") or []
        project_id = (
            request.form.get("project_id", type=int)
            or request.args.get("project_id", type=int)
            or (request.get_json(silent=True) or {}).get("project_id")
        )
        if not project_id:
            return jsonify({"ok": False, "error": "project_id is required."}), 400
        if parse_err and not rows:
            return jsonify({"ok": False, "error": parse_err}), 400
        val = validate_boq_management_import(
            db,
            rows,
            boq_units=units,
            project_id=int(project_id),
            boq_name=request.form.get("boq_name") or "",
        )
        if not val.get("ok"):
            return jsonify(val), 400
        try:
            result = save_boq_management_import(
                db,
                val["parsed_rows"],
                project_id=int(project_id),
                username=_username(),
                filename=(upload.filename if upload else "") or "import.json",
                boq_name=request.form.get("boq_name") or "",
                client_reference=request.form.get("client_reference") or "",
                contract_reference=request.form.get("contract_reference") or "",
                create_approval_request_fn=create_approval_request,
                record_pending_checker=record_pending_checker,
            )
            db.commit()
            log_import(
                db,
                module_key="boq_management",
                imported_by=_username(),
                filename=(upload.filename if upload else "") or "import.json",
                total_rows=len(val["parsed_rows"]),
                success_rows=result.get("line_count", len(val["parsed_rows"])),
                failed_rows=0,
            )
            db.commit()
            return jsonify({"ok": True, **result})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/boq-management/search", methods=["GET"])
    @login_required
    def boq_management_search():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        listing = list_boqs_master(
            db,
            search=request.args.get("q") or "",
            project_id=request.args.get("project_id", type=int),
            status=request.args.get("status") or "",
            approval_status=request.args.get("approval_status") or "",
            current_only=request.args.get("current_only") == "1",
            page=request.args.get("page", 1, type=int),
            per_page=min(request.args.get("per_page", 25, type=int), 100),
        )
        return jsonify(listing)

    @app.route("/api/boq-management/<int:boq_id>", methods=["GET"])
    @login_required
    def boq_management_detail(boq_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        row = get_boq_master(db, boq_id)
        if not row:
            return jsonify({"error": "BOQ not found."}), 404
        return jsonify(row)

    @app.route("/api/boq-management/<int:boq_id>/items", methods=["GET"])
    @login_required
    def boq_management_items(boq_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify({"boq_id": boq_id, "items": list_boq_items(db, boq_id)})

    @app.route("/api/boq-management/<int:boq_id>/audit", methods=["GET"])
    @login_required
    def boq_management_audit(boq_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify({"boq_id": boq_id, "audit": list_boq_audit_trail(db, boq_id)})

    @app.route("/api/boq-management/reports/<report_key>", methods=["GET"])
    @login_required
    def boq_management_report(report_key: str):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        rows = boq_report(
            db,
            report_key,
            project_id=request.args.get("project_id", type=int),
            search=request.args.get("q") or "",
            status=request.args.get("status") or "",
        )
        return jsonify({"report": report_key, "count": len(rows), "items": rows})

    @app.route("/api/boq-management/project/<int:project_id>/items", methods=["GET"])
    @login_required
    def boq_management_project_items(project_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        boq_id = request.args.get("boq_id", type=int)
        return jsonify(
            {
                "project_id": project_id,
                "items": get_boq_items_for_project(db, project_id, boq_id=boq_id),
                "summary": get_boq_balance_summary(db, project_id),
            }
        )

    @app.route("/api/boq-management/ai/validate", methods=["POST"])
    @login_required
    def boq_management_ai_validate():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or {}
        return jsonify(
            validate_boq(
                db,
                boq_id=payload.get("boq_id") or request.form.get("boq_id", type=int),
                form=payload.get("form"),
            )
        )

    @app.route("/api/boq-management/ai/compare", methods=["POST"])
    @login_required
    def boq_management_ai_compare():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or {}
        a = payload.get("boq_id_a") or request.form.get("boq_id_a", type=int)
        b = payload.get("boq_id_b") or request.form.get("boq_id_b", type=int)
        if not a or not b:
            return jsonify({"error": "boq_id_a and boq_id_b required."}), 400
        return jsonify(compare_boqs(db, int(a), int(b)))

    @app.route("/api/boq-management/ai/duplicates", methods=["POST"])
    @login_required
    def boq_management_ai_duplicates():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or {}
        boq_id = payload.get("boq_id") or request.form.get("boq_id", type=int)
        return jsonify(detect_duplicate_items(db, boq_id=boq_id))

    @app.route("/api/boq-management/ai/quantity-anomaly", methods=["POST"])
    @login_required
    def boq_management_ai_quantity_anomaly():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or {}
        boq_id = payload.get("boq_id") or request.form.get("boq_id", type=int)
        return jsonify(quantity_anomaly_check(db, boq_id=boq_id))

    @app.route("/api/mobile/boq", methods=["GET"])
    @login_required
    def api_mobile_boq_list():
        db = get_db()
        if not user_can_boq_management(db, _user_id(), "view", is_admin=is_admin_user()):
            return jsonify({"error": "Permission denied"}), 403
        listing = list_boqs_master(
            db,
            search=request.args.get("q") or "",
            project_id=request.args.get("project_id", type=int),
            current_only=True,
            page=request.args.get("page", 1, type=int),
            per_page=min(request.args.get("per_page", 50, type=int), 100),
        )
        items = []
        for row in listing["items"]:
            items.append(
                {
                    "id": row.get("id"),
                    "boq_number": row.get("boq_number"),
                    "boq_name": row.get("boq_name"),
                    "project_code": row.get("project_code"),
                    "project_name": row.get("project_name"),
                    "revision_number": row.get("revision_number"),
                    "status": row.get("status"),
                    "approval_status": row.get("approval_status"),
                    "total_amount": row.get("total_amount"),
                    "line_count": row.get("line_count"),
                }
            )
        return jsonify({"count": listing["total"], "items": items, "page": listing["page"]})

    @app.route("/api/mobile/boq/<int:boq_id>", methods=["GET"])
    @login_required
    def api_mobile_boq_detail(boq_id: int):
        db = get_db()
        if not user_can_boq_management(db, _user_id(), "view", is_admin=is_admin_user()):
            return jsonify({"error": "Permission denied"}), 403
        row = get_boq_master(db, boq_id)
        if not row:
            return jsonify({"error": "BOQ not found."}), 404
        return jsonify(
            {
                "id": row.get("id"),
                "boq_number": row.get("boq_number"),
                "boq_name": row.get("boq_name"),
                "project_code": row.get("project_code"),
                "project_name": row.get("project_name"),
                "client_name": row.get("client_name"),
                "revision_number": row.get("revision_number"),
                "status": row.get("status"),
                "approval_status": row.get("approval_status"),
                "total_amount": row.get("total_amount"),
                "items": row.get("items") or [],
                "revisions": row.get("revisions") or [],
            }
        )

    @app.route("/api/mobile/boq/search", methods=["GET"])
    @login_required
    def api_mobile_boq_search():
        return boq_management_search()
