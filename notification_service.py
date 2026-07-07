"""Enterprise Notification & Alert System (MODULE-022).

Centralized notification service for MAXEK ERP. Business modules should call
``notify_user()`` or ``send_notification()`` only — channel routing, preferences,
scheduling, and delivery logging are handled here.

AI preparation (future MODULE-019+):
- ``ai_metadata`` JSON: smart prioritization hints, summary drafts, model version.
- ``risk_score`` REAL: predictive alert severity (0.0–1.0).
- ``behavior_tags`` JSON: engagement / dismissal patterns for ML pipelines.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, time
from typing import Any

from company_master_service import _ensure_column, _now_ts, _table_exists

NOTIFICATION_PERMISSION_ENDPOINT = "notification_center"
NOTIFICATION_MODULE_NAME = "Settings"

NOTIFICATION_TYPES = (
    "Approval Pending",
    "Approval Approved",
    "Approval Rejected",
    "Task Assigned",
    "Task Completed",
    "Task Overdue",
    "Attendance Issue",
    "Payroll Generated",
    "Invoice Created",
    "Payment Received",
    "Payment Overdue",
    "Stock Low",
    "Material Shortage",
    "Purchase Order Approved",
    "Work Order Assigned",
    "Site Issue Reported",
    "Security Alert",
    "System Error",
    "Custom Notification",
)

NOTIFICATION_PRIORITIES = ("Low", "Normal", "High", "Critical")
NOTIFICATION_CHANNELS = ("in_app", "email", "sms")
NOTIFICATION_STATUSES = ("Pending", "Scheduled", "Sent", "Failed", "Cancelled")
READ_STATUSES = ("unread", "read")

NOTIFICATION_SORT_COLUMNS = (
    "created_at",
    "priority",
    "notification_type",
    "status",
    "channel",
    "title",
    "scheduled_at",
    "sent_at",
)

DEFAULT_MODULE_PREFERENCES = {
    "approvals": True,
    "tasks": True,
    "hr": True,
    "finance": True,
    "inventory": True,
    "projects": True,
    "security": True,
    "system": True,
}

DEFAULT_PRIORITY_PREFERENCES = {
    "Low": True,
    "Normal": True,
    "High": True,
    "Critical": True,
}

DEFAULT_TEMPLATES: tuple[dict[str, str], ...] = (
    {
        "template_code": "APPROVAL_PENDING",
        "template_name": "Approval Pending",
        "notification_type": "Approval Pending",
        "module": "approvals",
        "channel": "in_app",
        "subject_template": "Approval required: {{title}}",
        "body_template": "{{message}}",
        "priority": "High",
    },
    {
        "template_code": "TASK_ASSIGNED",
        "template_name": "Task Assigned",
        "notification_type": "Task Assigned",
        "module": "tasks",
        "channel": "in_app",
        "subject_template": "New task: {{title}}",
        "body_template": "{{message}}",
        "priority": "Normal",
    },
    {
        "template_code": "SECURITY_ALERT",
        "template_name": "Security Alert",
        "notification_type": "Security Alert",
        "module": "security",
        "channel": "in_app",
        "subject_template": "Security alert: {{title}}",
        "body_template": "{{message}}",
        "priority": "Critical",
    },
    {
        "template_code": "SYSTEM_ERROR",
        "template_name": "System Error",
        "notification_type": "System Error",
        "module": "system",
        "channel": "in_app",
        "subject_template": "System error: {{title}}",
        "body_template": "{{message}}",
        "priority": "High",
    },
    {
        "template_code": "CUSTOM",
        "template_name": "Custom Notification",
        "notification_type": "Custom Notification",
        "module": "system",
        "channel": "in_app",
        "subject_template": "{{title}}",
        "body_template": "{{message}}",
        "priority": "Normal",
    },
)

DEFAULT_CHANNELS: tuple[dict[str, Any], ...] = (
    {
        "channel_code": "IN_APP",
        "channel_name": "In-App",
        "channel_type": "in_app",
        "is_enabled": 1,
        "config_json": {},
    },
    {
        "channel_code": "EMAIL",
        "channel_name": "Email",
        "channel_type": "email",
        "is_enabled": 1,
        "config_json": {"provider": "stub", "smtp_ready": False},
    },
    {
        "channel_code": "SMS",
        "channel_name": "SMS",
        "channel_type": "sms",
        "is_enabled": 1,
        "config_json": {"provider": "stub", "gateway_ready": False},
    },
)


def _gen_uuid() -> str:
    return str(uuid.uuid4())


def _row_to_dict(row) -> dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    return dict(row) if hasattr(row, "keys") else {}


def _mask_sensitive(text: str | None) -> str:
    if not text:
        return ""
    masked = re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[email]", text, flags=re.I)
    masked = re.sub(r"\b\d{10,16}\b", "[number]", masked)
    masked = re.sub(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", "[card]", masked)
    return masked


def _parse_json_field(value: Any, default: Any) -> Any:
    if value is None or value == "":
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def _normalize_notification_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    is_read = int(out.get("is_read") or 0)
    out["read_status"] = out.get("read_status") or ("read" if is_read else "unread")
    out["is_read"] = is_read
    if not out.get("module") and out.get("module_id"):
        out["module"] = out["module_id"]
    if not out.get("related_record_type") and out.get("record_table"):
        out["related_record_type"] = out["record_table"]
    if not out.get("related_record_id") and out.get("record_id") is not None:
        out["related_record_id"] = out["record_id"]
    out["ai_metadata"] = _parse_json_field(out.get("ai_metadata"), {})
    out["behavior_tags"] = _parse_json_field(out.get("behavior_tags"), [])
    return out


def ensure_notification_schema(db) -> None:
    """Bootstrap MODULE-022 tables (idempotent). Extends legacy ``notifications`` table."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            notification_type TEXT,
            module_id TEXT,
            record_id INTEGER,
            record_table TEXT,
            is_read INTEGER DEFAULT 0,
            created_at TEXT
        )
        """
    )
    for col, ctype in (
        ("uuid", "TEXT"),
        ("company_id", "INTEGER"),
        ("branch_id", "INTEGER"),
        ("employee_id", "INTEGER"),
        ("module", "TEXT"),
        ("priority", "TEXT DEFAULT 'Normal'"),
        ("title", "TEXT"),
        ("channel", "TEXT DEFAULT 'in_app'"),
        ("status", "TEXT DEFAULT 'Pending'"),
        ("read_status", "TEXT DEFAULT 'unread'"),
        ("read_at", "TEXT"),
        ("scheduled_at", "TEXT"),
        ("sent_at", "TEXT"),
        ("failed_reason", "TEXT"),
        ("related_record_type", "TEXT"),
        ("related_record_id", "INTEGER"),
        ("created_by", "TEXT"),
        ("updated_at", "TEXT"),
        ("ai_metadata", "TEXT"),
        ("risk_score", "REAL"),
        ("behavior_tags", "TEXT"),
    ):
        _ensure_column(db, "notifications", col, ctype)

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS notification_templates(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_code TEXT UNIQUE NOT NULL,
            template_name TEXT NOT NULL,
            notification_type TEXT NOT NULL,
            module TEXT,
            channel TEXT DEFAULT 'in_app',
            subject_template TEXT,
            body_template TEXT,
            priority TEXT DEFAULT 'Normal',
            is_active INTEGER DEFAULT 1,
            metadata_json TEXT,
            created_by TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS notification_channels(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_code TEXT UNIQUE NOT NULL,
            channel_name TEXT NOT NULL,
            channel_type TEXT NOT NULL,
            is_enabled INTEGER DEFAULT 1,
            config_json TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS notification_preferences(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            company_id INTEGER,
            email_enabled INTEGER DEFAULT 1,
            sms_enabled INTEGER DEFAULT 0,
            in_app_enabled INTEGER DEFAULT 1,
            module_preferences_json TEXT,
            priority_preferences_json TEXT,
            quiet_hours_start TEXT,
            quiet_hours_end TEXT,
            daily_summary INTEGER DEFAULT 0,
            weekly_summary INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT,
            UNIQUE(user_id, company_id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS notification_logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notification_id INTEGER NOT NULL,
            channel TEXT NOT NULL,
            attempt_number INTEGER DEFAULT 1,
            status TEXT NOT NULL,
            response_payload TEXT,
            error_message TEXT,
            masked_payload TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(notification_id) REFERENCES notifications(id)
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read, created_at)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_notifications_company ON notifications(company_id, status, created_at)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_notification_logs_nid ON notification_logs(notification_id, created_at)"
    )
    db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_notifications_uuid ON notifications(uuid)"
    )
    try:
        from audit_trail_service import ensure_audit_schema

        ensure_audit_schema(db)
    except Exception:
        pass
    _seed_notification_channels(db)
    _seed_notification_templates(db)
    _seed_notification_permission(db)


def _seed_notification_channels(db) -> None:
    if not _table_exists(db, "notification_channels"):
        return
    now = _now_ts()
    for ch in DEFAULT_CHANNELS:
        existing = db.execute(
            "SELECT id FROM notification_channels WHERE channel_code=?",
            (ch["channel_code"],),
        ).fetchone()
        if existing:
            continue
        db.execute(
            """
            INSERT INTO notification_channels(
                channel_code, channel_name, channel_type, is_enabled,
                config_json, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?)
            """,
            (
                ch["channel_code"],
                ch["channel_name"],
                ch["channel_type"],
                int(ch["is_enabled"]),
                json.dumps(ch.get("config_json") or {}),
                now,
                now,
            ),
        )


def _seed_notification_templates(db) -> None:
    if not _table_exists(db, "notification_templates"):
        return
    now = _now_ts()
    for tpl in DEFAULT_TEMPLATES:
        existing = db.execute(
            "SELECT id FROM notification_templates WHERE template_code=?",
            (tpl["template_code"],),
        ).fetchone()
        if existing:
            continue
        db.execute(
            """
            INSERT INTO notification_templates(
                template_code, template_name, notification_type, module, channel,
                subject_template, body_template, priority, is_active,
                created_by, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                tpl["template_code"],
                tpl["template_name"],
                tpl["notification_type"],
                tpl["module"],
                tpl["channel"],
                tpl["subject_template"],
                tpl["body_template"],
                tpl["priority"],
                1,
                "system",
                now,
                now,
            ),
        )


