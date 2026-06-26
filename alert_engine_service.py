"""Alert & Notification Engine — unified system alerts across treasury, budget, workflow, and ops."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any

from budget_service import BUDGET_CATEGORY_ALL, budget_alerts, ensure_budget_schema
from treasury_service import (
    BG_EXPIRY_ALERT_DAYS,
    bg_expiry_alerts,
    ensure_treasury_schema,
    upcoming_maturity_alerts,
    upcoming_pdc_due_alerts,
)
from workflow_service import STATUS_PENDING_APPROVAL, STATUS_PENDING_CHECKER

logger = logging.getLogger(__name__)

ALERT_TYPES = (
    "bg_expiry",
    "fd_maturity",
    "pdc_due",
    "budget_overrun",
    "pending_approvals",
    "client_payment_due",
    "payroll_due",
    "material_shortage",
    "insurance_expiry",
    "vehicle_fitness_expiry",
)

ALERT_SEVERITIES = ("info", "warning", "critical")
ALERT_STATUSES = ("active", "dismissed", "resolved")

NOTIFICATION_SETTINGS_KEY = "alert_notification_prefs"

DEFAULT_NOTIFICATION_PREFS = {
    "email_enabled": False,
    "whatsapp_enabled": False,
    "email_address": "",
    "whatsapp_number": "",
    "notify_critical": True,
    "notify_warning": True,
    "notify_info": False,
}


def _table_exists(db, table: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _severity_from_days(days_left: int | None) -> str:
    if days_left is None:
        return "info"
    if days_left <= 7:
        return "critical"
    if days_left <= 30:
        return "warning"
    return "info"


def ensure_alert_engine_schema(db) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS system_alerts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_key TEXT NOT NULL UNIQUE,
            alert_type TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'info',
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            entity_type TEXT,
            entity_id INTEGER,
            due_date TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT,
            dismissed_by TEXT,
            dismissed_at TEXT
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_system_alerts_status ON system_alerts(status)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_system_alerts_type ON system_alerts(alert_type)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_system_alerts_severity ON system_alerts(severity)"
    )


def _upsert_alert(db, payload: dict[str, Any]) -> None:
    existing = db.execute(
        "SELECT id, status FROM system_alerts WHERE alert_key=?",
        (payload["alert_key"],),
    ).fetchone()
    if existing and existing["status"] == "dismissed":
        return
    ts = _now_ts()
    if existing:
        db.execute(
            """
            UPDATE system_alerts SET
                alert_type=?, severity=?, title=?, message=?,
                entity_type=?, entity_id=?, due_date=?,
                status='active', updated_at=?
            WHERE alert_key=? AND status != 'dismissed'
            """,
            (
                payload["alert_type"],
                payload["severity"],
                payload["title"],
                payload["message"],
                payload.get("entity_type"),
                payload.get("entity_id"),
                payload.get("due_date"),
                ts,
                payload["alert_key"],
            ),
        )
    else:
        db.execute(
            """
            INSERT INTO system_alerts(
                alert_key, alert_type, severity, title, message,
                entity_type, entity_id, due_date, status, created_at, updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                payload["alert_key"],
                payload["alert_type"],
                payload["severity"],
                payload["title"],
                payload["message"],
                payload.get("entity_type"),
                payload.get("entity_id"),
                payload.get("due_date"),
                "active",
                ts,
                ts,
            ),
        )


def _scan_bg_expiry(db) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    for row in bg_expiry_alerts(db):
        bg_id = row.get("id")
        threshold = row.get("alert_threshold", 90)
        days_left = row.get("days_left", 0)
        bg_number = row.get("bg_number") or f"#{bg_id}"
        alerts.append(
            {
                "alert_key": f"bg_expiry:{bg_id}:{threshold}",
                "alert_type": "bg_expiry",
                "severity": _severity_from_days(days_left),
                "title": f"BG expiring in {days_left} days",
                "message": (
                    f"Bank guarantee {bg_number} expires on {row.get('expiry_date')} "
                    f"(₹{float(row.get('amount') or 0):,.2f})."
                ),
                "entity_type": "bank_guarantee",
                "entity_id": bg_id,
                "due_date": row.get("expiry_date"),
            }
        )
    return alerts


