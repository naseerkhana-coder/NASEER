"""Per-user dashboard customization."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from user_context_service import ensure_user_context_schema

DEFAULT_ROLE_PROFILES: dict[str, dict[str, Any]] = {
    "accounts": {
        "favorite_modules": ["accounts_payments", "accounts_receipts", "accounts_gst", "accounts_reports"],
        "dashboard_cards": ["payments", "receipts", "gst", "pending_bills"],
        "quick_actions": ["payment_voucher", "receipt_voucher", "journal"],
        "reports": ["accounts_reports", "gst_summary"],
    },
    "project_engineer": {
        "favorite_modules": ["boq_management", "dpr_entry", "client_billing_register", "projects"],
        "dashboard_cards": ["active_projects", "boq", "dpr", "billing"],
        "quick_actions": ["new_boq", "new_dpr", "new_bill"],
        "reports": ["project_reports"],
    },
    "store": {
        "favorite_modules": ["store_receipt", "material_request", "store", "purchase_orders"],
        "dashboard_cards": ["grn", "material_request", "stock_status", "low_stock"],
        "quick_actions": ["material_request", "grn", "material_issue"],
        "reports": ["store_reports"],
    },
    "default": {
        "favorite_modules": ["dashboard", "approvals", "notifications"],
        "dashboard_cards": ["active_projects", "pending_approvals", "notifications"],
        "quick_actions": ["new_dpr", "material_request"],
        "reports": ["reports"],
    },
}


def _merge_defaults(prefs: dict[str, Any] | None, role_profile: str) -> dict[str, Any]:
    base = dict(DEFAULT_ROLE_PROFILES.get(role_profile, DEFAULT_ROLE_PROFILES["default"]))
    if not prefs:
        return base
    for key in ("favorite_modules", "dashboard_cards", "quick_actions", "reports"):
        if prefs.get(key):
            base[key] = prefs[key]
    return base


def load_dashboard_preferences(db, user_id: int | None) -> dict[str, Any]:
    if not user_id:
        return _merge_defaults(None, "default")
    ensure_user_context_schema(db)
    row = db.execute(
        "SELECT * FROM user_dashboard_preferences WHERE user_id=?",
        (user_id,),
    ).fetchone()
    if not row:
        return _merge_defaults(None, "default")
    role_profile = row["role_profile"] or "default"
    parsed: dict[str, Any] = {"role_profile": role_profile}
    for col in ("favorite_modules", "dashboard_cards", "quick_actions", "reports"):
        raw = row[col]
        if raw:
            try:
                parsed[col] = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                parsed[col] = []
        else:
            parsed[col] = []
    return _merge_defaults(parsed, role_profile)


def save_dashboard_preferences(
    db,
    user_id: int,
    *,
    role_profile: str | None = None,
    favorite_modules: list[str] | None = None,
    dashboard_cards: list[str] | None = None,
    quick_actions: list[str] | None = None,
    reports: list[str] | None = None,
) -> dict[str, Any]:
    ensure_user_context_schema(db)
    existing = load_dashboard_preferences(db, user_id)
    payload = {
        "role_profile": role_profile or existing.get("role_profile", "default"),
        "favorite_modules": favorite_modules if favorite_modules is not None else existing.get("favorite_modules", []),
        "dashboard_cards": dashboard_cards if dashboard_cards is not None else existing.get("dashboard_cards", []),
        "quick_actions": quick_actions if quick_actions is not None else existing.get("quick_actions", []),
        "reports": reports if reports is not None else existing.get("reports", []),
    }
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        """
        INSERT INTO user_dashboard_preferences(
            user_id, role_profile, favorite_modules, dashboard_cards, quick_actions, reports, updated_at
        ) VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET
            role_profile=excluded.role_profile,
            favorite_modules=excluded.favorite_modules,
            dashboard_cards=excluded.dashboard_cards,
            quick_actions=excluded.quick_actions,
            reports=excluded.reports,
            updated_at=excluded.updated_at
        """,
        (
            user_id,
            payload["role_profile"],
            json.dumps(payload["favorite_modules"]),
            json.dumps(payload["dashboard_cards"]),
            json.dumps(payload["quick_actions"]),
            json.dumps(payload["reports"]),
            now,
        ),
    )
    db.commit()
    return payload


def infer_role_profile(department: str | None, role: str | None) -> str:
    text = f"{department or ''} {role or ''}".lower()
    if any(k in text for k in ("account", "finance", "treasury")):
        return "accounts"
    if any(k in text for k in ("store", "procurement", "inventory")):
        return "store"
    if any(k in text for k in ("project", "engineer", "planning", "site")):
        return "project_engineer"
    return "default"