def _seed_notification_permission(db) -> None:
    if not _table_exists(db, "permissions"):
        return
    screen = NOTIFICATION_PERMISSION_ENDPOINT
    existing = db.execute(
        "SELECT id FROM permissions WHERE screen_name=? AND COALESCE(is_deleted,0)=0 LIMIT 1",
        (screen,),
    ).fetchone()
    if existing:
        return
    now = _now_ts()
    db.execute(
        """
        INSERT INTO permissions(
            permission_code, permission_name, module_name, menu_name, screen_name,
            action, description, status, created_by, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "SET-NOTIFICATION-CENTER",
            "Notification Center",
            NOTIFICATION_MODULE_NAME,
            NOTIFICATION_MODULE_NAME,
            screen,
            "",
            "Access to Notification Center",
            "Active",
            "system",
            now,
        ),
    )


def user_can_notification_center(
    db,
    user_id: int | None,
    action: str = "view",
    *,
    is_admin: bool = False,
    is_platform_super_admin: bool = False,
) -> bool:
    if is_platform_super_admin or is_admin:
        return True
    if not user_id:
        return False
    check = action if action in ("view", "create", "edit", "delete", "export", "admin_view") else "view"
    try:
        from user_permission_service import check_user_access_with_roles

        if check_user_access_with_roles(
            db,
            user_id,
            screen_name=NOTIFICATION_PERMISSION_ENDPOINT,
            endpoint=NOTIFICATION_PERMISSION_ENDPOINT,
            module_name=NOTIFICATION_MODULE_NAME,
            action=check if check != "admin_view" else "edit",
            is_admin=is_admin,
            is_platform_super_admin=is_platform_super_admin,
        ):
            return True
    except ImportError:
        pass
    try:
        from user_permission_service import (
            empty_permission_actions,
            ensure_user_tab_permissions_schema,
            normalize_permission_actions,
        )

        ensure_user_tab_permissions_schema(db)
        row = db.execute(
            """
            SELECT granted, action_flags FROM user_tab_permissions
            WHERE user_id=? AND granted=1 AND endpoint=?
            LIMIT 1
            """,
            (user_id, NOTIFICATION_PERMISSION_ENDPOINT),
        ).fetchone()
        if not row:
            return check == "view"
        raw_flags = row["action_flags"] if hasattr(row, "keys") else row[1]
        actions = normalize_permission_actions(
            json.loads(raw_flags) if raw_flags else empty_permission_actions()
        )
        if check == "admin_view":
            return bool(actions.get("edit") or actions.get("delete"))
        return bool(actions.get(check, check == "view"))
    except Exception:
        return check == "view"


def _user_company_branch(db, user_id: int) -> tuple[int | None, int | None]:
    if not _table_exists(db, "users"):
        return None, None
    row = db.execute(
        "SELECT company_id, branch_id FROM users WHERE id=?",
        (user_id,),
    ).fetchone()
    if not row:
        return None, None
    return row["company_id"] if hasattr(row, "keys") else row[0], (
        row["branch_id"] if hasattr(row, "keys") else row[1]
    )


def get_user_notification_preferences(
    db,
    user_id: int,
    *,
    company_id: int | None = None,
) -> dict[str, Any]:
    ensure_notification_schema(db)
    if company_id is None:
        company_id, _ = _user_company_branch(db, user_id)
    row = db.execute(
        """
        SELECT * FROM notification_preferences
        WHERE user_id=? AND (company_id IS ? OR company_id=?)
        ORDER BY CASE WHEN company_id IS NULL THEN 0 ELSE 1 END DESC, company_id DESC
        LIMIT 1
        """,
        (user_id, company_id, company_id),
    ).fetchone()
    if not row:
        return default_notification_preferences(user_id, company_id)
    data = _row_to_dict(row)
    return {
        "user_id": user_id,
        "company_id": data.get("company_id"),
        "email_enabled": bool(int(data.get("email_enabled") or 0)),
        "sms_enabled": bool(int(data.get("sms_enabled") or 0)),
        "in_app_enabled": bool(int(data.get("in_app_enabled") or 1)),
        "module_preferences": _parse_json_field(
            data.get("module_preferences_json"), dict(DEFAULT_MODULE_PREFERENCES)
        ),
        "priority_preferences": _parse_json_field(
            data.get("priority_preferences_json"), dict(DEFAULT_PRIORITY_PREFERENCES)
        ),
        "quiet_hours_start": data.get("quiet_hours_start") or "",
        "quiet_hours_end": data.get("quiet_hours_end") or "",
        "daily_summary": bool(int(data.get("daily_summary") or 0)),
        "weekly_summary": bool(int(data.get("weekly_summary") or 0)),
    }


def default_notification_preferences(
    user_id: int,
    company_id: int | None = None,
) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "company_id": company_id,
        "email_enabled": True,
        "sms_enabled": False,
        "in_app_enabled": True,
        "module_preferences": dict(DEFAULT_MODULE_PREFERENCES),
        "priority_preferences": dict(DEFAULT_PRIORITY_PREFERENCES),
        "quiet_hours_start": "",
        "quiet_hours_end": "",
        "daily_summary": False,
        "weekly_summary": False,
    }


def set_user_notification_preferences(
    db,
    user_id: int,
    payload: dict[str, Any],
    *,
    actor: str = "system",
) -> dict[str, Any]:
    ensure_notification_schema(db)
    company_id = payload.get("company_id")
    if company_id is None:
        company_id, _ = _user_company_branch(db, user_id)
    prefs = get_user_notification_preferences(db, user_id, company_id=company_id)
    for key in (
        "email_enabled",
        "sms_enabled",
        "in_app_enabled",
        "daily_summary",
        "weekly_summary",
        "quiet_hours_start",
        "quiet_hours_end",
    ):
        if key in payload:
            prefs[key] = payload[key]
    if "module_preferences" in payload:
        prefs["module_preferences"] = payload["module_preferences"]
    if "priority_preferences" in payload:
        prefs["priority_preferences"] = payload["priority_preferences"]
    now = _now_ts()
    row = db.execute(
        "SELECT id FROM notification_preferences WHERE user_id=? AND company_id IS ?",
        (user_id, company_id),
    ).fetchone()
    values = (
        int(prefs.get("email_enabled", True)),
        int(prefs.get("sms_enabled", False)),
        int(prefs.get("in_app_enabled", True)),
        json.dumps(prefs.get("module_preferences") or DEFAULT_MODULE_PREFERENCES),
        json.dumps(prefs.get("priority_preferences") or DEFAULT_PRIORITY_PREFERENCES),
        prefs.get("quiet_hours_start") or "",
        prefs.get("quiet_hours_end") or "",
        int(prefs.get("daily_summary", False)),
        int(prefs.get("weekly_summary", False)),
        now,
    )
    if row:
        db.execute(
            """
            UPDATE notification_preferences SET
                email_enabled=?, sms_enabled=?, in_app_enabled=?,
                module_preferences_json=?, priority_preferences_json=?,
                quiet_hours_start=?, quiet_hours_end=?,
                daily_summary=?, weekly_summary=?, updated_at=?
            WHERE id=?
            """,
            values + (row["id"] if hasattr(row, "keys") else row[0],),
        )
    else:
        db.execute(
            """
            INSERT INTO notification_preferences(
                user_id, company_id, email_enabled, sms_enabled, in_app_enabled,
                module_preferences_json, priority_preferences_json,
                quiet_hours_start, quiet_hours_end, daily_summary, weekly_summary,
                created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                user_id,
                company_id,
                *values[:9],
                now,
                now,
            ),
        )
    return get_user_notification_preferences(db, user_id, company_id=company_id)


