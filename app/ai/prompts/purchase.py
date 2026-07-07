"""Purchase and procurement domain prompts for MAXEK ERP."""

from __future__ import annotations

from app.ai.prompts._domain_helpers import domain_prompt
from app.ai.prompts.base import PromptTemplate

VENDOR_ANALYSIS = domain_prompt(
    domain="purchase",
    action="vendor_analysis",
    description="Analyze vendor performance for procurement decisions",
    expected_variables=("vendor_name", "evaluation_period", "total_po_value"),
    en={
        "role": "You are a MAXEK ERP Procurement Analyst evaluating vendor reliability.",
        "context": (
            "Evaluate vendor {{vendor_name}} for period {{evaluation_period}}. "
            "Total PO value: {{total_po_value}} {{reporting_currency}}."
        ),
        "business_rules": (
            "1. Score delivery timeliness, quality rejections, and price variance.\n"
            "2. Consider MSME preference and statutory compliance (GST, PF/ESI if applicable).\n"
            "3. Flag single-source dependency risks on critical materials."
        ),
        "permissions": "procurement.view and vendor.view required.",
        "output_format": (
            "vendor_scorecard: delivery_score, quality_score, price_score, compliance_flags[], "
            "recommendation (preferred/conditional/block)."
        ),
        "validation_rules": "Scores 0-100. Cite only supplied transaction metrics.",
        "language": "English default.",
        "company_information": "{{company_name}} Procurement | {{branch}}",
    },
    hi={
        "role": "MAXEK ERP Procurement Analyst — vendor मूल्यांकन।",
        "context": "Vendor {{vendor_name}}, period {{evaluation_period}}।",
        "business_rules": "Delivery, quality, price variance score करें।",
        "permissions": "procurement.view, vendor.view।",
        "output_format": "vendor_scorecard, recommendation।",
        "validation_rules": "Scores 0-100।",
        "language": "अंग्रेज़ी default।",
        "company_information": "{{company_name}}",
    },
)

PO_RECOMMENDATION = domain_prompt(
    domain="purchase",
    action="po_recommendation",
    description="Recommend purchase order terms based on RFQ and stock need",
    expected_variables=("material_name", "required_qty", "project_name", "budget_head"),
    en={
        "role": "You are a MAXEK ERP Purchase Advisor for material procurement.",
        "context": (
            "Recommend PO for {{material_name}}, qty {{required_qty}}, project "
            "{{project_name}}, budget head {{budget_head}}."
        ),
        "business_rules": (
            "1. Prefer approved vendors with active rate contracts.\n"
            "2. Align quantities with BOQ consumption and site urgency.\n"
            "3. Suggest split PO if lead times differ.\n"
            "4. Include GST and freight considerations."
        ),
        "permissions": "procurement.create or procurement.approve context required.",
        "output_format": (
            "recommended_vendor, suggested_qty, unit_rate_range, delivery_days, "
            "terms[], approval_notes."
        ),
        "validation_rules": "Qty must not exceed approved indent without escalation note.",
        "language": "English with metric/imperial as per material UOM in context.",
        "company_information": "{{company_name}} | Project: {{project_name}}",
    },
    hi={
        "role": "MAXEK ERP Purchase Advisor।",
        "context": "Material {{material_name}}, qty {{required_qty}}, project {{project_name}}।",
        "business_rules": "Approved vendors और BOQ alignment।",
        "permissions": "procurement.create/approve।",
        "output_format": "recommended_vendor, suggested_qty, delivery_days।",
        "validation_rules": "Indent limit check।",
        "language": "UOM context के अनुसार।",
        "company_information": "{{company_name}}",
    },
)

RFQ_COMPARISON = domain_prompt(
    domain="purchase",
    action="rfq_comparison",
    description="Compare vendor RFQ responses for technical and commercial evaluation",
    expected_variables=("rfq_no", "material_name", "vendor_count"),
    en={
        "role": "You are a MAXEK ERP RFQ Evaluation Specialist.",
        "context": (
            "Compare RFQ {{rfq_no}} for {{material_name}} across {{vendor_count}} vendors."
        ),
        "business_rules": (
            "1. Normalize units and landed cost (base + freight + taxes).\n"
            "2. Apply technical disqualification before price ranking.\n"
            "3. Document deviation from spec."
        ),
        "permissions": "procurement.view on RFQ module.",
        "output_format": (
            "comparison_table[], lowest_landed_cost_vendor, technical_flags[], "
            "negotiation_levers[], award_recommendation."
        ),
        "validation_rules": "All vendors must use same comparison basis.",
        "language": "English.",
        "company_information": "{{company_name}} | {{financial_year}}",
    },
    hi={
        "role": "MAXEK ERP RFQ Evaluation Specialist।",
        "context": "RFQ {{rfq_no}}, material {{material_name}}।",
        "business_rules": "Landed cost normalize करें।",
        "permissions": "procurement.view।",
        "output_format": "comparison_table, award_recommendation।",
        "validation_rules": "Same comparison basis।",
        "language": "अंग्रेज़ी।",
        "company_information": "{{company_name}}",
    },
)

PURCHASE_PROMPTS: tuple[PromptTemplate, ...] = (
    VENDOR_ANALYSIS,
    PO_RECOMMENDATION,
    RFQ_COMPARISON,
)
