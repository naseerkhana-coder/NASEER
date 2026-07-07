"""Roles & Permissions API routes — export, import, matrix, assignments, mobile."""

from __future__ import annotations

from typing import Callable

from flask import Response, jsonify, request, send_file, session

from bulk_import_service import parse_upload
from import_audit_service import log_import
from roles_permissions_import_service import save_roles_import, validate_roles_import
from roles_permissions_service import (
    STANDARD_ACTIONS,
    STANDARD_ACTION_LABELS,
    aggregate_user_role_permissions,
    ai_validate_role,
    assign_roles_to_user,
    assign_users_to_role,
    export_roles_csv,
    export_roles_excel,
    export_roles_pdf,
    get_permission_master,
    get_role_master,
    get_role_permission_matrix,
    is_roles_super_administrator,
    list_permission_audit_trail,
    list_permissions_master,
    list_role_audit_trail,
    list_roles_for_user,
    list_roles_master,
    list_users_for_role,
    roles_import_template,
    roles_permissions_report,
    save_permission_master,
    save_role_master,
    save_role_permission_matrix,
    soft_delete_permission_master,
    soft_delete_role_master,
    user_can_roles_permissions,
    user_has_assigned_role_permission,
)


def register_roles_permissions_routes(
    app,
    *,
    login_required: Callable,
    get_db: Callable,
    is_admin_user: Callable,
    is_super_admin_user: Callable | None = None,
) -> None:
    def _user_id() -> int | None:
        return session.get("user_id")

    def _username() -> str:
        return str(session.get("username") or "")

    def _is_super() -> bool:
        if is_super_admin_user:
            return bool(is_super_admin_user())
        return False

    def _require(action: str):
        db = get_db()
        if not user_can_roles_permissions(
            db,
            _user_id(),
            action,
            is_admin=is_admin_user(),
            is_platform_super_admin=_is_super(),
        ):
            return jsonify({"error": f"Permission denied: {action}"}), 403
        return None

    def _require_super():
        db = get_db()
        if not is_roles_super_administrator(db, _user_id(), is_platform_super_admin=_is_super()):
            return jsonify({"error": "Super Administrator access required."}), 403
        return None

    @app.route("/api/roles-permissions/export")
    @login_required
    def roles_permissions_export():
        denied = _require("export")
        if denied:
            return denied
        fmt = (request.args.get("format") or "xlsx").lower().strip()
        db = get_db()
        filters = {
            "include_deleted": request.args.get("include_deleted") == "1",
            "company_id": request.args.get("company_id", type=int),
            "status": request.args.get("status") or "",
        }
        clean_filters = {k: v for k, v in filters.items() if v not in (None, "", False) or k == "include_deleted"}
        report = request.args.get("report", "")
        if report:
            title = report.replace("_", " ").title()
            buf = export_roles_pdf(db, report_title=title, **clean_filters)
            return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name=f"roles_{report}.pdf")
        if fmt in ("xlsx", "excel"):
            buf = export_roles_excel(db, **clean_filters)
            return send_file(
                buf,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name="roles.xlsx",
            )
        if fmt == "csv":
            csv_text = export_roles_csv(db, **clean_filters)
            return Response(
                csv_text,
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment; filename=roles.csv"},
            )
        if fmt == "pdf":
            buf = export_roles_pdf(db, **clean_filters)
            return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name="roles.pdf")
        return jsonify({"error": "Unsupported format. Use xlsx, csv, or pdf."}), 400

    @app.route("/api/roles-permissions/import/template")
    @login_required
    def roles_permissions_import_template():
        denied = _require_super()
        if denied:
            return denied
        buf = roles_import_template()
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="roles_permissions_template.xlsx",
        )

    @app.route("/api/roles-permissions/import/validate", methods=["POST"])
    @login_required
    def roles_permissions_import_validate():
        denied = _require_super()
        if denied:
            return denied
        db = get_db()
        upload = request.files.get("file")
        rows, parse_err = parse_upload(upload)
        if parse_err:
            return jsonify({"ok": False, "errors": [{"row": "—", "column": "File", "error": parse_err}]}), 400
        return jsonify(validate_roles_import(db, rows))

    @app.route("/api/roles-permissions/import/save", methods=["POST"])
    @login_required
    def roles_permissions_import_save():
        denied = _require_super()
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
        val = validate_roles_import(db, rows)
        if not val.get("ok"):
            return jsonify(val), 400
        try:
            result = save_roles_import(
                db,
                val["parsed_rows"],
                username=_username(),
                filename=(upload.filename if upload else "") or "import.json",
                customer_id=session.get("customer_id"),
            )
            log_import(
                db,
                module_key="roles",
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

    @app.route("/api/roles-permissions/roles")
    @login_required
    def api_list_roles():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        listing = list_roles_master(
            db,
            search=request.args.get("q", ""),
            company_id=request.args.get("company_id", type=int),
            status=request.args.get("status", ""),
            include_deleted=request.args.get("include_deleted") == "1",
            page=request.args.get("page", 1, type=int),
            per_page=request.args.get("per_page", 25, type=int),
            sort_by=request.args.get("sort_by", "role_name"),
            sort_dir=request.args.get("sort_dir", "asc"),
            customer_id=session.get("customer_id"),
        )
        return jsonify(listing)

    @app.route("/api/roles-permissions/roles/<int:role_id>")
    @login_required
    def api_get_role(role_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        row = get_role_master(db, role_id, include_deleted=request.args.get("include_deleted") == "1")
        if not row:
            return jsonify({"error": "Role not found"}), 404
        return jsonify(row)

    @app.route("/api/roles-permissions/roles", methods=["POST"])
    @login_required
    def api_create_role():
        denied = _require_super()
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or request.form.to_dict(flat=True)
        try:
            rid = save_role_master(
                db,
                payload,
                _username(),
                customer_id=session.get("customer_id"),
            )
            db.commit()
            return jsonify({"ok": True, "role_id": rid, "role": get_role_master(db, rid)})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/roles-permissions/roles/<int:role_id>", methods=["PUT", "PATCH"])
    @login_required
    def api_update_role(role_id: int):
        denied = _require_super()
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or request.form.to_dict(flat=True)
        try:
            rid = save_role_master(db, payload, _username(), role_id, customer_id=session.get("customer_id"))
            db.commit()
            return jsonify({"ok": True, "role_id": rid, "role": get_role_master(db, rid)})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/roles-permissions/roles/<int:role_id>", methods=["DELETE"])
    @login_required
    def api_delete_role(role_id: int):
        denied = _require_super()
        if denied:
            return denied
        db = get_db()
        try:
            soft_delete_role_master(db, role_id, _username())
            db.commit()
            return jsonify({"ok": True})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/roles-permissions/permissions")
    @login_required
    def api_list_permissions():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        listing = list_permissions_master(
            db,
            search=request.args.get("q", ""),
            module_name=request.args.get("module_name", ""),
            screen_name=request.args.get("screen_name", ""),
            status=request.args.get("status", ""),
            include_deleted=request.args.get("include_deleted") == "1",
            page=request.args.get("page", 1, type=int),
            per_page=request.args.get("per_page", 50, type=int),
        )
        return jsonify(listing)

    @app.route("/api/roles-permissions/permissions", methods=["POST"])
    @login_required
    def api_create_permission():
        denied = _require_super()
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or request.form.to_dict(flat=True)
        try:
            pid = save_permission_master(db, payload, _username())
            db.commit()
            return jsonify({"ok": True, "permission_id": pid, "permission": get_permission_master(db, pid)})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/roles-permissions/permissions/<int:permission_id>", methods=["PUT", "PATCH"])
    @login_required
    def api_update_permission(permission_id: int):
        denied = _require_super()
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or request.form.to_dict(flat=True)
        try:
            pid = save_permission_master(db, payload, _username(), permission_id)
            db.commit()
            return jsonify({"ok": True, "permission_id": pid, "permission": get_permission_master(db, pid)})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/roles-permissions/permissions/<int:permission_id>", methods=["DELETE"])
    @login_required
    def api_delete_permission(permission_id: int):
        denied = _require_super()
        if denied:
            return denied
        db = get_db()
        try:
            soft_delete_permission_master(db, permission_id, _username())
            db.commit()
            return jsonify({"ok": True})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/roles-permissions/roles/<int:role_id>/matrix")
    @login_required
    def api_role_matrix(role_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify(
            {
                "role_id": role_id,
                "items": get_role_permission_matrix(db, role_id),
                "standard_actions": STANDARD_ACTIONS,
                "action_labels": STANDARD_ACTION_LABELS,
            }
        )

    @app.route("/api/roles-permissions/roles/<int:role_id>/matrix", methods=["POST"])
    @login_required
    def api_save_role_matrix(role_id: int):
        denied = _require_super()
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or {}
        assignments = payload.get("assignments") or payload.get("items") or []
        try:
            saved = save_role_permission_matrix(db, role_id, assignments, _username())
            db.commit()
            return jsonify({"ok": True, "saved": saved})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/roles-permissions/roles/<int:role_id>/users")
    @login_required
    def api_role_users(role_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify({"role_id": role_id, "items": list_users_for_role(db, role_id)})

    @app.route("/api/roles-permissions/roles/<int:role_id>/users", methods=["POST"])
    @login_required
    def api_assign_role_users(role_id: int):
        denied = _require_super()
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or {}
        user_ids = payload.get("user_ids") or []
        try:
            result = assign_users_to_role(db, role_id, user_ids, _username())
            db.commit()
            return jsonify({"ok": True, **result})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/roles-permissions/users/<int:user_id>/roles")
    @login_required
    def api_user_roles(user_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify(
            {
                "user_id": user_id,
                "items": list_roles_for_user(db, user_id),
                "permissions": aggregate_user_role_permissions(db, user_id),
            }
        )

    @app.route("/api/roles-permissions/users/<int:user_id>/roles", methods=["POST"])
    @login_required
    def api_assign_user_roles(user_id: int):
        denied = _require_super()
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or {}
        role_ids = payload.get("role_ids") or []
        try:
            result = assign_roles_to_user(db, user_id, role_ids, _username())
            db.commit()
            return jsonify({"ok": True, **result})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/roles-permissions/roles/<int:role_id>/audit")
    @login_required
    def roles_permissions_role_audit(role_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify({"items": list_role_audit_trail(db, role_id), "role_id": role_id})

    @app.route("/api/roles-permissions/permissions/<int:permission_id>/audit")
    @login_required
    def roles_permissions_permission_audit(permission_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify({"items": list_permission_audit_trail(db, permission_id), "permission_id": permission_id})

    @app.route("/api/roles-permissions/reports/<report_key>")
    @login_required
    def roles_permissions_report_route(report_key: str):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        rows = roles_permissions_report(
            db,
            report_key,
            company_id=request.args.get("company_id", type=int),
        )
        return jsonify({"report": report_key, "count": len(rows), "items": rows})

    @app.route("/api/roles-permissions/ai/validate", methods=["POST"])
    @login_required
    def roles_permissions_ai_validate():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or {}
        role_id = payload.get("role_id") or request.form.get("role_id", type=int)
        form = payload.get("form") or request.form.to_dict(flat=True)
        return jsonify(ai_validate_role(db, role_id=role_id, form=form or None))

    @app.route("/api/mobile/permissions/validate", methods=["POST"])
    @login_required
    def api_mobile_validate_permission():
        db = get_db()
        payload = request.get_json(silent=True) or {}
        module_name = (payload.get("module_name") or "").strip()
        screen_name = (payload.get("screen_name") or "").strip()
        menu_name = (payload.get("menu_name") or "").strip()
        field_name = (payload.get("field_name") or "").strip()
        action = (payload.get("action") or "view").strip().lower()
        allowed = user_has_assigned_role_permission(
            db,
            _user_id(),
            module_name=module_name,
            screen_name=screen_name,
            menu_name=menu_name,
            field_name=field_name,
            action=action,
            is_platform_super_admin=_is_super(),
        )
        if allowed is None:
            allowed = user_can_roles_permissions(
                db,
                _user_id(),
                action if action in ("view", "create", "edit", "delete", "export") else "view",
                is_admin=is_admin_user(),
                is_platform_super_admin=_is_super(),
            )
        return jsonify(
            {
                "allowed": bool(allowed),
                "module_name": module_name,
                "screen_name": screen_name,
                "action": action,
            }
        )

    @app.route("/api/mobile/users/<int:user_id>/permissions", methods=["GET"])
    @login_required
    def api_mobile_user_permissions(user_id: int):
        db = get_db()
        if not user_can_roles_permissions(
            db,
            _user_id(),
            "view",
            is_admin=is_admin_user(),
            is_platform_super_admin=_is_super(),
        ):
            return jsonify({"error": "Permission denied"}), 403
        return jsonify(
            {
                "user_id": user_id,
                "roles": list_roles_for_user(db, user_id),
                "permissions": aggregate_user_role_permissions(db, user_id),
            }
        )
