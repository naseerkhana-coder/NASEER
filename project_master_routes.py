"""Project Master API routes — export, import, audit, reports, AI, mobile."""

from __future__ import annotations

from typing import Callable

from flask import Response, jsonify, request, send_file, session

from bulk_import_service import parse_upload
from import_audit_service import log_import
from project_import_service import save_project_import, validate_project_import
from project_master_service import (
    cost_prediction_stub,
    delay_prediction_stub,
    export_projects_csv,
    export_projects_excel,
    export_projects_pdf,
    get_project_dashboard_summary,
    get_project_master,
    list_project_audit_trail,
    list_projects_master,
    progress_analysis_stub,
    project_health_check,
    project_report,
    risk_flags,
    user_can_project_master,
)


def register_project_master_routes(
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
        if not user_can_project_master(db, _user_id(), action, is_admin=is_admin_user()):
            return jsonify({"error": f"Permission denied: {action}"}), 403
        return None

    @app.route("/api/project-master/export")
    @login_required
    def project_master_export():
        denied = _require("export")
        if denied:
            return denied
        fmt = (request.args.get("format") or "xlsx").lower().strip()
        db = get_db()
        filters = {
            "include_deleted": request.args.get("include_deleted") == "1",
            "company_id": request.args.get("company_id", type=int),
            "branch_id": request.args.get("branch_id", type=int),
            "client_id": request.args.get("client_id", type=int),
            "project_status": request.args.get("project_status") or "",
            "project_type": request.args.get("project_type") or "",
            "status": request.args.get("status") or "",
            "search": request.args.get("q") or "",
        }
        clean_filters = {
            k: v for k, v in filters.items() if v not in (None, "", False) or k == "include_deleted"
        }
        report = request.args.get("report", "")
        if report:
            title = report.replace("_", " ").title()
            buf = export_projects_pdf(db, report_title=title, **clean_filters)
            return send_file(
                buf,
                mimetype="application/pdf",
                as_attachment=True,
                download_name=f"projects_{report}.pdf",
            )
        if fmt in ("xlsx", "excel"):
            buf = export_projects_excel(db, **clean_filters)
            return send_file(
                buf,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name="projects.xlsx",
            )
        if fmt == "csv":
            csv_text = export_projects_csv(db, **clean_filters)
            return Response(
                csv_text,
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment; filename=projects.csv"},
            )
        if fmt == "pdf":
            buf = export_projects_pdf(db, **clean_filters)
            return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name="projects.pdf")
        return jsonify({"error": "Unsupported format. Use xlsx, csv, or pdf."}), 400

    @app.route("/api/project-master/import/template")
    @login_required
    def project_master_import_template_route():
        denied = _require("import")
        if denied:
            return denied
        from project_master_service import project_import_template

        buf = project_import_template()
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="project_master_template.xlsx",
        )

    @app.route("/api/project-master/import/validate", methods=["POST"])
    @login_required
    def project_master_import_validate():
        denied = _require("import")
        if denied:
            return denied
        db = get_db()
        upload = request.files.get("file")
        rows, parse_err = parse_upload(upload)
        if parse_err:
            return jsonify({"ok": False, "errors": [{"row": "—", "column": "File", "error": parse_err}]}), 400
        return jsonify(validate_project_import(db, rows))

    @app.route("/api/project-master/import/save", methods=["POST"])
    @login_required
    def project_master_import_save():
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
        val = validate_project_import(db, rows)
        if not val.get("ok"):
            return jsonify(val), 400
        try:
            result = save_project_import(
                db,
                val["parsed_rows"],
                username=_username(),
                filename=(upload.filename if upload else "") or "import.json",
                customer_id=session.get("customer_id"),
            )
            log_import(
                db,
                module_key="projects",
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

    @app.route("/api/project-master/<int:project_id>/audit")
    @login_required
    def project_master_audit(project_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify({"items": list_project_audit_trail(db, project_id), "project_id": project_id})

    @app.route("/api/project-master/<int:project_id>/dashboard")
    @login_required
    def project_master_dashboard_api(project_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        summary = get_project_dashboard_summary(db, project_id)
        return jsonify(summary)

    @app.route("/api/project-master/reports/<report_key>")
    @login_required
    def project_master_report_route(report_key: str):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        rows = project_report(
            db,
            report_key,
            company_id=request.args.get("company_id", type=int),
            branch_id=request.args.get("branch_id", type=int),
            client_id=request.args.get("client_id", type=int),
            project_status=request.args.get("project_status") or "",
            status=request.args.get("status") or "",
        )
        return jsonify({"report": report_key, "count": len(rows), "items": rows})

    @app.route("/api/project-master/ai/health/<int:project_id>")
    @login_required
    def project_master_ai_health(project_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify(project_health_check(db, project_id))

    @app.route("/api/project-master/ai/risks/<int:project_id>")
    @login_required
    def project_master_ai_risks(project_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify({"flags": risk_flags(db, project_id)})

    @app.route("/api/project-master/ai/delay/<int:project_id>")
    @login_required
    def project_master_ai_delay(project_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify(delay_prediction_stub(db, project_id))

    @app.route("/api/project-master/ai/cost/<int:project_id>")
    @login_required
    def project_master_ai_cost(project_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify(cost_prediction_stub(db, project_id))

    @app.route("/api/project-master/ai/progress/<int:project_id>")
    @login_required
    def project_master_ai_progress(project_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify(progress_analysis_stub(db, project_id))

    @app.route("/api/mobile/projects", methods=["GET"])
    @login_required
    def api_mobile_list_projects():
        db = get_db()
        if not user_can_project_master(db, _user_id(), "view", is_admin=is_admin_user()):
            return jsonify({"error": "Permission denied"}), 403
        listing = list_projects_master(
            db,
            search=request.args.get("q") or "",
            company_id=request.args.get("company_id", type=int),
            branch_id=request.args.get("branch_id", type=int),
            client_id=request.args.get("client_id", type=int),
            project_status=request.args.get("project_status") or "",
            status=request.args.get("status") or "Active",
            page=request.args.get("page", 1, type=int),
            per_page=min(request.args.get("per_page", 50, type=int), 100),
        )
        items = []
        for row in listing["items"]:
            items.append(
                {
                    "id": row.get("id"),
                    "project_code": row.get("project_code"),
                    "project_name": row.get("project_name"),
                    "short_name": row.get("short_name"),
                    "client_name": row.get("client_name"),
                    "project_status": row.get("project_status"),
                    "city": row.get("city"),
                    "latitude": row.get("latitude"),
                    "longitude": row.get("longitude"),
                    "start_date": row.get("start_date"),
                    "planned_completion_date": row.get("planned_completion_date"),
                    "project_value": row.get("project_value"),
                    "status": row.get("status"),
                }
            )
        return jsonify({"count": listing["total"], "items": items, "page": listing["page"]})

    @app.route("/api/mobile/projects/<int:project_id>", methods=["GET"])
    @login_required
    def api_mobile_project_detail(project_id: int):
        db = get_db()
        if not user_can_project_master(db, _user_id(), "view", is_admin=is_admin_user()):
            return jsonify({"error": "Permission denied"}), 403
        row = get_project_master(db, project_id)
        if not row:
            return jsonify({"error": "Project not found"}), 404
        return jsonify(
            {
                "id": row.get("id"),
                "project_code": row.get("project_code"),
                "project_name": row.get("project_name"),
                "short_name": row.get("short_name"),
                "project_type": row.get("project_type"),
                "project_status": row.get("project_status"),
                "client_id": row.get("client_id"),
                "client_name": row.get("client_name"),
                "company_id": row.get("company_id"),
                "branch_id": row.get("branch_id"),
                "project_manager_name": row.get("project_manager_name"),
                "engineer_name": row.get("engineer_name"),
                "location": row.get("location"),
                "site_address": row.get("site_address"),
                "city": row.get("city"),
                "state": row.get("state"),
                "latitude": row.get("latitude"),
                "longitude": row.get("longitude"),
                "start_date": row.get("start_date"),
                "planned_completion_date": row.get("planned_completion_date"),
                "project_value": row.get("project_value"),
                "currency": row.get("currency"),
                "description": row.get("description"),
                "team_count": len(row.get("team") or []),
                "photo_count": row.get("photo_count"),
                "document_count": row.get("document_count"),
            }
        )

    @app.route("/api/mobile/projects/<int:project_id>/dashboard", methods=["GET"])
    @login_required
    def api_mobile_project_dashboard(project_id: int):
        db = get_db()
        if not user_can_project_master(db, _user_id(), "view", is_admin=is_admin_user()):
            return jsonify({"error": "Permission denied"}), 403
        return jsonify(get_project_dashboard_summary(db, project_id))

    @app.route("/api/mobile/projects/search", methods=["GET"])
    @login_required
    def api_mobile_search_projects():
        db = get_db()
        if not user_can_project_master(db, _user_id(), "view", is_admin=is_admin_user()):
            return jsonify({"error": "Permission denied"}), 403
        q = request.args.get("q") or ""
        listing = list_projects_master(db, search=q, status="Active", per_page=30)
        return jsonify(
            {
                "q": q,
                "items": [
                    {
                        "id": r.get("id"),
                        "project_code": r.get("project_code"),
                        "project_name": r.get("project_name"),
                        "latitude": r.get("latitude"),
                        "longitude": r.get("longitude"),
                    }
                    for r in listing["items"]
                ],
            }
        )
