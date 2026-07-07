"""Enterprise Dashboard API routes (MODULE-008)."""

from __future__ import annotations

from typing import Callable

from flask import jsonify, request, session

from enterprise_dashboard_service import (
    DASHBOARD_PERMISSION_ENDPOINT,
    ai_dashboard_insights,
    build_user_scope,
    dashboard_report,
    get_dashboard_layout,
    get_recent_activities,
    get_widget_data,
    list_available_widgets,
    mobile_dashboard_payload,
    reset_dashboard_layout,
    save_dashboard_layout,
    save_widget_preferences,
    user_can_enterprise_dashboard,
)


def register_enterprise_dashboard_routes(
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

    def _scope(db):
        return build_user_scope(db, _user_id(), dict(session))

    def _require(action: str = "view"):
        db = get_db()
        if not user_can_enterprise_dashboard(
            db,
            _user_id(),
            action,
            is_admin=is_admin_user(),
            is_platform_super_admin=_is_super(),
        ):
            return jsonify({"error": f"Permission denied: {action}"}), 403
        return None

    @app.route("/api/dashboard/layout", methods=["GET"])
    @login_required
    def api_dashboard_layout_get():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        scope = _scope(db)
        role_id = request.args.get("role_id", type=int)
        department_id = request.args.get("department_id", type=int)
        payload = get_dashboard_layout(
            db,
            _user_id(),
            scope,
            role_id=role_id,
            department_id=department_id,
        )
        return jsonify(payload)

    @app.route("/api/dashboard/layout", methods=["POST"])
    @login_required
    def api_dashboard_layout_save():
        denied = _require("configure")
        if denied:
            return denied
        db = get_db()
        data = request.get_json(silent=True) or {}
        layout = data.get("layout") or data
        scope_type = (data.get("scope_type") or "user").strip().lower()
        try:
            result = save_dashboard_layout(
                db,
                int(_user_id()),
                layout,
                _username(),
                role_id=data.get("role_id"),
                department_id=data.get("department_id"),
                layout_name=data.get("layout_name") or "default",
                scope_type=scope_type,
            )
            db.commit()
            return jsonify(result)
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/dashboard/layout/reset", methods=["POST"])
    @login_required
    def api_dashboard_layout_reset():
        denied = _require("reset")
        if denied:
            return denied
        db = get_db()
        data = request.get_json(silent=True) or {}
        scope_type = (data.get("scope_type") or "user").strip().lower()
        scope = _scope(db)
        result = reset_dashboard_layout(
            db,
            int(_user_id()),
            _username(),
            role_id=data.get("role_id"),
            department_id=data.get("department_id"),
            scope_type=scope_type,
        )
        db.commit()
        return jsonify(result)

    @app.route("/api/dashboard/widgets")
    @login_required
    def api_dashboard_widgets():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        scope = _scope(db)
        return jsonify(
            {
                "widgets": list_available_widgets(db, scope),
                "permissions": {
                    "view": True,
                    "configure": user_can_enterprise_dashboard(
                        db, _user_id(), "configure", is_admin=is_admin_user(), is_platform_super_admin=_is_super()
                    ),
                    "reset": user_can_enterprise_dashboard(
                        db, _user_id(), "reset", is_admin=is_admin_user(), is_platform_super_admin=_is_super()
                    ),
                    "manage_widgets": user_can_enterprise_dashboard(
                        db,
                        _user_id(),
                        "manage_widgets",
                        is_admin=is_admin_user(),
                        is_platform_super_admin=_is_super(),
                    ),
                },
            }
        )

    @app.route("/api/dashboard/widgets/<widget_key>/data")
    @login_required
    def api_dashboard_widget_data(widget_key: str):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        scope = _scope(db)
        return jsonify(get_widget_data(db, widget_key, scope))

    @app.route("/api/dashboard/preferences", methods=["GET", "POST"])
    @login_required
    def api_dashboard_preferences():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        if request.method == "GET":
            from enterprise_dashboard_service import load_widget_preferences

            return jsonify(load_widget_preferences(db, _user_id()))
        denied = _require("configure")
        if denied:
            return denied
        data = request.get_json(silent=True) or {}
        try:
            prefs = save_widget_preferences(db, int(_user_id()), data, _username())
            db.commit()
            return jsonify({"ok": True, "preferences": prefs})
        except ValueError as exc:
            db.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/dashboard/recent-activities")
    @login_required
    def api_dashboard_recent_activities():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        limit = request.args.get("limit", 20, type=int)
        return jsonify({"items": get_recent_activities(db, _user_id(), limit=limit)})

    @app.route("/api/dashboard/ai/insights")
    @login_required
    def api_dashboard_ai_insights():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        scope = _scope(db)
        return jsonify(ai_dashboard_insights(db, scope))

    @app.route("/api/dashboard/reports/<report_key>")
    @login_required
    def api_dashboard_report(report_key: str):
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        scope = _scope(db)
        return jsonify(dashboard_report(db, report_key, scope))

    @app.route("/api/mobile/dashboard")
    @login_required
    def api_mobile_dashboard():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        scope = _scope(db)
        return jsonify(mobile_dashboard_payload(db, _user_id(), scope))

    @app.route("/api/mobile/dashboard/widgets")
    @login_required
    def api_mobile_dashboard_widgets():
        denied = _require("view")
        if denied:
            return denied
        db = get_db()
        scope = _scope(db)
        widgets = list_available_widgets(db, scope)
        return jsonify({"widgets": widgets[:12]})

    @app.route("/enterprise-dashboard")
    @login_required
    def enterprise_dashboard_page():
        from flask import render_template

        db = get_db()
        if not user_can_enterprise_dashboard(
            db, _user_id(), "view", is_admin=is_admin_user(), is_platform_super_admin=_is_super()
        ):
            return jsonify({"error": "Permission denied: view"}), 403
        perms = {
            "view": True,
            "configure": user_can_enterprise_dashboard(
                db, _user_id(), "configure", is_admin=is_admin_user(), is_platform_super_admin=_is_super()
            ),
            "reset": user_can_enterprise_dashboard(
                db, _user_id(), "reset", is_admin=is_admin_user(), is_platform_super_admin=_is_super()
            ),
            "manage_widgets": user_can_enterprise_dashboard(
                db,
                _user_id(),
                "manage_widgets",
                is_admin=is_admin_user(),
                is_platform_super_admin=_is_super(),
            ),
        }
        return render_template(
            "enterprise_dashboard.html",
            dashboard_permissions=perms,
            dashboard_endpoint=DASHBOARD_PERMISSION_ENDPOINT,
        )
