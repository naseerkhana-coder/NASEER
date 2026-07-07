"""AI memory manager — conversation, ERP, session, and user preference storage."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _table_exists(db, table: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def ensure_ai_memory_schema(db) -> None:
    """Idempotent bootstrap for AI memory tables."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_conversation_memory(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            user_id INTEGER,
            company_id INTEGER,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            module_key TEXT,
            request_type TEXT,
            metadata_json TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_conversation_session "
        "ON ai_conversation_memory(session_id, created_at)"
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_erp_memory(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_key TEXT NOT NULL,
            company_id INTEGER,
            user_id INTEGER,
            memory_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(memory_key, company_id, user_id, memory_type)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_session_memory(
            session_id TEXT PRIMARY KEY,
            user_id INTEGER,
            company_id INTEGER,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_user_preferences(
            user_id INTEGER PRIMARY KEY,
            preferred_module TEXT,
            temperature REAL,
            token_limit INTEGER,
            streaming INTEGER DEFAULT 0,
            extra_json TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )
    db.commit()


def ensure_ai_core_schema(db) -> None:
    """Bootstrap all AI Core persistence tables (memory + logger)."""
    ensure_ai_memory_schema(db)
    from app.ai.logger import ensure_ai_logger_schema

    ensure_ai_logger_schema(db)


class MemoryManager:
    """Manage conversation, ERP, session memory, and user AI preferences."""

    def __init__(self, db) -> None:
        self.db = db
        ensure_ai_memory_schema(db)

    def append_conversation(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        user_id: int | None = None,
        company_id: int | None = None,
        module_key: str = "",
        request_type: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> int:
        now = _now_ts()
        cursor = self.db.execute(
            """
            INSERT INTO ai_conversation_memory(
                session_id, user_id, company_id, role, content,
                module_key, request_type, metadata_json, created_at
            ) VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (
                session_id,
                user_id,
                company_id,
                role,
                content,
                module_key,
                request_type,
                json.dumps(metadata or {}),
                now,
            ),
        )
        self.db.commit()
        return int(cursor.lastrowid)

    def get_conversation(
        self,
        session_id: str,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        rows = self.db.execute(
            """
            SELECT * FROM ai_conversation_memory
            WHERE session_id=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
        items = [dict(row) for row in reversed(rows)]
        for item in items:
            raw = item.pop("metadata_json", None)
            item["metadata"] = json.loads(raw) if raw else {}
        return items

    def set_erp_memory(
        self,
        memory_key: str,
        payload: dict[str, Any],
        *,
        company_id: int | None = None,
        user_id: int | None = None,
        memory_type: str = "fact",
    ) -> None:
        now = _now_ts()
        self.db.execute(
            """
            INSERT INTO ai_erp_memory(
                memory_key, company_id, user_id, memory_type, payload_json, updated_at
            ) VALUES(?,?,?,?,?,?)
            ON CONFLICT(memory_key, company_id, user_id, memory_type) DO UPDATE SET
                payload_json=excluded.payload_json,
                updated_at=excluded.updated_at
            """,
            (
                memory_key,
                company_id,
                user_id,
                memory_type,
                json.dumps(payload),
                now,
            ),
        )
        self.db.commit()

    def get_erp_memory(
        self,
        memory_key: str,
        *,
        company_id: int | None = None,
        user_id: int | None = None,
        memory_type: str = "fact",
    ) -> dict[str, Any] | None:
        row = self.db.execute(
            """
            SELECT payload_json FROM ai_erp_memory
            WHERE memory_key=? AND company_id IS ? AND user_id IS ? AND memory_type=?
            """,
            (memory_key, company_id, user_id, memory_type),
        ).fetchone()
        if not row:
            return None
        raw = row["payload_json"] if hasattr(row, "keys") else row[0]
        return json.loads(raw) if raw else None

    def set_session_memory(
        self,
        session_id: str,
        payload: dict[str, Any],
        *,
        user_id: int | None = None,
        company_id: int | None = None,
    ) -> None:
        now = _now_ts()
        self.db.execute(
            """
            INSERT INTO ai_session_memory(session_id, user_id, company_id, payload_json, updated_at)
            VALUES(?,?,?,?,?)
            ON CONFLICT(session_id) DO UPDATE SET
                user_id=excluded.user_id,
                company_id=excluded.company_id,
                payload_json=excluded.payload_json,
                updated_at=excluded.updated_at
            """,
            (session_id, user_id, company_id, json.dumps(payload), now),
        )
        self.db.commit()

    def get_session_memory(self, session_id: str) -> dict[str, Any]:
        row = self.db.execute(
            "SELECT payload_json FROM ai_session_memory WHERE session_id=?",
            (session_id,),
        ).fetchone()
        if not row:
            return {}
        raw = row["payload_json"] if hasattr(row, "keys") else row[0]
        return json.loads(raw) if raw else {}

    def save_user_preferences(
        self,
        user_id: int,
        *,
        preferred_module: str | None = None,
        temperature: float | None = None,
        token_limit: int | None = None,
        streaming: bool | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        existing = self.get_user_preferences(user_id)
        payload = {
            "preferred_module": preferred_module if preferred_module is not None else existing.get("preferred_module"),
            "temperature": temperature if temperature is not None else existing.get("temperature", 0.4),
            "token_limit": token_limit if token_limit is not None else existing.get("token_limit", 4096),
            "streaming": int(streaming) if streaming is not None else int(existing.get("streaming", 0)),
            "extra_json": json.dumps(extra if extra is not None else existing.get("extra", {})),
            "updated_at": _now_ts(),
        }
        self.db.execute(
            """
            INSERT INTO ai_user_preferences(
                user_id, preferred_module, temperature, token_limit, streaming, extra_json, updated_at
            ) VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
                preferred_module=excluded.preferred_module,
                temperature=excluded.temperature,
                token_limit=excluded.token_limit,
                streaming=excluded.streaming,
                extra_json=excluded.extra_json,
                updated_at=excluded.updated_at
            """,
            (
                user_id,
                payload["preferred_module"],
                payload["temperature"],
                payload["token_limit"],
                payload["streaming"],
                payload["extra_json"],
                payload["updated_at"],
            ),
        )
        self.db.commit()
        return self.get_user_preferences(user_id)

    def get_user_preferences(self, user_id: int) -> dict[str, Any]:
        row = self.db.execute(
            "SELECT * FROM ai_user_preferences WHERE user_id=?",
            (user_id,),
        ).fetchone()
        if not row:
            return {
                "user_id": user_id,
                "preferred_module": None,
                "temperature": 0.4,
                "token_limit": 4096,
                "streaming": False,
                "extra": {},
            }
        data = dict(row)
        extra_raw = data.pop("extra_json", None)
        data["extra"] = json.loads(extra_raw) if extra_raw else {}
        data["streaming"] = bool(data.get("streaming"))
        return data

    def build_memory_snapshot(
        self,
        *,
        session_id: str,
        user_id: int | None = None,
        company_id: int | None = None,
    ) -> dict[str, Any]:
        return {
            "conversation": self.get_conversation(session_id, limit=10) if session_id else [],
            "session": self.get_session_memory(session_id) if session_id else {},
            "preferences": self.get_user_preferences(user_id) if user_id else {},
            "erp_facts": self._list_erp_facts(user_id=user_id, company_id=company_id, limit=10),
        }

    def _list_erp_facts(
        self,
        *,
        user_id: int | None,
        company_id: int | None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        if not _table_exists(self.db, "ai_erp_memory"):
            return []
        rows = self.db.execute(
            """
            SELECT memory_key, memory_type, payload_json, updated_at
            FROM ai_erp_memory
            WHERE (user_id IS ? OR user_id IS NULL)
              AND (company_id IS ? OR company_id IS NULL)
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (user_id, company_id, limit),
        ).fetchall()
        facts = []
        for row in rows:
            item = dict(row)
            raw = item.pop("payload_json", None)
            item["payload"] = json.loads(raw) if raw else {}
            facts.append(item)
        return facts
