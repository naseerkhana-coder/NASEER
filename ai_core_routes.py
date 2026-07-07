"""Flask routes for MAXEK AI Core Engine (MODULE-019)."""

from __future__ import annotations

from typing import Any, Callable

from flask import jsonify, render_template, request, session

from app.ai import (
    AICoreEngine,
    default_engine_config,
    ensure_ai_core_schema,
    get_default_registry,
    list_ai_execution_logs,
    process_ai_request,
)


def register_ai_core_routes(
    app,
    *,
    login_required: Callable,
    get_db: Callable,
    is_admin_user: Callable,
    is_super_admin_user: Callable | None = None,
) -> None:
    """Register AI Core API and settings stub routes."""

    def _user_id() -> int | None:
        raw = session.get("user_id")
        try:
            return int(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    def _is_super() -> bool:
        if is_super_admin_user:
            return bool(is_super_admin_user())
        return False

    def _session_payload() -> dict[str, Any]:
        return {
            "user_id": _user_id(),
            "username": session.get("username"),
            "role": session.get("role"),
            "company_id": session.get("company_id"),
            "branch_id": session.get("branch_id"),
            "selected_project_id": session.get("selected_project_id"),
            "ai_session_id": session.get("ai_session_id"),
        }

    @app.route("/api/ai", methods=["POST"])
    @login_required
    def api_ai_core_execute():
        db = get_db()
        ensure_ai_core_schema(db)
        body = request.get_json(silent=True) or {}
        body.setdefault("user_id", _user_id())
        body.setdefault("company_id", session.get("company_id"))
        body.setdefault("is_admin", is_admin_user())
        body.setdefault("is_platform_super_admin", _is_super())
        response = process_ai_request(db, body, session_data=_session_payload())
        status_code = 200 if response.success else (403 if response.status == "denied" else 400)
        return jsonify(
            {
                "success": response.success,
                "module_key": response.module_key,
                "request_type": response.request_type,
                "status": response.status,
                "message": response.message,
                "data": response.data,
                "execution_ms": response.execution_ms,
                "error": response.error,
            }
        ), status_code

    @app.route("/api/ai/modules", methods=["GET"])
    @login_required
    def api_ai_core_modules():
        db = get_db()
        ensure_ai_core_schema(db)
        registry = get_default_registry()
        config = default_engine_config()
        return jsonify(
            {
                "modules": registry.list_modules(),
                "config": {
                    "llm_provider": config.llm_provider,
                    "embedding_provider": config.embedding_provider,
                    "model_version": config.model_version,
                    "temperature": config.temperature,
                    "token_limit": config.token_limit,
                    "streaming": config.streaming,
                },
            }
        )

    @app.route("/api/ai/logs", methods=["GET"])
    @login_required
    def api_ai_core_logs():
        if not is_admin_user() and not _is_super():
            return jsonify({"error": "Admin access required"}), 403
        db = get_db()
        ensure_ai_core_schema(db)
        limit = request.args.get("limit", default=25, type=int)
        logs = list_ai_execution_logs(db, user_id=_user_id(), limit=min(limit, 100))
        return jsonify({"items": logs})

    @app.route("/settings/ai-core", methods=["GET"])
    @login_required
    def settings_ai_core_stub():
        db = get_db()
        ensure_ai_core_schema(db)
        registry = get_default_registry()
        config = default_engine_config()
        payload = {
            "title": "AI Core Engine",
            "module": "MODULE-019",
            "status": "interface_ready",
            "providers": {
                "llm": config.llm_provider,
                "embedding": config.embedding_provider,
                "model_version": config.model_version,
            },
            "registered_modules": registry.list_modules(),
            "api_endpoints": {
                "execute": "/api/ai",
                "modules": "/api/ai/modules",
                "logs": "/api/ai/logs",
            },
        }
        if request.accept_mimetypes.best_match(["application/json", "text/html"]) == "application/json":
            return jsonify(payload)
        return render_template(
            "settings.html",
            page_title="AI Core Engine",
            ai_core_stub=payload,
        )
