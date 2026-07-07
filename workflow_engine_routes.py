"""Workflow Engine API routes (MODULE-007) — CRUD, queues, approval, mobile."""

from __future__ import annotations

from typing import Callable

from flask import Response, jsonify, request, send_file, session

from bulk_import_service import parse_upload
from import_audit_service import log_import
from workflow_engine_import_service import (
    save_workflow_import,
    validate_workflow_import,
    workflow_import_template,
)
from workflow_engine_service import (
    activate_workflow_engine,
    ai_workflow_insights,
    deactivate_workflow_engine,
    export_workflows_csv,
    export_workflows_excel,
    get_workflow_engine,
    list_workflow_engine_audit,
    list_workflow_history,
    list_workflow_queue,
    list_workflows_engine,
    process_workflow_escalations,
    save_workflow_engine,
    soft_delete_workflow_engine,
    user_can_workflow_engine,
    workflow_action,
    workflow_engine_dashboard,
    workflow_engine_report,
)
from workflow_service import WORKFLOW_MODES, WORKFLOW_MODE_LABELS


def register_workflow_engine_routes(
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
        if not user_can_workflow_engine(db, _user_id(), action, is_admin=is_admin_user()):
            return jsonify({"error": f"Permission denied: {action}"}), 403
        return None

    @app.route("/api/workflow-engine")
    @login_required
    def api_list_workflows():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        listing = list_workflows_engine(
            db,
            search=request.args.get("q", ""),
            status=request.args.get("status", ""),
            module_id=request.args.get("module_id", ""),
            include_deleted=request.args.get("include_deleted") == "1",
            page=request.args.get("page", 1, type=int),
            per_page=request.args.get("per_page", 25, type=int),
            sort_by=request.args.get("sort_by", "workflow_name"),
            sort_dir=request.args.get("sort_dir", "asc"),
        )
        return jsonify(listing)

    @app.route("/api/workflow-engine/dashboard")
    @login_required
    def api_workflow_engine_dashboard():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify(
            workflow_engine_dashboard(db, _user_id(), is_admin=is_admin_user())
        )

    @app.route("/api/workflow-engine/<int:workflow_id>")
    @login_required
    def api_get_workflow(workflow_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        item = get_workflow_engine(db, workflow_id)
        if not item:
            return jsonify({"error": "Workflow not found"}), 404
        return jsonify(item)

    @app.route("/api/workflow-engine", methods=["POST"])
    @login_required
    def api_create_workflow():
        denied = _require("create")
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or request.form.to_dict(flat=True)
        try:
            wf_id = save_workflow_engine(
                db,
                payload,
                _username(),
                None,
                customer_id=session.get("customer_id"),
            )
            db.commit()
            return jsonify({"ok": True, "workflow_id": wf_id, "item": get_workflow_engine(db, wf_id)})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/workflow-engine/<int:workflow_id>", methods=["PUT", "PATCH", "POST"])
    @login_required
    def api_update_workflow(workflow_id: int):
        denied = _require("edit")
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or request.form.to_dict(flat=True)
        try:
            wf_id = save_workflow_engine(
                db,
                payload,
                _username(),
                workflow_id,
                customer_id=session.get("customer_id"),
            )
            db.commit()
            return jsonify({"ok": True, "workflow_id": wf_id, "item": get_workflow_engine(db, wf_id)})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/workflow-engine/<int:workflow_id>/activate", methods=["POST"])
    @login_required
    def api_activate_workflow(workflow_id: int):
        denied = _require("activate")
        if denied:
            return denied
        db = get_db()
        try:
            activate_workflow_engine(db, workflow_id, _username())
            db.commit()
            return jsonify({"ok": True})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/workflow-engine/<int:workflow_id>/deactivate", methods=["POST"])
    @login_required
    def api_deactivate_workflow(workflow_id: int):
        denied = _require("deactivate")
        if denied:
            return denied
        db = get_db()
        try:
            deactivate_workflow_engine(db, workflow_id, _username())
            db.commit()
            return jsonify({"ok": True})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/workflow-engine/<int:workflow_id>", methods=["DELETE"])
    @login_required
    def api_delete_workflow(workflow_id: int):
        denied = _require("delete")
        if denied:
            return denied
        db = get_db()
        try:
            soft_delete_workflow_engine(db, workflow_id, _username())
            db.commit()
            return jsonify({"ok": True})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/workflow-engine/<int:workflow_id>/audit")
    @login_required
    def api_workflow_audit(workflow_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify({"items": list_workflow_engine_audit(db, workflow_id), "workflow_id": workflow_id})

    @app.route("/api/workflow-engine/queue/<queue_key>")
    @login_required
    def api_workflow_queue(queue_key: str):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify(
            list_workflow_queue(
                db,
                queue_key,
                _user_id(),
                is_admin=is_admin_user(),
                module_id=request.args.get("module_id") or None,
                page=request.args.get("page", 1, type=int),
                per_page=request.args.get("per_page", 25, type=int),
            )
        )

    @app.route("/api/workflow-engine/history")
    @login_required
    def api_workflow_history():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        items = list_workflow_history(
            db,
            module_id=request.args.get("module_id") or None,
            workflow_status=request.args.get("status") or None,
            user_id=request.args.get("user_id", type=int),
            limit=request.args.get("limit", 100, type=int),
            offset=request.args.get("offset", 0, type=int),
        )
        return jsonify({"items": items, "count": len(items)})

    @app.route("/api/workflow-engine/approval/<int:approval_id>/action", methods=["POST"])
    @login_required
    def api_workflow_approval_action(approval_id: int):
        payload = request.get_json(silent=True) or request.form.to_dict(flat=True)
        action = (payload.get("action") or "").strip().lower()
        perm = "approve"
        if action == "reject":
            perm = "reject"
        elif action == "verify":
            perm = "verify"
        elif action in ("return_to_maker", "return"):
            perm = "return"
            action = "return_to_maker"
        elif action == "reopen":
            perm = "edit"
        denied = _require(perm)
        if denied:
            return denied
        db = get_db()
        ok, msg = workflow_action(
            db,
            approval_id,
            _user_id(),
            action,
            payload.get("comments") or payload.get("remarks") or "",
            is_admin=is_admin_user(),
        )
        if ok:
            db.commit()
            return jsonify({"ok": True, "message": msg})
        db.rollback()
        return jsonify({"ok": False, "error": msg}), 400

    @app.route("/api/workflow-engine/reports/<report_key>")
    @login_required
    def api_workflow_report(report_key: str):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        rows = workflow_engine_report(
            db,
            report_key,
            user_id=request.args.get("user_id", type=int) or _user_id(),
            module_id=request.args.get("module_id") or None,
        )
        return jsonify({"report": report_key, "count": len(rows), "items": rows})

    @app.route("/api/workflow-engine/ai/insights")
    @login_required
    def api_workflow_ai_insights():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify(ai_workflow_insights(db))

    @app.route("/api/workflow-engine/escalations/run", methods=["POST"])
    @login_required
    def api_workflow_escalations():
        denied = _require("edit")
        if denied:
            return denied
        db = get_db()
        count = process_workflow_escalations(db)
        db.commit()
        return jsonify({"ok": True, "escalations_sent": count})

    @app.route("/api/workflow-engine/export")
    @login_required
    def api_workflow_export():
        denied = _require("export")
        if denied:
            return denied
        fmt = (request.args.get("format") or "xlsx").lower().strip()
        db = get_db()
        filters = {
            "include_deleted": request.args.get("include_deleted") == "1",
            "status": request.args.get("status") or "",
            "search": request.args.get("q") or "",
        }
        clean = {k: v for k, v in filters.items() if v not in (None, "") or k == "include_deleted"}
        if fmt in ("xlsx", "excel"):
            buf = export_workflows_excel(db, **clean)
            return send_file(
                buf,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name="workflows.xlsx",
            )
        if fmt == "csv":
            csv_text = export_workflows_csv(db, **clean)
            return Response(
                csv_text,
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment; filename=workflows.csv"},
            )
        return jsonify({"error": "Unsupported format. Use xlsx or csv."}), 400

    @app.route("/api/workflow-engine/import/template")
    @login_required
    def api_workflow_import_template():
        denied = _require("import")
        if denied:
            return denied
        buf = workflow_import_template()
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="workflow_engine_template.xlsx",
        )

    @app.route("/api/workflow-engine/import/validate", methods=["POST"])
    @login_required
    def api_workflow_import_validate():
        denied = _require("import")
        if denied:
            return denied
        db = get_db()
        upload = request.files.get("file")
        rows, parse_err = parse_upload(upload)
        if parse_err:
            return jsonify({"ok": False, "errors": [{"row": "—", "column": "File", "error": parse_err}]}), 400
        return jsonify(validate_workflow_import(db, rows))

    @app.route("/api/workflow-engine/import/save", methods=["POST"])
    @login_required
    def api_workflow_import_save():
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
        val = validate_workflow_import(db, rows)
        if not val.get("ok"):
            return jsonify(val), 400
        try:
            result = save_workflow_import(
                db,
                val["parsed_rows"],
                username=_username(),
                filename=(upload.filename if upload else "") or "import.json",
                customer_id=session.get("customer_id"),
            )
            log_import(
                db,
                module_key="workflow_engine",
                imported_by=_username(),
                filename=(upload.filename if upload else "") or "import.json",
                total_rows=len(val["parsed_rows"]),
                success_rows=result.get("imported", 0) + result.get("updated", 0),
                failed_rows=0,
            )
            db.commit()
            return jsonify(result)
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/workflow-engine/meta")
    @login_required
    def api_workflow_meta():
        return jsonify(
            {
                "workflow_modes": WORKFLOW_MODES,
                "workflow_mode_labels": WORKFLOW_MODE_LABELS,
                "stage_types": ["Maker", "Checker", "Approver"],
                "statuses": ["Active", "Inactive"],
                "record_statuses": [
                    "Pending Checker",
                    "Pending Approval",
                    "Approved",
                    "Rejected by Checker",
                    "Rejected by Approver",
                ],
            }
        )

    @app.route("/api/mobile/workflow/pending")
    @login_required
    def api_mobile_workflow_pending():
        db = get_db()
        uid = _user_id()
        if not user_can_workflow_engine(db, uid, "view", is_admin=is_admin_user()):
            return jsonify({"error": "Permission denied"}), 403
        checker = list_workflow_queue(db, "checker", uid, is_admin=is_admin_user(), per_page=50)
        approver = list_workflow_queue(db, "approver", uid, is_admin=is_admin_user(), per_page=50)
        return jsonify(
            {
                "pending_checker": checker["items"],
                "pending_approval": approver["items"],
                "counts": {
                    "checker": checker["total"],
                    "approver": approver["total"],
                },
            }
        )

    @app.route("/api/mobile/workflow/approve/<int:approval_id>", methods=["POST"])
    @login_required
    def api_mobile_workflow_approve(approval_id: int):
        denied = _require("approve")
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or {}
        action = payload.get("action") or "approve"
        ok, msg = workflow_action(
            db,
            approval_id,
            _user_id(),
            action,
            payload.get("comments") or "",
            is_admin=is_admin_user(),
        )
        if ok:
            db.commit()
            return jsonify({"ok": True, "message": msg})
        db.rollback()
        return jsonify({"ok": False, "error": msg}), 400

    @app.route("/api/mobile/workflow/reject/<int:approval_id>", methods=["POST"])
    @login_required
    def api_mobile_workflow_reject(approval_id: int):
        denied = _require("reject")
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or {}
        ok, msg = workflow_action(
            db,
            approval_id,
            _user_id(),
            "reject",
            payload.get("comments") or payload.get("reason") or "",
            is_admin=is_admin_user(),
        )
        if ok:
            db.commit()
            return jsonify({"ok": True, "message": msg})
        db.rollback()
        return jsonify({"ok": False, "error": msg}), 400

    @app.route("/api/mobile/workflow/history")
    @login_required
    def api_mobile_workflow_history():
        db = get_db()
        uid = _user_id()
        if not user_can_workflow_engine(db, uid, "view", is_admin=is_admin_user()):
            return jsonify({"error": "Permission denied"}), 403
        items = list_workflow_history(
            db,
            user_id=uid,
            limit=request.args.get("limit", 50, type=int),
        )
        return jsonify({"items": items, "count": len(items)})