def _scan_fd_maturity(db) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    for row in upcoming_maturity_alerts(db):
        fd_id = row.get("id")
        threshold = row.get("alert_threshold", 90)
        days_left = row.get("days_left", 0)
        fd_number = row.get("fd_number") or f"#{fd_id}"
        alerts.append(
            {
                "alert_key": f"fd_maturity:{fd_id}:{threshold}",
                "alert_type": "fd_maturity",
                "severity": _severity_from_days(days_left),
                "title": f"FD maturing in {days_left} days",
                "message": (
                    f"Fixed deposit {fd_number} matures on {row.get('maturity_date')} "
                    f"(₹{float(row.get('amount') or 0):,.2f})."
                ),
                "entity_type": "fixed_deposit",
                "entity_id": fd_id,
                "due_date": row.get("maturity_date"),
            }
        )
    return alerts


def _scan_pdc_due(db) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    for row in upcoming_pdc_due_alerts(db):
        pdc_id = row.get("id")
        threshold = row.get("alert_threshold", 7)
        days_left = row.get("days_left", 0)
        cheque_no = row.get("cheque_number") or f"#{pdc_id}"
        alerts.append(
            {
                "alert_key": f"pdc_due:{pdc_id}:{threshold}",
                "alert_type": "pdc_due",
                "severity": _severity_from_days(days_left),
                "title": f"PDC due in {days_left} days",
                "message": (
                    f"{row.get('pdc_type', 'PDC')} cheque #{cheque_no} for "
                    f"{row.get('party_name', '—')} due {row.get('cheque_date')}."
                ),
                "entity_type": "pdc_register",
                "entity_id": pdc_id,
                "due_date": row.get("cheque_date"),
            }
        )
    return alerts


def _scan_budget_overrun(db) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    try:
        rows = budget_alerts(db)
    except Exception as exc:
        logger.warning("Budget alert scan skipped: %s", exc)
        return alerts
    for row in rows:
        project_id = row.get("project_id")
        category = row.get("category") or BUDGET_CATEGORY_ALL
        alert_types = row.get("alert_types") or []
        severity = "critical" if "cost_overrun" in alert_types else "warning"
        type_label = ", ".join(t.replace("_", " ").title() for t in alert_types) or "Budget Alert"
        alerts.append(
            {
                "alert_key": f"budget_overrun:{project_id}:{category}",
                "alert_type": "budget_overrun",
                "severity": severity,
                "title": f"Budget alert — {row.get('project_name', 'Project')}",
                "message": (
                    f"{type_label} on {category}: utilized ₹{float(row.get('utilized') or 0):,.0f} "
                    f"vs budget ₹{float(row.get('budget_amount') or 0):,.0f}."
                ),
                "entity_type": "project_budget",
                "entity_id": project_id,
                "due_date": None,
            }
        )
    return alerts


def _scan_pending_approvals(db) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    if not _table_exists(db, "approval_requests"):
        return alerts
    pending_checker = db.execute(
        "SELECT COUNT(*) AS c FROM approval_requests WHERE workflow_status=?",
        (STATUS_PENDING_CHECKER,),
    ).fetchone()["c"]
    pending_approval = db.execute(
        "SELECT COUNT(*) AS c FROM approval_requests WHERE workflow_status=?",
        (STATUS_PENDING_APPROVAL,),
    ).fetchone()["c"]
    total = int(pending_checker) + int(pending_approval)
    if total <= 0:
        return alerts
    severity = "warning" if total >= 10 else "info"
    if total >= 25:
        severity = "critical"
    alerts.append(
        {
            "alert_key": "pending_approvals:total",
            "alert_type": "pending_approvals",
            "severity": severity,
            "title": f"{total} pending approval(s)",
            "message": (
                f"{pending_checker} awaiting checker verification, "
                f"{pending_approval} awaiting final approval."
            ),
            "entity_type": "approval_requests",
            "entity_id": None,
            "due_date": None,
        }
    )
    return alerts