def _in_quiet_hours(prefs: dict[str, Any], now: datetime | None = None) -> bool:
    start = (prefs.get("quiet_hours_start") or "").strip()
    end = (prefs.get("quiet_hours_end") or "").strip()
    if not start or not end:
        return False
    try:
        now = now or datetime.now()
        start_t = datetime.strptime(start[:5], "%H:%M").time()
        end_t = datetime.strptime(end[:5], "%H:%M").time()
        current = now.time()
        if start_t <= end_t:
            return start_t <= current <= end_t
        return current >= start_t or current <= end_t
    except ValueError:
        return False


def _channel_enabled(prefs: dict[str, Any], channel: str) -> bool:
    if channel == "in_app":
        return bool(prefs.get("in_app_enabled", True))
    if channel == "email":
        return bool(prefs.get("email_enabled", True))
    if channel == "sms":
        return bool(prefs.get("sms_enabled", False))
    return False


def _module_allowed(prefs: dict[str, Any], module: str | None) -> bool:
    if not module:
        return True
    mods = prefs.get("module_preferences") or {}
    key = module.lower().replace(" ", "_")
    for k, v in mods.items():
        if k.lower() == key or key.startswith(k.lower()):
            return bool(v)
    return True


def _priority_allowed(prefs: dict[str, Any], priority: str) -> bool:
    prios = prefs.get("priority_preferences") or {}
    return bool(prios.get(priority, True))


