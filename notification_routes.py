"""Notification Center API routes (MODULE-022)."""

from __future__ import annotations

from typing import Callable

from flask import jsonify, request, session

from notification_service import (
    get_dashboard_metrics,
    get_notification,
    get_unread_count,
    get_user_notification_preferences,
    get_user_notifications,
    mark_all_as_read,
    mark_as_read,
    retry_failed_notification,
    send_notification,
    set_user_notification_preferences,
    user_can_notification_center,
)


def register_notification_routes(
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

    def _require(action: str = "view"):
        db = get_db()
        if not user_can_notification_center(
            db,
            _user_id(),
            action,
            is_admin=is_admin_user(),
            is_platform_super_admin=_is_super(),
        ):
            return jsonify({"error": f"Permission denied: {action}"}), 403
        return None

    def _admin_view_allowed(db) -> bool:
        return user_can_notification_center(
            db,
            _user_id(),
            "admin_view",
            is_admin=is_admin_user(),
            is_platform_super_admin=_is_super(),
        )

    def _session_company_id(db) -> int | None:
        cid = session.get("company_id")
        if cid is not None:
            return int(cid)
        uid = _user_id()
        if not uid:
            return None
        try:
            from notification_service import _user_company_branch

            company_id, _ = _user_company_branch(db, int(uid))
            return company_id
        except Exception:
            return None

    @app.route("/api/v1/notifications", methods=["GET"])
    @login_required
    def api_notifications_list():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        uid = _user_id()
        admin_view = request.args.get("admin_view") == "1" and _admin_view_allowed(db)
        company_id = request.args.get("company_id", type=int)
        if company_id is None and admin_view:
            company_id = _session_company_id(db)
        try:
            result = get_user_notifications(
                db,
                int(uid),
                page=request.args.get("page", 1, type=int),
                per_page=request.args.get("per_page", 20, type=int),
                sort_by=request.args.get("sort_by") or "created_at",
                sort_dir=request.args.get("sort_dir") or "desc",
                unread_only=request.args.get("unread_only") == "1",
                notification_type=request.args.get("notification_type") or "",
                priority=request.args.get("priority") or "",
                status=request.args.get("status") or "",
                module=request.args.get("module") or "",
                channel=request.args.get("channel") or "",
                company_id=company_id,
                admin_view=admin_view,
            )
            return jsonify({"ok": True, **result})
        except (ValueError, PermissionError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/v1/notifications/<int:notification_id>", methods=["GET"])
    @login_required
    def api_notification_detail(notification_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        try:
            item = get_notification(
                db,
                notification_id,
                user_id=_user_id(),
                admin=_admin_view_allowed(db),
            )
            return jsonify({"ok": True, "item": item})
        except PermissionError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 403
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 404

    @app.route("/api/v1/notifications/send", methods=["POST"])
    @login_required
    def api_notifications_send():
        denied = _require("create")
        if denied:
            return denied
        db = get_db()
        data = request.get_json(silent=True) or {}
        data.setdefault("created_by", _username())
        try:
            result = send_notification(db, data)
            db.commit()
            return jsonify(result), 201 if result.get("ok") else 200
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/v1/notifications/<int:notification_id>/read", methods=["POST"])
    @login_required
    def api_notification_mark_read(notification_id: int):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        try:
            result = mark_as_read(db, int(_user_id()), notification_id)
            db.commit()
            return jsonify(result)
        except PermissionError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 403
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 404

    @app.route("/api/v1/notifications/read-all", methods=["POST"])
    @login_required
    def api_notifications_read_all():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        data = request.get_json(silent=True) or {}
        company_id = data.get("company_id")
        if company_id is None:
            company_id = _session_company_id(db)
        result = mark_all_as_read(db, int(_user_id()), company_id=company_id)
        db.commit()
        return jsonify(result)

    @app.route("/api/v1/notifications/unread-count", methods=["GET"])
    @login_required
    def api_notifications_unread_count():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        company_id = request.args.get("company_id", type=int)
        count = get_unread_count(db, int(_user_id()), company_id=company_id)
        return jsonify({"ok": True, "unread_count": count})

    @app.route("/api/v1/notifications/preferences", methods=["GET"])
    @login_required
    def api_notifications_preferences_get():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        company_id = request.args.get("company_id", type=int)
        if company_id is None:
            company_id = _session_company_id(db)
        prefs = get_user_notification_preferences(db, int(_user_id()), company_id=company_id)
        return jsonify({"ok": True, "preferences": prefs})

    @app.route("/api/v1/notifications/preferences", methods=["PUT"])
    @login_required
    def api_notifications_preferences_put():
        denied = _require("edit")
        if denied:
            return denied
        db = get_db()
        data = request.get_json(silent=True) or {}
        if data.get("company_id") is None:
            data["company_id"] = _session_company_id(db)
        try:
            prefs = set_user_notification_preferences(db, int(_user_id()), data, actor=_username())
            db.commit()
            return jsonify({"ok": True, "preferences": prefs})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/v1/notifications/retry", methods=["POST"])
    @login_required
    def api_notifications_retry():
        denied = _require("edit")
        if denied:
            return denied
        db = get_db()
        data = request.get_json(silent=True) or {}
        notification_id = data.get("notification_id") or data.get("id")
        if not notification_id:
            return jsonify({"ok": False, "error": "notification_id is required"}), 400
        try:
            result = retry_failed_notification(db, int(notification_id), actor=_username())
            db.commit()
            return jsonify(result)
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 500

    @app.route("/api/v1/notifications/dashboard", methods=["GET"])
    @login_required
    def api_notifications_dashboard():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        admin_view = request.args.get("admin_view") == "1" and _admin_view_allowed(db)
        company_id = request.args.get("company_id", type=int)
        if company_id is None and admin_view:
            company_id = _session_company_id(db)
        metrics = get_dashboard_metrics(
            db,
            int(_user_id()),
            company_id=company_id,
            admin_view=admin_view,
        )
        return jsonify({"ok": True, "metrics": metrics})
