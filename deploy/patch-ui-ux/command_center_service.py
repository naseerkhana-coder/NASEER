"""Management Command Center — executive dashboard aggregating treasury, project, and ops KPIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from budget_service import budget_alerts, ensure_budget_schema
from claims_service import ensure_claims_schema, get_claims_summary, list_claims
from contract_service import ensure_contract_schema, list_contracts
from equipment_costing_service import (
    ensure_equipment_costing_schema,
    get_equipment_costing_summary,
    list_equipment_with_summary,
)
from labour_productivity_service import ensure_labour_productivity_schema, get_list_summary
from profitability_service import ensure_profitability_schema, list_all_projects_profitability
from treasury_service import (
    ensure_treasury_schema,
    get_cash_flow_forecast,
    get_treasury_cash_flow_summary,
    list_bank_accounts,
    treasury_hub_stats,
)


def _table_exists(db, table: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _round2(value: float) -> float:
    return round(_safe_float(value), 2)


def _ensure_command_center_schemas(db) -> None:
    ensure_treasury_schema(db)
    ensure_budget_schema(db)
    ensure_profitability_schema(db)
    ensure_contract_schema(db)
    ensure_claims_schema(db)
    ensure_equipment_costing_schema(db)
    ensure_labour_productivity_schema(db)


def _active_projects(db) -> dict[str, Any]:
    total = db.execute("SELECT COUNT(*) AS c FROM projects").fetchone()["c"]
    active = db.execute(
        "SELECT COUNT(*) AS c FROM projects WHERE COALESCE(status, '') = 'Active'"
    ).fetchone()["c"]
    rows = [
        dict(r)
        for r in db.execute(
            """
            SELECT id, project_name, project_code, location, status, end_date
            FROM projects
            WHERE COALESCE(status, '') = 'Active'
            ORDER BY project_name
            LIMIT 12
            """
        ).fetchall()
    ]
    return {
        "total_projects": int(total),
        "active_count": int(active),
        "projects": rows,
    }


def _profitability_summary(db) -> dict[str, Any]:
    rows = list_all_projects_profitability(db, active_only=True, sync_modules=False)
    total_contract = _round2(sum(_safe_float(r.get("contract_value")) for r in rows))
    total_billing = _round2(sum(_safe_float(r.get("client_billing")) for r in rows))
    total_receipts = _round2(sum(_safe_float(r.get("receipts")) for r in rows))
    total_net_profit = _round2(sum(_safe_float(r.get("net_profit")) for r in rows))
    top = sorted(rows, key=lambda r: _safe_float(r.get("net_profit")), reverse=True)[:8]
    top_rows = [
        {
            "project_id": r["project_id"],
            "project_name": r.get("project_name") or "",
            "contract_value": _safe_float(r.get("contract_value")),
            "client_billing": _safe_float(r.get("client_billing")),
            "net_profit": _safe_float(r.get("net_profit")),
            "profit_pct": _safe_float(r.get("profit_pct")),
            "margin_on_billing": _safe_float(r.get("margin_on_billing")),
        }
        for r in top
    ]
    return {
        "project_count": len(rows),
        "total_contract": total_contract,
        "total_billing": total_billing,
        "total_receipts": total_receipts,
        "total_net_profit": total_net_profit,
        "top_projects": top_rows,
    }


def _outstanding_receivables(db) -> dict[str, Any]:
    total = 0.0
    bill_count = 0
    top_bills: list[dict] = []
    if _table_exists(db, "client_bills"):
        row = db.execute(
            """
            SELECT COALESCE(SUM(
                CASE
                    WHEN (net_payable - COALESCE(paid_amount, 0)) > 0
                    THEN (net_payable - COALESCE(paid_amount, 0))
                    ELSE 0
                END
            ), 0) AS total,
            COUNT(*) AS c
            FROM client_bills
            WHERE approval_status = 'Approved'
              AND COALESCE(bill_status, '') != 'Paid'
              AND (net_payable - COALESCE(paid_amount, 0)) > 0
            """
        ).fetchone()
        total = _safe_float(row["total"] if row else 0)
        bill_count = int(row["c"] if row else 0)
        top_bills = [
            dict(r)
            for r in db.execute(
                """
                SELECT cb.id, cb.bill_number, cb.bill_date, cb.net_payable,
                       COALESCE(cb.paid_amount, 0) AS paid_amount,
                       (cb.net_payable - COALESCE(cb.paid_amount, 0)) AS outstanding_amount,
                       p.project_name
                FROM client_bills cb
                LEFT JOIN projects p ON cb.project_id = p.id
                WHERE cb.approval_status = 'Approved'
                  AND COALESCE(cb.bill_status, '') != 'Paid'
                  AND (cb.net_payable - COALESCE(cb.paid_amount, 0)) > 0
                ORDER BY outstanding_amount DESC
                LIMIT 8
                """
            ).fetchall()
        ]
    return {
        "total": _round2(total),
        "bill_count": bill_count,
        "top_bills": top_bills,
    }


def _outstanding_payables(db) -> dict[str, Any]:
    pending_payments = 0.0
    pending_payment_count = 0
    if _table_exists(db, "bank_payments"):
        row = db.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS c
            FROM bank_payments
            WHERE approval_status != 'Approved'
            """
        ).fetchone()
        pending_payments = _safe_float(row["total"] if row else 0)
        pending_payment_count = int(row["c"] if row else 0)
    unpaid_expenses = 0.0
    unpaid_expense_count = 0
    if _table_exists(db, "account_expenses"):
        try:
            row = db.execute(
                """
                SELECT COALESCE(SUM(grand_total), 0) AS total, COUNT(*) AS c
                FROM account_expenses
                WHERE COALESCE(payment_status, '') IN ('Unpaid', 'Partially Paid', 'Draft')
                  AND approval_status = 'Approved'
                """
            ).fetchone()
            unpaid_expenses = _safe_float(row["total"] if row else 0)
            unpaid_expense_count = int(row["c"] if row else 0)
        except Exception:
            unpaid_expenses = 0.0
            unpaid_expense_count = 0
    total = _round2(pending_payments + unpaid_expenses)
    return {
        "total": total,
        "pending_payments": _round2(pending_payments),
        "pending_payment_count": pending_payment_count,
        "unpaid_expenses": _round2(unpaid_expenses),
        "unpaid_expense_count": unpaid_expense_count,
    }