def _scan_client_payment_due(db) -> list[dict[str, Any]]:
    """Stub-friendly scan of outstanding client bills."""
    alerts: list[dict[str, Any]] = []
    if not _table_exists(db, "client_bills"):
        return alerts
    cols = {
        r["name"]
        for r in db.execute("PRAGMA table_info(client_bills)").fetchall()
    }
    due_col = "cb.due_date" if "due_date" in cols else "cb.bill_date"
    try:
        rows = db.execute(
            f"""
            SELECT cb.id, cb.bill_number, cb.bill_date,
                   {due_col} AS due_date, cb.net_payable,
                   COALESCE(cb.paid_amount, 0) AS paid_amount,
                   (cb.net_payable - COALESCE(cb.paid_amount, 0)) AS outstanding,
                   p.project_name
            FROM client_bills cb
            LEFT JOIN projects p ON cb.project_id = p.id
            WHERE cb.approval_status = 'Approved'
              AND COALESCE(cb.bill_status, '') != 'Paid'
              AND (cb.net_payable - COALESCE(cb.paid_amount, 0)) > 0
            ORDER BY COALESCE({due_col}, cb.bill_date) ASC, cb.bill_date ASC
            LIMIT 50
            """
        ).fetchall()
    except Exception as exc:
        logger.warning("Client payment due scan skipped: %s", exc)
        return alerts
    today = date.today()
    for row in rows:
        item = dict(row)
        bill_id = item["id"]
        due_raw = item.get("due_date") or item.get("bill_date")
        due = _parse_date(due_raw)
        days_left = (due - today).days if due else None
        outstanding = float(item.get("outstanding") or 0)
        if due and days_left is not None and days_left < 0:
            severity = "critical"
            title = f"Client payment overdue ({abs(days_left)}d)"
        elif due and days_left is not None and days_left <= 7:
            severity = "warning"
            title = f"Client payment due in {days_left} days"
        elif due and days_left is not None and days_left <= 30:
            severity = "info"
            title = f"Client payment due in {days_left} days"
        else:
            severity = "info"
            title = "Client payment outstanding"
        alerts.append(
            {
                "alert_key": f"client_payment_due:{bill_id}",
                "alert_type": "client_payment_due",
                "severity": severity,
                "title": title,
                "message": (
                    f"Bill {item.get('bill_number') or bill_id} — "
                    f"{item.get('project_name') or '—'}: ₹{outstanding:,.2f} outstanding"
                    + (f", due {due_raw}." if due_raw else ".")
                ),
                "entity_type": "client_bill",
                "entity_id": bill_id,
                "due_date": due_raw,
            }
        )
    return alerts


def _scan_payroll_due(db) -> list[dict[str, Any]]:
    """Stub: flag recent months with pending payroll processing."""
    alerts: list[dict[str, Any]] = []
    try:
        from payroll_service import list_pending_payroll_months

        pending = list_pending_payroll_months(db, months_back=3)
    except Exception:
        return alerts
    seen_months: set[str] = set()
    for item in pending[:12]:
        ym = (item.get("year_month") or "")[:7]
        if not ym or ym in seen_months:
            continue
        seen_months.add(ym)
        count = sum(1 for p in pending if (p.get("year_month") or "")[:7] == ym)
        alerts.append(
            {
                "alert_key": f"payroll_due:{ym}",
                "alert_type": "payroll_due",
                "severity": "warning" if count >= 5 else "info",
                "title": f"Payroll pending for {ym}",
                "message": (
                    f"{count} employee(s) have attendance/timesheet data but payroll "
                    f"is not finalized for {ym} (stub alert)."
                ),
                "entity_type": "payroll",
                "entity_id": None,
                "due_date": f"{ym}-28",
            }
        )
    return alerts


def _scan_material_shortage(db) -> list[dict[str, Any]]:
    """Stub: surface low-stock materials when inventory tables exist."""
    alerts: list[dict[str, Any]] = []
    if not _table_exists(db, "inventory_items"):
        return alerts
    try:
        rows = db.execute(
            """
            SELECT id, item_code, item_name, current_stock, reorder_level
            FROM inventory_items
            WHERE reorder_level IS NOT NULL
              AND reorder_level > 0
              AND COALESCE(current_stock, 0) < reorder_level
            ORDER BY (reorder_level - COALESCE(current_stock, 0)) DESC
            LIMIT 20
            """
        ).fetchall()
    except Exception:
        return alerts
    for row in rows:
        item = dict(row)
        item_id = item["id"]
        stock = float(item.get("current_stock") or 0)
        reorder = float(item.get("reorder_level") or 0)
        alerts.append(
            {
                "alert_key": f"material_shortage:{item_id}",
                "alert_type": "material_shortage",
                "severity": "critical" if stock <= 0 else "warning",
                "title": f"Material shortage — {item.get('item_name') or item_id}",
                "message": (
                    f"{item.get('item_code') or 'Item'} stock {stock:,.2f} "
                    f"below reorder level {reorder:,.2f} (stub alert)."
                ),
                "entity_type": "inventory_item",
                "entity_id": item_id,
                "due_date": None,
            }
        )
    return alerts


