"""Live ERP badge counts for sub-toolbar and action panels."""

from __future__ import annotations

from typing import Any

from store_service import store_dashboard_stats, _pending_approval_count, _table_exists


def get_live_badge_counts(db, user_id: int | None, is_admin: bool = False) -> dict[str, int]:
    """Return live counts keyed for UI badges."""
    counts: dict[str, int] = {
        "material_request": 0,
        "purchase_request": 0,
        "pending_approval": 0,
        "pending_checker": 0,
        "payroll_pending": 0,
        "store_alerts": 0,
        "grn_pending": 0,
        "purchase_order_pending": 0,
    }
    try:
        from workflow_service import get_pending_counts

        widgets = get_pending_counts(db, user_id, is_admin) if user_id else {
            "maker": 0,
            "checker": 0,
            "approver": 0,
        }
        counts["pending_checker"] = int(widgets.get("checker", 0))
        counts["pending_approval"] = int(
            widgets.get("maker", 0) + widgets.get("checker", 0) + widgets.get("approver", 0)
        )
    except Exception:
        pass

    try:
        stats = store_dashboard_stats(db)
        counts["material_request"] = int(stats.get("pending_material_requests", 0))
        counts["purchase_request"] = int(stats.get("pending_purchase_requests", 0))
        counts["grn_pending"] = int(stats.get("pending_grn", 0))
        counts["purchase_order_pending"] = int(stats.get("pending_purchase_orders", 0))
        low_stock = int(stats.get("low_stock_count", 0))
        counts["store_alerts"] = low_stock + counts["grn_pending"]
    except Exception:
        counts["material_request"] = _pending_approval_count(db, "material_requests")
        counts["purchase_request"] = _pending_approval_count(db, "purchase_requests")

    if _table_exists(db, "payroll_records"):
        try:
            counts["payroll_pending"] = int(
                db.execute(
                    "SELECT COUNT(*) AS c FROM payroll_records "
                    "WHERE approval_status IS NOT NULL AND approval_status != 'Approved'"
                ).fetchone()["c"]
            )
        except Exception:
            pass
    elif _table_exists(db, "salary"):
        try:
            counts["payroll_pending"] = int(
                db.execute(
                    "SELECT COUNT(*) AS c FROM salary "
                    "WHERE COALESCE(approval_status, payment_status, '') NOT IN ('Approved', 'Paid')"
                ).fetchone()["c"]
            )
        except Exception:
            pass

    return counts


def badge_for_endpoint(endpoint: str, counts: dict[str, int]) -> int | None:
    mapping = {
        "material_request": "material_request",
        "purchase_request": "purchase_request",
        "approvals": "pending_approval",
        "payroll": "payroll_pending",
        "store": "store_alerts",
        "store_receipt": "grn_pending",
        "purchase_orders": "purchase_order_pending",
    }
    key = mapping.get(endpoint)
    if not key:
        return None
    val = counts.get(key, 0)
    return int(val) if val else None