def _plant_utilization(db) -> dict[str, Any]:
    try:
        from plant_service import ensure_plant_schema, plant_dashboard_stats

        ensure_plant_schema(db)
        stats = plant_dashboard_stats(db)
        total = int(stats.get("total_plants") or 0)
        active = int(stats.get("active_plants") or 0)
        utilization_pct = round((active / total) * 100, 1) if total > 0 else None
        return {
            "available": total > 0,
            "stub": False,
            "total_plants": total,
            "active_plants": active,
            "utilization_pct": utilization_pct,
            "today_production_ton": _round2(_safe_float(stats.get("today_production_ton"))),
            "today_rmc_m3": _round2(_safe_float(stats.get("today_rmc_production_m3"))),
            "open_maintenance_jobs": int(stats.get("open_maintenance_jobs") or 0),
        }
    except Exception:
        return {
            "available": False,
            "stub": True,
            "total_plants": 0,
            "active_plants": 0,
            "utilization_pct": None,
            "today_production_ton": 0.0,
            "today_rmc_m3": 0.0,
            "open_maintenance_jobs": 0,
        }


def _equipment_utilization(db) -> dict[str, Any]:
    equipment = list_equipment_with_summary(db)
    summary = get_equipment_costing_summary(db, equipment)
    total_hours = 0.0
    if _table_exists(db, "equipment_cost_entries"):
        row = db.execute(
            "SELECT COALESCE(SUM(operating_hours), 0) AS total FROM equipment_cost_entries"
        ).fetchone()
        total_hours = _safe_float(row["total"] if row else 0)
    active = int(summary.get("active_count") or 0)
    with_costs = int(summary.get("with_costs_count") or 0)
    utilization_pct = round((with_costs / active) * 100, 1) if active > 0 else None
    top_machines = sorted(
        equipment,
        key=lambda r: _safe_float(r.get("total_cost")),
        reverse=True,
    )[:6]
    return {
        **summary,
        "total_operating_hours": _round2(total_hours),
        "utilization_pct": utilization_pct,
        "top_machines": [
            {
                "id": r.get("id"),
                "equipment_name": r.get("equipment_name") or r.get("reg_no") or "—",
                "status": r.get("status"),
                "total_cost": _safe_float(r.get("total_cost")),
                "operating_hours": _safe_float(r.get("operating_hours")),
            }
            for r in top_machines
        ],
    }


def _contracts_and_claims(db) -> dict[str, Any]:
    contracts = list_contracts(db)
    claims = list_claims(db)
    claims_summary = get_claims_summary(db, claims)
    active_contracts = sum(1 for c in contracts if c.get("status") == "Active")
    return {
        "contract_count": len(contracts),
        "active_contract_count": active_contracts,
        "revised_total": _round2(sum(_safe_float(c.get("revised_value")) for c in contracts)),
        "claims": claims_summary,
    }


def get_management_command_center(db) -> dict[str, Any]:
    """Single-screen executive dashboard payload."""
    _ensure_command_center_schemas(db)
    treasury_stats = treasury_hub_stats(db)
    cash_flow_mtd = get_treasury_cash_flow_summary(db)
    forecast_7 = get_cash_flow_forecast(db, "7")
    forecast_30 = get_cash_flow_forecast(db, "30")
    try:
        budget_alert_rows = budget_alerts(db)
    except Exception:
        budget_alert_rows = []
    labour_summary = get_list_summary(db)
    bank_accounts = list_bank_accounts(db, active_only=True)

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "treasury": treasury_stats,
        "cash_flow_mtd": cash_flow_mtd,
        "cash_flow_forecast": {
            "days_7": {
                "net_position": forecast_7["net_cash_position"],
                "expected_inflows": forecast_7["expected_inflows"],
                "expected_outflows": forecast_7["expected_outflows"],
                "opening_balance": forecast_7["opening_balance"],
            },
            "days_30": {
                "net_position": forecast_30["net_cash_position"],
                "expected_inflows": forecast_30["expected_inflows"],
                "expected_outflows": forecast_30["expected_outflows"],
                "opening_balance": forecast_30["opening_balance"],
            },
        },
        "projects": _active_projects(db),
        "profitability": _profitability_summary(db),
        "receivables": _outstanding_receivables(db),
        "payables": _outstanding_payables(db),
        "bank_accounts": bank_accounts,
        "budget_overrun_count": len(budget_alert_rows),
        "budget_alerts": budget_alert_rows[:8],
        "contracts_claims": _contracts_and_claims(db),
        "plant": _plant_utilization(db),
        "equipment": _equipment_utilization(db),
        "labour": labour_summary,
    }