def _scan_vehicle_document_expiry(db, doc_type: str, alert_type: str) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    if not _table_exists(db, "fleet_vehicle_documents") or not _table_exists(db, "fleet_vehicles"):
        return alerts
    rows = db.execute(
        """
        SELECT d.id, d.doc_type, d.doc_number, d.expiry_date, v.registration_number
        FROM fleet_vehicle_documents d
        JOIN fleet_vehicles v ON d.vehicle_id = v.id
        WHERE d.doc_type = ?
          AND d.expiry_date IS NOT NULL AND d.expiry_date != ''
        """,
        (doc_type,),
    ).fetchall()
    today = date.today()
    for row in rows:
        item = dict(row)
        expiry = _parse_date(item.get("expiry_date"))
        if not expiry:
            continue
        days_left = (expiry - today).days
        if days_left < 0:
            continue
        matched_threshold = None
        for threshold in BG_EXPIRY_ALERT_DAYS:
            if days_left <= threshold:
                matched_threshold = threshold
                break
        if matched_threshold is None:
            continue
        doc_id = item["id"]
        reg = item.get("registration_number") or "Vehicle"
        alerts.append(
            {
                "alert_key": f"{alert_type}:{doc_id}:{matched_threshold}",
                "alert_type": alert_type,
                "severity": _severity_from_days(days_left),
                "title": f"{doc_type} expiring in {days_left} days — {reg}",
                "message": (
                    f"{doc_type} #{item.get('doc_number') or doc_id} for {reg} "
                    f"expires on {item.get('expiry_date')}."
                ),
                "entity_type": "fleet_vehicle_document",
                "entity_id": doc_id,
                "due_date": item.get("expiry_date"),
            }
        )
    return alerts


def _resolve_stale_alerts(db, active_keys: set[str]) -> None:
    if not active_keys:
        db.execute(
            "UPDATE system_alerts SET status='resolved', updated_at=? WHERE status='active'",
            (_now_ts(),),
        )
        return
    placeholders = ",".join("?" for _ in active_keys)
    db.execute(
        f"""
        UPDATE system_alerts SET status='resolved', updated_at=?
        WHERE status='active' AND alert_key NOT IN ({placeholders})
        """,
        (_now_ts(), *active_keys),
    )