def _log_delivery(
    db,
    notification_id: int,
    channel: str,
    status: str,
    *,
    attempt: int = 1,
    response: Any = None,
    error: str | None = None,
    payload: str | None = None,
) -> None:
    db.execute(
        """
        INSERT INTO notification_logs(
            notification_id, channel, attempt_number, status,
            response_payload, error_message, masked_payload, created_at
        ) VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            notification_id,
            channel,
            attempt,
            status,
            json.dumps(response) if response is not None else None,
            error,
            _mask_sensitive(payload or ""),
            _now_ts(),
        ),
    )


def send_in_app(db, notification_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Deliver in-app notification (record already exists)."""
    now = _now_ts()
    db.execute(
        """
        UPDATE notifications SET status='Sent', sent_at=?, channel='in_app',
            updated_at=?, read_status='unread', is_read=0
        WHERE id=?
        """,
        (now, now, notification_id),
    )
    _log_delivery(
        db,
        notification_id,
        "in_app",
        "sent",
        response={"delivered": True},
        payload=payload.get("message"),
    )
    return {"ok": True, "channel": "in_app", "notification_id": notification_id}


def send_email(db, notification_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Email stub — logs delivery intent; SMTP integration point for production."""
    user_id = payload.get("user_id")
    email = None
    if user_id and _table_exists(db, "users"):
        row = db.execute("SELECT email FROM users WHERE id=?", (user_id,)).fetchone()
        if row:
            email = row["email"] if hasattr(row, "keys") else row[0]
    masked_to = _mask_sensitive(email or f"user:{user_id}")
    _log_delivery(
        db,
        notification_id,
        "email",
        "stub_sent",
        response={"provider": "stub", "queued": True, "to": masked_to},
        payload=payload.get("message"),
    )
    return {"ok": True, "channel": "email", "stub": True, "to": masked_to}


def send_sms(db, notification_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """SMS stub — logs delivery intent; gateway integration point for production."""
    user_id = payload.get("user_id")
    mobile = None
    if user_id and _table_exists(db, "users"):
        row = db.execute("SELECT mobile FROM users WHERE id=?", (user_id,)).fetchone()
        if row:
            mobile = row["mobile"] if hasattr(row, "keys") else row[0]
    masked_to = _mask_sensitive(mobile or f"user:{user_id}")
    _log_delivery(
        db,
        notification_id,
        "sms",
        "stub_sent",
        response={"provider": "stub", "queued": True, "to": masked_to},
        payload=payload.get("message"),
    )
    return {"ok": True, "channel": "sms", "stub": True, "to": masked_to}


def _validate_send_payload(payload: dict[str, Any]) -> None:
    if not payload.get("user_id"):
        raise ValueError("user_id is required")
    ntype = payload.get("notification_type") or "Custom Notification"
    if ntype not in NOTIFICATION_TYPES:
        raise ValueError(f"Invalid notification_type: {ntype}")
    priority = payload.get("priority") or "Normal"
    if priority not in NOTIFICATION_PRIORITIES:
        raise ValueError(f"Invalid priority: {priority}")
    channel = payload.get("channel") or "in_app"
    if channel not in NOTIFICATION_CHANNELS and channel != "all":
        raise ValueError(f"Invalid channel: {channel}")


def _insert_notification(db, payload: dict[str, Any], *, status: str = "Pending") -> int:
    now = _now_ts()
    user_id = int(payload["user_id"])
    company_id = payload.get("company_id")
    branch_id = payload.get("branch_id")
    if company_id is None or branch_id is None:
        uc, ub = _user_company_branch(db, user_id)
        company_id = company_id if company_id is not None else uc
        branch_id = branch_id if branch_id is not None else ub
    module = payload.get("module") or payload.get("module_id") or ""
    record_table = payload.get("related_record_type") or payload.get("record_table")
    record_id = payload.get("related_record_id") or payload.get("record_id")
    title = (payload.get("title") or payload.get("notification_type") or "Notification").strip()
    message = (payload.get("message") or title).strip()
    ai_meta = payload.get("ai_metadata") or {}
    behavior = payload.get("behavior_tags") or []
    db.execute(
        """
        INSERT INTO notifications(
            uuid, company_id, branch_id, user_id, employee_id,
            module, module_id, notification_type, priority, title, message,
            channel, status, read_status, is_read,
            scheduled_at, related_record_type, related_record_id,
            record_table, record_id,
            created_by, created_at, updated_at,
            ai_metadata, risk_score, behavior_tags
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            payload.get("uuid") or _gen_uuid(),
            company_id,
            branch_id,
            user_id,
            payload.get("employee_id"),
            module,
            module,
            payload.get("notification_type") or "Custom Notification",
            payload.get("priority") or "Normal",
            title,
            message,
            payload.get("channel") or "in_app",
            status,
            "unread",
            payload.get("scheduled_at"),
            record_table,
            record_id,
            record_table,
            record_id,
            payload.get("created_by") or "system",
            now,
            now,
            json.dumps(ai_meta) if ai_meta else None,
            payload.get("risk_score"),
            json.dumps(behavior) if behavior else None,
        ),
    )
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


def send_notification(db, payload: dict[str, Any]) -> dict[str, Any]:
    """Primary entry point — routes to enabled channels respecting user preferences."""
    ensure_notification_schema(db)
    _validate_send_payload(payload)
    user_id = int(payload["user_id"])
    prefs = get_user_notification_preferences(db, user_id, company_id=payload.get("company_id"))
    module = payload.get("module") or payload.get("module_id") or "system"
    priority = payload.get("priority") or "Normal"

    if not _module_allowed(prefs, module):
        return {"ok": False, "skipped": True, "reason": "module_disabled"}
    if not _priority_allowed(prefs, priority):
        return {"ok": False, "skipped": True, "reason": "priority_disabled"}

    scheduled_at = payload.get("scheduled_at")
    if scheduled_at:
        nid = _insert_notification(db, payload, status="Scheduled")
        return {"ok": True, "notification_id": nid, "status": "Scheduled"}

    quiet = _in_quiet_hours(prefs)
    requested = payload.get("channel") or "in_app"
    channels: list[str]
    if requested == "all":
        channels = [c for c in NOTIFICATION_CHANNELS if _channel_enabled(prefs, c)]
    else:
        channels = [requested] if _channel_enabled(prefs, requested) else []

    if quiet and priority not in ("Critical", "High"):
        channels = [c for c in channels if c == "in_app"] or (["in_app"] if prefs.get("in_app_enabled") else [])

    if not channels:
        return {"ok": False, "skipped": True, "reason": "no_enabled_channels"}

    nid = _insert_notification(db, payload, status="Pending")
    deliver_payload = {**payload, "user_id": user_id, "notification_id": nid}
    results = []
    primary_sent = False
    for ch in channels:
        if ch == "in_app":
            results.append(send_in_app(db, nid, deliver_payload))
            primary_sent = True
        elif ch == "email":
            results.append(send_email(db, nid, deliver_payload))
        elif ch == "sms":
            results.append(send_sms(db, nid, deliver_payload))
    if not primary_sent and "in_app" not in channels:
        now = _now_ts()
        db.execute(
            "UPDATE notifications SET status='Sent', sent_at=?, updated_at=? WHERE id=?",
            (now, now, nid),
        )
    return {"ok": True, "notification_id": nid, "channels": results}


def notify_user(
    db,
    user_id: int,
    message: str,
    notification_type: str = "Custom Notification",
    *,
    title: str | None = None,
    module: str | None = None,
    module_id: str | None = None,
    record_id: int | None = None,
    record_table: str | None = None,
    priority: str = "Normal",
    channel: str = "in_app",
    created_by: str = "system",
    **kwargs: Any,
) -> dict[str, Any]:
    """Thin wrapper for other ERP modules."""
    payload = {
        "user_id": user_id,
        "message": message,
        "notification_type": notification_type,
        "title": title,
        "module": module or module_id,
        "module_id": module_id or module,
        "record_id": record_id,
        "record_table": record_table,
        "related_record_id": record_id,
        "related_record_type": record_table,
        "priority": priority,
        "channel": channel,
        "created_by": created_by,
        **kwargs,
    }
    return send_notification(db, payload)


def schedule_notification(db, payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get("scheduled_at"):
        raise ValueError("scheduled_at is required for scheduling")
    ensure_notification_schema(db)
    _validate_send_payload(payload)
    nid = _insert_notification(db, payload, status="Scheduled")
    return {"ok": True, "notification_id": nid, "status": "Scheduled"}


def mark_as_read(db, user_id: int, notification_id: int) -> dict[str, Any]:
    ensure_notification_schema(db)
    row = db.execute(
        "SELECT id, user_id FROM notifications WHERE id=?",
        (notification_id,),
    ).fetchone()
    if not row:
        raise ValueError("Notification not found")
    owner = row["user_id"] if hasattr(row, "keys") else row[1]
    if int(owner) != int(user_id):
        raise PermissionError("Cannot mark another user's notification")
    now = _now_ts()
    db.execute(
        """
        UPDATE notifications SET is_read=1, read_status='read', read_at=?, updated_at=?
        WHERE id=? AND user_id=?
        """,
        (now, now, notification_id, user_id),
    )
    return {"ok": True, "notification_id": notification_id}


def mark_all_as_read(db, user_id: int, *, company_id: int | None = None) -> dict[str, Any]:
    ensure_notification_schema(db)
    now = _now_ts()
    if company_id is not None:
        db.execute(
            """
            UPDATE notifications SET is_read=1, read_status='read', read_at=?, updated_at=?
            WHERE user_id=? AND company_id=? AND COALESCE(is_read,0)=0
            """,
            (now, now, user_id, company_id),
        )
    else:
        db.execute(
            """
            UPDATE notifications SET is_read=1, read_status='read', read_at=?, updated_at=?
            WHERE user_id=? AND COALESCE(is_read,0)=0
            """,
            (now, now, user_id),
        )
    return {"ok": True}


def get_notification(db, notification_id: int, *, user_id: int | None = None, admin: bool = False) -> dict[str, Any]:
    ensure_notification_schema(db)
    row = db.execute("SELECT * FROM notifications WHERE id=?", (notification_id,)).fetchone()
    if not row:
        raise ValueError("Notification not found")
    data = _normalize_notification_row(_row_to_dict(row))
    if not admin and user_id is not None and int(data.get("user_id") or 0) != int(user_id):
        raise PermissionError("Access denied")
    return data


def get_user_notifications(
    db,
    user_id: int,
    *,
    page: int = 1,
    per_page: int = 20,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    unread_only: bool = False,
    notification_type: str = "",
    priority: str = "",
    status: str = "",
    module: str = "",
    channel: str = "",
    company_id: int | None = None,
    admin_view: bool = False,
) -> dict[str, Any]:
    ensure_notification_schema(db)
    page = max(1, int(page))
    per_page = max(1, min(100, int(per_page)))
    sort_by = sort_by if sort_by in NOTIFICATION_SORT_COLUMNS else "created_at"
    sort_dir = "ASC" if str(sort_dir).lower() == "asc" else "DESC"
    clauses = []
    params: list[Any] = []
    if admin_view and company_id is not None:
        clauses.append("company_id=?")
        params.append(company_id)
    else:
        clauses.append("user_id=?")
        params.append(user_id)
    if unread_only:
        clauses.append("COALESCE(is_read,0)=0")
    if notification_type:
        clauses.append("notification_type=?")
        params.append(notification_type)
    if priority:
        clauses.append("priority=?")
        params.append(priority)
    if status:
        clauses.append("status=?")
        params.append(status)
    if module:
        clauses.append("(module=? OR module_id=?)")
        params.extend([module, module])
    if channel:
        clauses.append("channel=?")
        params.append(channel)
    where = " AND ".join(clauses) if clauses else "1=1"
    total = int(
        db.execute(f"SELECT COUNT(*) FROM notifications WHERE {where}", tuple(params)).fetchone()[0]
    )
    offset = (page - 1) * per_page
    rows = db.execute(
        f"""
        SELECT * FROM notifications WHERE {where}
        ORDER BY {sort_by} {sort_dir}
        LIMIT ? OFFSET ?
        """,
        tuple(params) + (per_page, offset),
    ).fetchall()
    items = [_normalize_notification_row(_row_to_dict(r)) for r in rows]
    return {
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": max(1, (total + per_page - 1) // per_page),
    }


def get_unread_count(db, user_id: int, *, company_id: int | None = None) -> int:
    ensure_notification_schema(db)
    if company_id is not None:
        row = db.execute(
            """
            SELECT COUNT(*) FROM notifications
            WHERE user_id=? AND company_id=? AND COALESCE(is_read,0)=0
            """,
            (user_id, company_id),
        ).fetchone()
    else:
        row = db.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id=? AND COALESCE(is_read,0)=0",
            (user_id,),
        ).fetchone()
    return int(row[0] if row else 0)


def retry_failed_notification(db, notification_id: int, *, actor: str = "system") -> dict[str, Any]:
    ensure_notification_schema(db)
    row = db.execute("SELECT * FROM notifications WHERE id=?", (notification_id,)).fetchone()
    if not row:
        raise ValueError("Notification not found")
    data = _row_to_dict(row)
    if data.get("status") not in ("Failed", "Pending"):
        raise ValueError("Only failed or pending notifications can be retried")
    channel = data.get("channel") or "in_app"
    payload = {
        "user_id": data.get("user_id"),
        "message": data.get("message"),
        "notification_type": data.get("notification_type"),
        "title": data.get("title"),
    }
    try:
        if channel == "email":
            result = send_email(db, notification_id, payload)
        elif channel == "sms":
            result = send_sms(db, notification_id, payload)
        else:
            result = send_in_app(db, notification_id, payload)
        now = _now_ts()
        db.execute(
            "UPDATE notifications SET status='Sent', sent_at=?, failed_reason=NULL, updated_at=?, created_by=? WHERE id=?",
            (now, now, actor, notification_id),
        )
        return {"ok": True, "notification_id": notification_id, "result": result}
    except Exception as exc:
        db.execute(
            "UPDATE notifications SET status='Failed', failed_reason=?, updated_at=? WHERE id=?",
            (str(exc)[:500], _now_ts(), notification_id),
        )
        _log_delivery(db, notification_id, channel, "failed", error=str(exc))
        raise


def get_dashboard_metrics(
    db,
    user_id: int,
    *,
    company_id: int | None = None,
    admin_view: bool = False,
) -> dict[str, Any]:
    ensure_notification_schema(db)
    if admin_view and company_id is not None:
        scope_sql = "company_id=?"
        scope_params: tuple[Any, ...] = (company_id,)
    else:
        scope_sql = "user_id=?"
        scope_params = (user_id,)

    total = int(
        db.execute(f"SELECT COUNT(*) FROM notifications WHERE {scope_sql}", scope_params).fetchone()[0]
    )
    unread = int(
        db.execute(
            f"SELECT COUNT(*) FROM notifications WHERE {scope_sql} AND COALESCE(is_read,0)=0",
            scope_params,
        ).fetchone()[0]
    )
    failed = int(
        db.execute(
            f"SELECT COUNT(*) FROM notifications WHERE {scope_sql} AND status='Failed'",
            scope_params,
        ).fetchone()[0]
    )
    high_priority = int(
        db.execute(
            f"""
            SELECT COUNT(*) FROM notifications
            WHERE {scope_sql} AND priority IN ('High','Critical') AND COALESCE(is_read,0)=0
            """,
            scope_params,
        ).fetchone()[0]
    )
    recent = [
        _normalize_notification_row(_row_to_dict(r))
        for r in db.execute(
            f"""
            SELECT * FROM notifications WHERE {scope_sql}
            ORDER BY created_at DESC LIMIT 10
            """,
            scope_params,
        ).fetchall()
    ]
    by_channel_rows = db.execute(
        f"""
        SELECT channel, COUNT(*) AS cnt FROM notifications
        WHERE {scope_sql} GROUP BY channel
        """,
        scope_params,
    ).fetchall()
    delivery_by_channel = {
        (r["channel"] if hasattr(r, "keys") else r[0]): int(r["cnt"] if hasattr(r, "keys") else r[1])
        for r in by_channel_rows
    }
    trend_rows = db.execute(
        f"""
        SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS cnt
        FROM notifications WHERE {scope_sql} AND created_at IS NOT NULL
        GROUP BY day ORDER BY day DESC LIMIT 14
        """,
        scope_params,
    ).fetchall()
    trend = [
        {"date": r["day"] if hasattr(r, "keys") else r[0], "count": int(r["cnt"] if hasattr(r, "keys") else r[1])}
        for r in reversed(list(trend_rows))
    ]
    return {
        "total": total,
        "unread": unread,
        "failed": failed,
        "high_priority": high_priority,
        "recent": recent,
        "delivery_by_channel": delivery_by_channel,
        "trend": trend,
    }
