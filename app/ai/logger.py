"""AI execution audit logger with sanitized context persistence."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any


_SENSITIVE_KEY_PATTERN = re.compile(
    r"(password|secret|token|api_key|authorization|credential)",
    re.IGNORECASE,
)


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_ai_logger_schema(db) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_execution_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            company_id INTEGER,
            session_id TEXT,
            module_key TEXT,
            request_type TEXT,
            prompt_preview TEXT,
            context_json TEXT,
            response_status TEXT NOT NULL,
            success INTEGER NOT NULL DEFAULT 0,
            execution_ms INTEGER DEFAULT 0,
            error_message TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_execution_log_created "
        "ON ai_execution_log(created_at DESC)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_execution_log_user "
        "ON ai_execution_log(user_id, created_at DESC)"
    )
    db.commit()


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if _SENSITIVE_KEY_PATTERN.search(str(key)):
                cleaned[key] = "[REDACTED]"
            else:
                cleaned[key] = _sanitize_value(item)
        return cleaned
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value[:50]]
    if isinstance(value, str) and len(value) > 2000:
        return value[:2000] + "…"
    return value


def sanitize_context(context: dict[str, Any] | None) -> dict[str, Any]:
    if not context:
        return {}
    return _sanitize_value(context)


def log_ai_execution(
    db,
    *,
    user_id: int | None,
    company_id: int | None,
    session_id: str,
    module_key: str,
    request_type: str,
    prompt: str,
    context: dict[str, Any] | None,
    response_status: str,
    success: bool,
    execution_ms: int = 0,
    error_message: str | None = None,
) -> int:
    ensure_ai_logger_schema(db)
    preview = (prompt or "").strip()
    if len(preview) > 500:
        preview = preview[:497] + "..."
    cursor = db.execute(
        """
        INSERT INTO ai_execution_log(
            user_id, company_id, session_id, module_key, request_type,
            prompt_preview, context_json, response_status, success,
            execution_ms, error_message, created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            user_id,
            company_id,
            session_id,
            module_key,
            request_type,
            preview,
            json.dumps(sanitize_context(context), ensure_ascii=False, default=str),
            response_status,
            1 if success else 0,
            execution_ms,
            error_message,
            _now_ts(),
        ),
    )
    db.commit()
    return int(cursor.lastrowid)


def list_ai_execution_logs(
    db,
    *,
    user_id: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    ensure_ai_logger_schema(db)
    if user_id:
        rows = db.execute(
            """
            SELECT id, user_id, company_id, session_id, module_key, request_type,
                   prompt_preview, response_status, success, execution_ms,
                   error_message, created_at
            FROM ai_execution_log
            WHERE user_id=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    else:
        rows = db.execute(
            """
            SELECT id, user_id, company_id, session_id, module_key, request_type,
                   prompt_preview, response_status, success, execution_ms,
                   error_message, created_at
            FROM ai_execution_log
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]