def _ensure_app_settings_table(db) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS app_settings(
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT
        )
        """
    )


def _get_app_setting(db, key: str, default: Any = None) -> Any:
    _ensure_app_settings_table(db)
    row = db.execute(
        "SELECT setting_value FROM app_settings WHERE setting_key=?",
        (key,),
    ).fetchone()
    if not row or row["setting_value"] is None:
        return default
    return row["setting_value"]


def _set_app_setting(db, key: str, value: str) -> None:
    _ensure_app_settings_table(db)
    db.execute(
        "INSERT INTO app_settings(setting_key, setting_value) VALUES(?,?) "
        "ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value",
        (key, value),
    )


def get_notification_prefs(db) -> dict[str, Any]:
    raw = _get_app_setting(db, NOTIFICATION_SETTINGS_KEY)
    if not raw:
        prefs = dict(DEFAULT_NOTIFICATION_PREFS)
        _set_app_setting(db, NOTIFICATION_SETTINGS_KEY, json.dumps(prefs))
        db.commit()
        return prefs
    try:
        data = json.loads(raw)
        merged = dict(DEFAULT_NOTIFICATION_PREFS)
        merged.update({k: data[k] for k in data if k in merged or k in data})
        return merged
    except (TypeError, json.JSONDecodeError):
        return dict(DEFAULT_NOTIFICATION_PREFS)


def save_notification_prefs(db, prefs: dict[str, Any]) -> dict[str, Any]:
    merged = dict(DEFAULT_NOTIFICATION_PREFS)
    for key in DEFAULT_NOTIFICATION_PREFS:
        if key in prefs:
            merged[key] = prefs[key]
    if "email_address" in prefs:
        merged["email_address"] = str(prefs.get("email_address") or "").strip()
    if "whatsapp_number" in prefs:
        merged["whatsapp_number"] = str(prefs.get("whatsapp_number") or "").strip()
    _set_app_setting(db, NOTIFICATION_SETTINGS_KEY, json.dumps(merged))
    db.commit()
    return merged


def dispatch_notification_stubs(db, alerts: list[dict[str, Any]] | None = None) -> dict[str, int]:
    """Log-only email/WhatsApp dispatch stubs — no external API calls."""
    prefs = get_notification_prefs(db)
    if alerts is None:
        alerts = list_alerts(db, status="active")
    email_count = 0
    whatsapp_count = 0
    for alert in alerts:
        sev = alert.get("severity") or "info"
        if sev == "info" and not prefs.get("notify_info"):
            continue
        if sev == "warning" and not prefs.get("notify_warning", True):
            continue
        if sev == "critical" and not prefs.get("notify_critical", True):
            continue
        title = alert.get("title") or "Alert"
        message = alert.get("message") or ""
        if prefs.get("email_enabled"):
            logger.info(
                "[ALERT EMAIL STUB] to=%s subject=%s body=%s",
                prefs.get("email_address") or "(not configured)",
                title,
                message,
            )
            email_count += 1
        if prefs.get("whatsapp_enabled"):
            logger.info(
                "[ALERT WHATSAPP STUB] to=%s message=%s — %s",
                prefs.get("whatsapp_number") or "(not configured)",
                title,
                message,
            )
            whatsapp_count += 1
    return {"email_dispatched": email_count, "whatsapp_dispatched": whatsapp_count}


def generate_alerts(db) -> dict[str, int]:
    """Scan all modules and upsert system alerts."""
    ensure_alert_engine_schema(db)
    ensure_treasury_schema(db)
    ensure_budget_schema(db)

    desired: list[dict[str, Any]] = []
    desired.extend(_scan_bg_expiry(db))
    desired.extend(_scan_fd_maturity(db))
    desired.extend(_scan_pdc_due(db))
    desired.extend(_scan_budget_overrun(db))
    desired.extend(_scan_pending_approvals(db))
    desired.extend(_scan_client_payment_due(db))
    desired.extend(_scan_payroll_due(db))
    desired.extend(_scan_material_shortage(db))
    desired.extend(_scan_vehicle_document_expiry(db, "Insurance", "insurance_expiry"))
    desired.extend(_scan_vehicle_document_expiry(db, "Fitness", "vehicle_fitness_expiry"))

    active_keys: set[str] = set()
    for payload in desired:
        active_keys.add(payload["alert_key"])
        _upsert_alert(db, payload)

    _resolve_stale_alerts(db, active_keys)
    db.commit()

    dispatch = dispatch_notification_stubs(db, desired)
    counts = get_alert_counts_by_severity(db)
    return {
        "generated": len(desired),
        "active": counts.get("total", 0),
        **dispatch,
    }


def list_alerts(
    db,
    *,
    alert_type: str | None = None,
    severity: str | None = None,
    status: str | None = "active",
    limit: int = 500,
) -> list[dict]:
    ensure_alert_engine_schema(db)
    sql = "SELECT * FROM system_alerts WHERE 1=1"
    args: list[Any] = []
    if status:
        sql += " AND status=?"
        args.append(status)
    if alert_type:
        sql += " AND alert_type=?"
        args.append(alert_type)
    if severity:
        sql += " AND severity=?"
        args.append(severity)
    sql += " ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END, due_date ASC, created_at DESC LIMIT ?"
    args.append(limit)
    return [dict(r) for r in db.execute(sql, args).fetchall()]


def dismiss_alert(db, alert_id: int, dismissed_by: str) -> bool:
    ensure_alert_engine_schema(db)
    row = db.execute("SELECT id, status FROM system_alerts WHERE id=?", (alert_id,)).fetchone()
    if not row or row["status"] != "active":
        return False
    ts = _now_ts()
    db.execute(
        """
        UPDATE system_alerts SET status='dismissed', dismissed_by=?, dismissed_at=?, updated_at=?
        WHERE id=?
        """,
        (dismissed_by, ts, ts, alert_id),
    )
    db.commit()
    return True


def get_alert_counts_by_severity(db, *, status: str = "active") -> dict[str, int]:
    ensure_alert_engine_schema(db)
    rows = db.execute(
        """
        SELECT severity, COUNT(*) AS c
        FROM system_alerts
        WHERE status=?
        GROUP BY severity
        """,
        (status,),
    ).fetchall()
    counts = {"info": 0, "warning": 0, "critical": 0, "total": 0}
    for row in rows:
        sev = row["severity"]
        c = int(row["c"])
        if sev in counts:
            counts[sev] = c
        counts["total"] += c
    return counts
