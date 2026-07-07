"""Request-type detection and routing to AI modules."""

from __future__ import annotations

import re
from typing import Any

from app.ai.registry import AIModuleRegistry, AIRequest, get_default_registry

# Explicit request_type → registry module key
REQUEST_TYPE_ROUTES: dict[str, str] = {
    "generate_report": "analytics_ai",
    "dashboard_insight": "analytics_ai",
    "kpi_analysis": "analytics_ai",
    "predict_stock": "inventory_ai",
    "stock_alert": "inventory_ai",
    "inventory_summary": "inventory_ai",
    "summarize_project": "project_ai",
    "analyze_boq": "project_ai",
    "project_health": "project_ai",
    "read_invoice": "finance_ai",
    "ledger_insight": "finance_ai",
    "cashflow_summary": "finance_ai",
    "tender_recommendation": "tender_ai",
    "bid_analysis": "tender_ai",
    "tender_summary": "tender_ai",
    "vendor_analysis": "purchase_ai",
    "purchase_recommendation": "purchase_ai",
    "po_insight": "purchase_ai",
    "client_insight": "sales_ai",
    "sales_forecast": "sales_ai",
    "crm_summary": "sales_ai",
    "workforce_summary": "hr_ai",
    "attendance_insight": "hr_ai",
    "payroll_insight": "hr_ai",
    "summarize_document": "document_ai",
    "extract_clauses": "document_ai",
    "document_qa": "document_ai",
}

# Keyword patterns (order matters — first match wins)
_KEYWORD_ROUTES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(generate|build|create)\s+report\b", re.I), "analytics_ai"),
    (re.compile(r"\b(kpi|analytics|dashboard)\b", re.I), "analytics_ai"),
    (re.compile(r"\b(predict|forecast)\s+stock\b", re.I), "inventory_ai"),
    (re.compile(r"\b(inventory|stock|reorder)\b", re.I), "inventory_ai"),
    (re.compile(r"\b(summarize|summary)\s+project\b", re.I), "project_ai"),
    (re.compile(r"\b(analyze|analysis)\s+boq\b", re.I), "project_ai"),
    (re.compile(r"\b(project|boq|dpr)\b", re.I), "project_ai"),
    (re.compile(r"\b(read|parse|scan)\s+invoice\b", re.I), "finance_ai"),
    (re.compile(r"\b(invoice|ledger|payment|receipt|gst)\b", re.I), "finance_ai"),
    (re.compile(r"\b(tender|bid|rfq)\b", re.I), "tender_ai"),
    (re.compile(r"\b(vendor|supplier|purchase\s+order|po)\b", re.I), "purchase_ai"),
    (re.compile(r"\b(client|crm|sales|billing)\b", re.I), "sales_ai"),
    (re.compile(r"\b(hr|payroll|attendance|employee|workforce)\b", re.I), "hr_ai"),
    (re.compile(r"\b(document|contract|agreement|clause)\b", re.I), "document_ai"),
)


def normalize_request_type(value: str | None) -> str:
    return (value or "").strip().lower().replace(" ", "_").replace("-", "_")


def detect_request_type(request: AIRequest) -> str:
    """Resolve the effective request type from explicit field or prompt keywords."""
    explicit = normalize_request_type(request.request_type)
    if explicit:
        return explicit

    prompt = (request.prompt or "").strip().lower()
    if not prompt:
        return "general"

    for pattern, _module_key in _KEYWORD_ROUTES:
        if pattern.search(prompt):
            matched = pattern.pattern
            # Derive a readable type from the pattern's primary verb/noun
            for route_type in REQUEST_TYPE_ROUTES:
                if route_type.replace("_", " ") in prompt or route_type in prompt:
                    return route_type
            if "report" in matched:
                return "generate_report"
            if "stock" in matched:
                return "predict_stock"
            if "project" in matched:
                return "summarize_project"
            if "boq" in matched:
                return "analyze_boq"
            if "invoice" in matched:
                return "read_invoice"
            if "tender" in matched or "bid" in matched:
                return "tender_recommendation"
            if "vendor" in matched or "purchase" in matched:
                return "vendor_analysis"
            if "client" in matched or "sales" in matched:
                return "crm_summary"
            if "hr" in matched or "payroll" in matched:
                return "workforce_summary"
            if "document" in matched:
                return "summarize_document"
            return "general"

    return "general"


def resolve_module_key(
    request: AIRequest,
    *,
    registry: AIModuleRegistry | None = None,
) -> tuple[str, str]:
    """
    Return (module_key, request_type) for the given request.

    Falls back to analytics_ai for unrecognized general queries.
    """
    reg = registry or get_default_registry()
    request_type = detect_request_type(request)

    if request_type in REQUEST_TYPE_ROUTES:
        return REQUEST_TYPE_ROUTES[request_type], request_type

    prompt = request.prompt or ""
    for pattern, module_key in _KEYWORD_ROUTES:
        if pattern.search(prompt):
            return module_key, request_type

    if request_type == "general":
        return "analytics_ai", request_type

    # Last resort: map to analytics
    return "analytics_ai", request_type


def route_request(
    request: AIRequest,
    *,
    registry: AIModuleRegistry | None = None,
) -> dict[str, Any]:
    """Produce routing metadata without executing the module."""
    reg = registry or get_default_registry()
    module_key, request_type = resolve_module_key(request, registry=reg)
    module = reg.require(module_key)
    return {
        "module_key": module_key,
        "display_name": module.display_name,
        "request_type": request_type,
        "erp_module_name": module.erp_module_name,
        "erp_screen_name": module.erp_screen_name,
    }
