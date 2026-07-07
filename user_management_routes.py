"""User Management API routes — export, import, audit, reports, AI, mobile."""

from __future__ import annotations

import os
import uuid
from typing import Callable

from flask import Response, jsonify, request, send_file, session

from bulk_import_service import parse_upload
from import_audit_service import log_import
from user_import_service import save_user_import, validate_user_import
from user_management_service import (
    PROFILE_PHOTO_EXTENSIONS,
    USER_STATUSES,
    USER_SYSTEM_ROLES,
    USER_WORKFLOW_ROLES,
    activate_user_master,
    ai_validate_user,
    deactivate_user_master,
    export_users_csv,
    export_users_excel,
    export_users_pdf,
    get_user_master,
    list_user_audit_trail,
    list_users_master,
    lock_user_master,
    reset_user_password,
    save_user_master,
    save_user_profile_photo,
    soft_delete_user_master,
    unlock_user_master,
    user_can_user_management,
    user_import_template,
    user_profile_photo_dir,
    user_report,
    verify_user_password,
)


def register_user_management_routes(
    app,
    *,
    login_required: Callable,
    get_db: Callable,
    is_admin_user: Callable,
    is_customer_admin_user: Callable | None = None,
    assert_user_limit_fn: Callable | None = None,
    base_dir: str = "",
) -> None:
    def _user_id() -> int | None:
        return session.get("user_id")

    def _username() -> str:
        return str(session.get("username") or "")

    def _is_customer_admin() -> bool:
        if is_customer_admin_user:
            return bool(is_customer_admin_user())
        return False

    def _require(action: str):
        db = get_db()
        if not user_can_user_management(
            db,
            _user_id(),
            action,
            is_admin=is_admin_user(),
            is_customer_admin=_is_customer_admin(),
        ):
            return jsonify({"error": f"Permission denied: {action}"}), 403
        return None

    @app.route("/api/user-management/list")
    @login_required
    def user_management_list_api():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        listing = list_users_master(
            db,
            search=request.args.get("q") or "",
            company_id=request.args.get("company_id", type=int),
            branch_id=request.args.get("branch_id", type=int),
            department_id=request.args.get("department_id", type=int),
            status=request.args.get("status") or "",
            locked=request.args.get("locked") or "",
            customer_id=session.get("customer_id"),
            include_deleted=request.args.get("include_deleted") == "1",
            page=request.args.get("page", 1, type=int),
            per_page=request.args.get("per_page", 25, type=int),
            sort_by=request.args.get("sort_by") or "username",
            sort_dir=request.args.get("sort_dir") or "asc",
        )
        return jsonify(listing)

    @app.route("/api/user-management/<int:user_id>")
    @login_required
    def user_management_get_api(user_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        row = get_user_master(db, user_id, include_deleted=request.args.get("include_deleted") == "1")
        if not row:
            return jsonify({"error": "User not found"}), 404
        safe = dict(row)
        safe.pop("password", None)
        return jsonify(safe)

    @app.route("/api/user-management/save", methods=["POST"])
    @login_required
    def user_management_save_api():
        action = "edit" if request.form.get("user_id") else "create"
        denied = _require(action)
        if denied:
            return denied
        db = get_db()
        user_id = request.form.get("user_id", type=int)
        password = request.form.get("password") or None
        if user_id and not password:
            password = None
        try:
            uid = save_user_master(
                db,
                request.form,
                _username(),
                user_id=user_id,
                customer_id=session.get("customer_id"),
                password=password,
                assert_user_limit_fn=assert_user_limit_fn,
            )
            db.commit()
            return jsonify({"ok": True, "user_id": uid})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/user-management/<int:user_id>/delete", methods=["POST"])
    @login_required
    def user_management_delete_api(user_id: int):
        denied = _require("delete")
        if denied:
            return denied
        db = get_db()
        try:
            soft_delete_user_master(db, user_id, _username())
            db.commit()
            return jsonify({"ok": True})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/user-management/<int:user_id>/activate", methods=["POST"])
    @login_required
    def user_management_activate_api(user_id: int):
        denied = _require("activate")
        if denied:
            return denied
        db = get_db()
        activate_user_master(db, user_id, _username())
        db.commit()
        return jsonify({"ok": True})

    @app.route("/api/user-management/<int:user_id>/deactivate", methods=["POST"])
    @login_required
    def user_management_deactivate_api(user_id: int):
        denied = _require("deactivate")
        if denied:
            return denied
        db = get_db()
        deactivate_user_master(db, user_id, _username())
        db.commit()
        return jsonify({"ok": True})

    @app.route("/api/user-management/<int:user_id>/lock", methods=["POST"])
    @login_required
    def user_management_lock_api(user_id: int):
        denied = _require("lock")
        if denied:
            return denied
        db = get_db()
        reason = (request.get_json(silent=True) or {}).get("reason") or request.form.get("reason") or ""
        lock_user_master(db, user_id, _username(), reason=reason)
        db.commit()
        return jsonify({"ok": True})

    @app.route("/api/user-management/<int:user_id>/unlock", methods=["POST"])
    @login_required
    def user_management_unlock_api(user_id: int):
        denied = _require("unlock")
        if denied:
            return denied
        db = get_db()
        unlock_user_master(db, user_id, _username())
        db.commit()
        return jsonify({"ok": True})

    @app.route("/api/user-management/<int:user_id>/reset-password", methods=["POST"])
    @login_required
    def user_management_reset_password_api(user_id: int):
        denied = _require("reset_password")
        if denied:
            return denied
        payload = request.get_json(silent=True) or request.form.to_dict(flat=True)
        new_password = payload.get("new_password") or payload.get("password")
        if not new_password:
            return jsonify({"ok": False, "error": "New password is required."}), 400
        db = get_db()
        try:
            reset_user_password(db, user_id, new_password, _username())
            db.commit()
            return jsonify({"ok": True})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/user-management/<int:user_id>/photo", methods=["POST"])
    @login_required
    def user_management_photo_api(user_id: int):
        denied = _require("edit")
        if denied:
            return denied
        upload = request.files.get("photo") or request.files.get("file")
        if not upload or not upload.filename:
            return jsonify({"ok": False, "error": "Photo file is required."}), 400
        ext = os.path.splitext(upload.filename)[1].lower()
        if ext not in PROFILE_PHOTO_EXTENSIONS:
            return jsonify({"ok": False, "error": "Use JPG, PNG, or WEBP."}), 400
        photo_dir = user_profile_photo_dir(base_dir or app.root_path)
        fname = f"user_{user_id}_{uuid.uuid4().hex[:8]}{ext}"
        upload.save(os.path.join(photo_dir, fname))
        rel = f"uploads/users/profiles/{fname}"
        db = get_db()
        save_user_profile_photo(db, user_id, rel, _username())
        db.commit()
        return jsonify({"ok": True, "profile_photo": rel})

    @app.route("/api/user-management/export")
    @login_required
    def user_management_export():
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
            "status": request.args.get("status") or "",
            "locked": request.args.get("locked") or "",
            "customer_id": session.get("customer_id"),
        }
        clean_filters = {k: v for k, v in filters.items() if v not in (None, "", False) or k == "include_deleted"}
        report = request.args.get("report", "")
        if report:
            title = report.replace("_", " ").title()
            buf = export_users_pdf(db, report_title=title, **clean_filters)
            return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name=f"users_{report}.pdf")
        if fmt in ("xlsx", "excel"):
            buf = export_users_excel(db, **clean_filters)
            return send_file(
                buf,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name="users.xlsx",
            )
        if fmt == "csv":
            csv_text = export_users_csv(db, **clean_filters)
            return Response(
                csv_text,
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment; filename=users.csv"},
            )
        if fmt == "pdf":
            buf = export_users_pdf(db, **clean_filters)
            return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name="users.pdf")
        return jsonify({"error": "Unsupported format. Use xlsx, csv, or pdf."}), 400

    @app.route("/api/user-management/import/template")
    @login_required
    def user_management_import_template():
        denied = _require("import")
        if denied:
            return denied
        buf = user_import_template()
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="user_management_template.xlsx",
        )

    @app.route("/api/user-management/import/validate", methods=["POST"])
    @login_required
    def user_management_import_validate():
        denied = _require("import")
        if denied:
            return denied
        db = get_db()
        upload = request.files.get("file")
        rows, parse_err = parse_upload(upload)
        if parse_err:
            return jsonify({"ok": False, "errors": [{"row": "—", "column": "File", "error": parse_err}]}), 400
        return jsonify(validate_user_import(db, rows))

    @app.route("/api/user-management/import/save", methods=["POST"])
    @login_required
    def user_management_import_save():
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
        val = validate_user_import(db, rows)
        if not val.get("ok"):
            return jsonify(val), 400
        try:
            result = save_user_import(
                db,
                val["parsed_rows"],
                username=_username(),
                filename=(upload.filename if upload else "") or "import.json",
                customer_id=session.get("customer_id"),
                assert_user_limit_fn=assert_user_limit_fn,
            )
            log_import(
                db,
                module_key="users",
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

    @app.route("/api/user-management/<int:user_id>/audit")
    @login_required
    def user_management_audit(user_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        return jsonify({"items": list_user_audit_trail(db, user_id), "user_id": user_id})

    @app.route("/api/user-management/reports/<report_key>")
    @login_required
    def user_management_report_route(report_key: str):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        rows = user_report(
            db,
            report_key,
            company_id=request.args.get("company_id", type=int),
            branch_id=request.args.get("branch_id", type=int),
            department_id=request.args.get("department_id", type=int),
            customer_id=session.get("customer_id"),
        )
        return jsonify({"report": report_key, "count": len(rows), "items": rows})

    @app.route("/api/user-management/ai/validate", methods=["POST"])
    @login_required
    def user_management_ai_validate():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        payload = request.get_json(silent=True) or {}
        user_id = payload.get("user_id") or request.form.get("user_id", type=int)
        form = payload.get("form") or request.form.to_dict(flat=True)
        return jsonify(ai_validate_user(db, user_id=user_id, form=form or None))

    @app.route("/api/mobile/users", methods=["GET"])
    @login_required
    def api_mobile_list_users():
        db = get_db()
        if not user_can_user_management(
            db,
            _user_id(),
            "view",
            is_admin=is_admin_user(),
            is_customer_admin=_is_customer_admin(),
        ):
            return jsonify({"error": "Permission denied"}), 403
        listing = list_users_master(
            db,
            status="Active",
            customer_id=session.get("customer_id"),
            per_page=500,
        )
        items = [
            {
                "id": u["id"],
                "username": u.get("username"),
                "display_name": u.get("display_name"),
                "email": u.get("email"),
                "mobile": u.get("mobile"),
                "role": u.get("role"),
                "company_code": u.get("company_code"),
                "branch_name": u.get("branch_name"),
                "department_name": u.get("department_name"),
            }
            for u in listing["items"]
        ]
        return jsonify({"items": items, "count": len(items)})

    @app.route("/api/mobile/users/<int:user_id>", methods=["GET"])
    @login_required
    def api_mobile_get_user(user_id: int):
        db = get_db()
        row = get_user_master(db, user_id)
        if not row:
            return jsonify({"error": "User not found"}), 404
        if int(_user_id() or 0) != user_id and not user_can_user_management(
            db,
            _user_id(),
            "view",
            is_admin=is_admin_user(),
            is_customer_admin=_is_customer_admin(),
        ):
            return jsonify({"error": "Permission denied"}), 403
        safe = dict(row)
        safe.pop("password", None)
        return jsonify(safe)

    @app.route("/api/mobile/profile", methods=["GET"])
    @login_required
    def api_mobile_profile():
        db = get_db()
        uid = _user_id()
        if not uid:
            return jsonify({"error": "Not authenticated"}), 401
        row = get_user_master(db, uid)
        if not row:
            return jsonify({"error": "User not found"}), 404
        safe = dict(row)
        safe.pop("password", None)
        return jsonify(safe)

    @app.route("/api/mobile/profile/password", methods=["POST"])
    @login_required
    def api_mobile_change_password():
        db = get_db()
        uid = _user_id()
        payload = request.get_json(silent=True) or request.form.to_dict(flat=True)
        current = payload.get("current_password") or ""
        new_password = payload.get("new_password") or ""
        row = db.execute("SELECT password FROM users WHERE id=?", (uid,)).fetchone()
        if not row or not verify_user_password(row[0], current):
            return jsonify({"ok": False, "error": "Current password is incorrect."}), 400
        try:
            reset_user_password(db, uid, new_password, _username(), notify=False)
            db.commit()
            return jsonify({"ok": True})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/mobile/profile/photo", methods=["POST"])
    @login_required
    def api_mobile_profile_photo():
        uid = _user_id()
        if not uid:
            return jsonify({"error": "Not authenticated"}), 401
        return user_management_photo_api(uid)
