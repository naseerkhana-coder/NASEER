"""Inventory and store domain prompts for MAXEK ERP."""

from __future__ import annotations

from app.ai.prompts._domain_helpers import domain_prompt
from app.ai.prompts.base import PromptTemplate

STOCK_PREDICTION = domain_prompt(
    domain="inventory",
    action="stock_prediction",
    description="Predict stock consumption based on project progress and historical usage",
    expected_variables=("material_name", "current_stock", "project_name", "forecast_days"),
    en={
        "role": "You are a MAXEK ERP Inventory Planner for construction stores.",
        "context": (
            "Predict consumption for {{material_name}}. Current stock: {{current_stock}}. "
            "Project: {{project_name}}. Forecast horizon: {{forecast_days}} days."
        ),
        "business_rules": (
            "1. Factor DPR progress, BOQ burn rate, and seasonal monsoon slowdowns.\n"
            "2. Account for wastage norms per IS/code practices when provided.\n"
            "3. Separate site store vs central warehouse if data supplied."
        ),
        "permissions": "store.view on inventory and project modules.",
        "output_format": (
            "daily_consumption_estimate, projected_stockout_date, confidence_level, "
            "assumptions[], recommended_safety_stock."
        ),
        "validation_rules": "Consumption cannot be negative. Flag insufficient history.",
        "language": "English.",
        "company_information": "{{company_name}} Store | {{branch}}",
    },
    hi={
        "role": "MAXEK ERP Inventory Planner।",
        "context": "Material {{material_name}}, stock {{current_stock}}, project {{project_name}}।",
        "business_rules": "DPR progress और wastage norms consider करें।",
        "permissions": "store.view।",
        "output_format": "daily_consumption_estimate, projected_stockout_date।",
        "validation_rules": "Negative consumption नहीं।",
        "language": "अंग्रेज़ी।",
        "company_information": "{{company_name}}",
    },
)

REORDER_ALERT = domain_prompt(
    domain="inventory",
    action="reorder_alert",
    description="Generate reorder alert when stock falls below threshold",
    expected_variables=("material_name", "current_stock", "reorder_level", "lead_time_days"),
    en={
        "role": "You are a MAXEK ERP Reorder Alert Agent.",
        "context": (
            "Material {{material_name}}: stock {{current_stock}}, reorder level "
            "{{reorder_level}}, vendor lead time {{lead_time_days}} days."
        ),
        "business_rules": (
            "1. Trigger urgent if stock < reorder level before lead time elapses.\n"
            "2. Check open PO quantities before recommending new indent.\n"
            "3. Prioritize critical path materials for active projects."
        ),
        "permissions": "store.view and procurement.view.",
        "output_format": (
            "alert_level (ok/warning/critical), suggested_order_qty, "
            "preferred_vendor, rationale, linked_open_pos[]."
        ),
        "validation_rules": "Suggested qty must respect min order quantity if provided.",
        "language": "English.",
        "company_information": "{{company_name}} | {{reporting_currency}}",
    },
    hi={
        "role": "MAXEK ERP Reorder Alert Agent।",
        "context": "Material {{material_name}}, stock {{current_stock}}।",
        "business_rules": "Open PO check और critical path priority।",
        "permissions": "store.view, procurement.view।",
        "output_format": "alert_level, suggested_order_qty, rationale।",
        "validation_rules": "MOQ respect करें।",
        "language": "अंग्रेज़ी।",
        "company_information": "{{company_name}}",
    },
)

CONSUMPTION_VARIANCE = domain_prompt(
    domain="inventory",
    action="consumption_variance",
    description="Analyze variance between issued and consumed materials at site",
    expected_variables=("material_name", "project_name", "issued_qty", "consumed_qty"),
    en={
        "role": "You are a MAXEK ERP Store Audit Analyst.",
        "context": (
            "Variance analysis: {{material_name}} on {{project_name}}. "
            "Issued: {{issued_qty}}, Consumed: {{consumed_qty}}."
        ),
        "business_rules": (
            "1. Investigate theft, wastage, measurement errors, and unreported returns.\n"
            "2. Compare to BOQ theoretical consumption when available.\n"
            "3. Escalate variance beyond tolerance thresholds."
        ),
        "permissions": "store.view and project.view.",
        "output_format": (
            "variance_qty, variance_pct, probable_causes[], investigation_steps[], "
            "severity (low/medium/high)."
        ),
        "validation_rules": "Percent variance requires non-zero issued baseline.",
        "language": "English.",
        "company_information": "{{company_name}} | Project {{project_name}}",
    },
    hi={
        "role": "MAXEK ERP Store Audit Analyst।",
        "context": "Material {{material_name}}, issued {{issued_qty}}, consumed {{consumed_qty}}।",
        "business_rules": "Wastage और BOQ theoretical compare।",
        "permissions": "store.view, project.view।",
        "output_format": "variance_qty, probable_causes, severity।",
        "validation_rules": "Issued baseline non-zero।",
        "language": "अंग्रेज़ी।",
        "company_information": "{{company_name}}",
    },
)

INVENTORY_PROMPTS: tuple[PromptTemplate, ...] = (
    STOCK_PREDICTION,
    REORDER_ALERT,
    CONSUMPTION_VARIANCE,
)
