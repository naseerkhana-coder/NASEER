"""Worker Master API routes — export, import, audit, reports, AI, mobile, face registration."""

from __future__ import annotations

import base64
import os
from typing import Callable

from flask import Response, jsonify, request, send_file, session

from bulk_import_service import parse_upload
from import_audit_service import log_import
from worker_import_service import save_worker_import, validate_worker_import
from worker_master_service import (
    ai_validate_worker,
    export_workers_csv,
    export_workers_excel,
    export_workers_pdf,
    get_face_template_reference,
    get_worker_master,
    list_worker_audit_trail,
    list_workers_for_project,
    list_workers_master,
    register_face_template,
    user_can_worker_master,
    validate_worker_for_attendance,
    worker_import_template,
    worker_report,
    worker_upload_dir,
)


def register_worker_master_routes(
    app,
    *,
    login_required: Callable,
    get_db: Callable,
    is_admin_user: Callable,
    base_dir: str | None = None,
) -> None:
    upload_root = base_dir or os.path.dirname(os.path.abspath(__file__))

    def _user_id() -> int | None:
        return session.get("user_id")

    def _username() -> str:
        return str(session.get("username") or "")

    def _require(action: str):
        db = get_db()
        if not user_can_worker_master(db, _user_id(), action, is_admin=is_admin_user()):
            return jsonify({"error": f"Permission denied: {action}"}), 403
        return None

    @app.route("/api/worker-master/export")
    @login_required
    def worker_master_export():
        denied = _require("export")
        if denied:
            return denied
        fmt = (request.args.get("format") or "xlsx").lower().strip()
        db = get_db()
        filters = {
            "include_deleted": request.args.get("include_deleted") == "1",
            "status": request.args.get("status") or "",
            "worker_type": request.args.get("worker_type") or "",
            "trade": request.args.get("trade") or "",
            "subcontractor_id": request.args.get("subcontractor_id", type=int),
            "project_id": request.args.get("project_id", type=int),
            "company_id": request.args.get("company_id", type=int),
            "search": request.args.get("q") or "",
        }
        clean_filters = {
            k: v for k, v in filters.items() if v not in (None, "", False) or k == "include_deleted"
        }
        report = request.args.get("report", "")
        if report:
            title = report.replace("_", " ").title()
            buf = export_workers_pdf(db, report_title=title, **clean_filters)
            return send_file(
                buf,
                mimetype="application/pdf",
                as_attachment=True,
                download_name=f"workers_{report}.pdf",
            )
        if fmt in ("xlsx", "excel"):
            buf = export_workers_excel(db, **clean_filters)
            return send_file(
                buf,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name="workers.xlsx",
            )
        if fmt == "csv":
            csv_text = export_workers_csv(db, **clean_filters)
            return Response(
                csv_text,
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment; filename=workers.csv"},
            )
        if fmt == "pdf":
            buf = export_workers_pdf(db, **clean_filters)
            return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name="workers.pdf")
        return jsonify({"error": "Unsupported format. Use xlsx, csv, or pdf."}), 400

    @app.route("/api/worker-master/import/template")
    @login_required
    def worker_master_import_template_route():
        denied = _require("import")
        if denied:
            return denied
        buf = worker_import_template()
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="worker_master_template.xlsx",
        )

    @app.route("/api/worker-master/import/validate", methods=["POST"])
    @login_required
    def worker_master_import_validate():
        denied = _require("import")
        if denied:
            return denied
        db = get_db()
        upload = request.files.get("file")
        rows, parse_err = parse_upload(upload)
        if parse_err:
            return jsonify({"ok": False, "errors": [{"row": "—", "column": "File", "error": parse_err}]}), 400
        return jsonify(validate_worker_import(db, rows))

    @app.route("/api/worker-master/import/save", methods=["POST"])
    @login_required
    def worker_master_import_save():
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
        val = validate_worker_import(db, rows)
        if not val.get("ok"):
            return jsonify(val), 400
        try:
            result = save_worker_import(
                db,
                val["parsed_rows"],
                username=_username(),
                filename=(upload.filename if upload else "") or "import.json",
                customer_id=session.get("customer_id"),
            )
            log_import(
                db,
                module_key="workers",
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

    @app.route("/api/worker-master/<int:worker_id>/audit")
    @login_required
    def worker_master_audit(worker_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify({"items": list_worker_audit_trail(db, worker_id), "worker_id": worker_id})

    @app.route("/api/worker-master/reports/<report_key>")
    @login_required
    def worker_master_report_route(report_key: str):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        rows = worker_report(
            db,
            report_key,
            status=request.args.get("status") or "",
            trade=request.args.get("trade") or "",
            skill=request.args.get("skill") or "",
            project_id=request.args.get("project_id", type=int),
            subcontractor_id=request.args.get("subcontractor_id", type=int),
            company_id=request.args.get("company_id", type=int),
        )
        return jsonify({"report": report_key, "count": len(rows), "items": rows})

    @app.route("/api/worker-master/ai/validate", methods=["POST"])
    @login_required
    def worker_master_ai_validate():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or {}
        worker_id = payload.get("worker_id") or request.form.get("worker_id", type=int)
        form = payload.get("form") or request.form.to_dict(flat=True)
        return jsonify(ai_validate_worker(db, worker_id=worker_id, form=form or None))

    @app.route("/api/worker-master/search", methods=["GET"])
    @login_required
    def worker_master_search():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        listing = list_workers_master(
            db,
            search=request.args.get("q") or "",
            status=request.args.get("status") or "",
            worker_type=request.args.get("worker_type") or "",
            trade=request.args.get("trade") or "",
            subcontractor_id=request.args.get("subcontractor_id", type=int),
            project_id=request.args.get("project_id", type=int),
            page=request.args.get("page", 1, type=int),
            per_page=min(request.args.get("per_page", 25, type=int), 100),
        )
        return jsonify(listing)

    @app.route("/api/worker-master/project/<int:project_id>/workers")
    @login_required
    def worker_master_project_workers(project_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify({"project_id": project_id, "items": list_workers_for_project(db, project_id)})

    @app.route("/api/worker-master/<int:worker_id>/attendance-check")
    @login_required
    def worker_master_attendance_check(worker_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify(validate_worker_for_attendance(db, worker_id))

    @app.route("/api/worker-master/<int:worker_id>/face-template", methods=["GET"])
    @login_required
    def worker_master_face_template_get(worker_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        ref = get_face_template_reference(db, worker_id)
        return jsonify({"worker_id": worker_id, "template_reference": ref})

    @app.route("/api/worker-master/<int:worker_id>/face-registration", methods=["POST"])
    @login_required
    def worker_master_face_registration(worker_id: int):
        denied = _require("edit")
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or {}
        template_ref = payload.get("template_reference") or request.form.get("template_reference")
        upload_dir = worker_upload_dir(upload_root)
        if not template_ref:
            upload = request.files.get("face_image") or request.files.get("file")
            b64 = payload.get("image_base64") or request.form.get("image_base64")
            if upload and upload.filename:
                ext = os.path.splitext(upload.filename)[1].lower() or ".jpg"
                fname = f"face_{worker_id}_{os.urandom(4).hex()}{ext}"
                path = os.path.join(upload_dir, fname)
                upload.save(path)
                template_ref = f"uploads/workers/{fname}"
            elif b64:
                raw = b64.split(",", 1)[-1] if "," in b64 else b64
                data = base64.b64decode(raw)
                fname = f"face_{worker_id}_{os.urandom(4).hex()}.jpg"
                path = os.path.join(upload_dir, fname)
                with open(path, "wb") as fh:
                    fh.write(data)
                template_ref = f"uploads/workers/{fname}"
        if not template_ref:
            return jsonify({"error": "Provide template_reference, face_image file, or image_base64."}), 400
        try:
            result = register_face_template(
                db,
                worker_id,
                str(template_ref),
                {
                    "registered_by": _username(),
                    "device_info": payload.get("device_info") or request.form.get("device_info") or "",
                },
            )
            db.commit()
            return jsonify(result)
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/mobile/workers", methods=["GET"])
    @login_required
    def api_mobile_list_workers():
        db = get_db()
        if not user_can_worker_master(db, _user_id(), "view", is_admin=is_admin_user()):
            return jsonify({"error": "Permission denied"}), 403
        listing = list_workers_master(
            db,
            search=request.args.get("q") or "",
            status=request.args.get("status") or "Active",
            project_id=request.args.get("project_id", type=int),
            page=request.args.get("page", 1, type=int),
            per_page=min(request.args.get("per_page", 50, type=int), 100),
        )
        items = []
        for row in listing["items"]:
            items.append(
                {
                    "id": row.get("id"),
                    "worker_code": row.get("worker_code"),
                    "name": row.get("worker_name"),
                    "trade": row.get("trade"),
                    "worker_type": row.get("worker_type"),
                    "mobile": row.get("mobile"),
                    "status": row.get("status"),
                    "project_code": row.get("project_code"),
                    "subcontractor_name": row.get("subcontractor_name"),
                    "photo": row.get("photo"),
                    "face_template_ref": row.get("face_template_ref"),
                }
            )
        return jsonify({"count": listing["total"], "items": items, "page": listing["page"]})

    @app.route("/api/mobile/workers/<int:worker_id>", methods=["GET"])
    @login_required
    def api_mobile_worker_profile(worker_id: int):
        db = get_db()
        if not user_can_worker_master(db, _user_id(), "view", is_admin=is_admin_user()):
            return jsonify({"error": "Permission denied"}), 403
        row = get_worker_master(db, worker_id)
        if not row:
            return jsonify({"error": "Worker not found"}), 404
        return jsonify(
            {
                "id": row.get("id"),
                "worker_code": row.get("worker_code"),
                "name": row.get("worker_name"),
                "worker_type": row.get("worker_type"),
                "trade": row.get("trade"),
                "skill": row.get("skill"),
                "mobile": row.get("mobile"),
                "status": row.get("status"),
                "project_code": row.get("project_code"),
                "project_name": row.get("project_name"),
                "subcontractor_name": row.get("subcontractor_name"),
                "joining_date": row.get("joining_date"),
                "photo": row.get("photo"),
                "face_template_ref": get_face_template_reference(db, worker_id),
                "emergency_contacts": row.get("emergency_contacts") or [],
                "project_assignments": row.get("project_assignments") or [],
                "attendance_mode": row.get("attendance_mode"),
            }
        )

    @app.route("/api/mobile/workers/<int:worker_id>/face-registration", methods=["POST"])
    @login_required
    def api_mobile_worker_face_registration(worker_id: int):
        return worker_master_face_registration(worker_id)
