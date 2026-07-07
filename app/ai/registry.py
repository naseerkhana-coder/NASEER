"""AI module registry and prompt registry bridge (MODULE-019 / MODULE-020)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

from app.ai.config import AIEngineConfig
from app.ai.prompts import (
    PromptTemplate,
    get_prompt,
    list_prompts,
    register_all_prompts,
)


# ---------------------------------------------------------------------------
# MODULE-020 — prompt registry bridge (backward compatible)
# ---------------------------------------------------------------------------


class AIRegistry:
    """Central registry bridging AI core components and prompt templates."""

    @staticmethod
    def register_prompts() -> int:
        return register_all_prompts()

    @staticmethod
    def resolve_prompt(
        domain: str,
        action: str,
        *,
        version: str | None = None,
        language: str = "en",
        variables: dict[str, Any] | None = None,
    ) -> str:
        return get_prompt(
            domain,
            action,
            version=version,
            language=language,
            variables=variables,
        )

    @staticmethod
    def get_template(domain: str, action: str, version: str | None = None) -> PromptTemplate:
        register_all_prompts()
        from app.ai.prompts.base import PromptRegistry

        return PromptRegistry.get_template(domain, action, version)

    @staticmethod
    def list_prompts(domain: str | None = None) -> list[dict[str, Any]]:
        return list_prompts(domain)


# ---------------------------------------------------------------------------
# MODULE-019 — pluggable AI domain modules
# ---------------------------------------------------------------------------


@dataclass
class AIRequest:
    """Normalized inbound AI request for the core engine."""

    prompt: str
    request_type: str | None = None
    user_id: int | None = None
    company_id: int | None = None
    department_id: int | None = None
    branch_id: int | None = None
    project_id: int | None = None
    client_id: int | None = None
    vendor_id: int | None = None
    document_id: int | None = None
    module_name: str = ""
    screen_name: str = ""
    action: str = "view"
    record_table: str = ""
    record_id: int | None = None
    session_id: str = ""
    is_admin: bool = False
    is_platform_super_admin: bool = False
    context_hints: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    prompt_variables: dict[str, Any] = field(default_factory=dict)


@dataclass
class AIResponse:
    """Normalized outbound AI response from the core engine."""

    success: bool
    module_key: str
    request_type: str
    status: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    execution_ms: int = 0
    error: str | None = None


class BaseAIModule(ABC):
    """Base class for all MAXEK AI domain modules."""

    key: ClassVar[str]
    display_name: ClassVar[str]
    erp_module_name: ClassVar[str]
    erp_screen_name: ClassVar[str]
    supported_request_types: ClassVar[tuple[str, ...]]

    @abstractmethod
    def execute(
        self,
        request: AIRequest,
        *,
        context: dict[str, Any],
        memory_snapshot: dict[str, Any],
        config: AIEngineConfig,
    ) -> dict[str, Any]:
        """Run module logic and return a structured payload."""


def _stub_payload(
    module_key: str,
    request: AIRequest,
    *,
    capability: str,
    hints: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "module": module_key,
        "capability": capability,
        "request_type": request.request_type or "general",
        "prompt_preview": (request.prompt or "")[:240],
        "status": "stub_completed",
        "hints": hints or [],
        "note": "AI Core stub response — connect an LLM provider to enable live inference.",
    }


class SalesAIModule(BaseAIModule):
    key = "sales_ai"
    display_name = "SalesAI"
    erp_module_name = "Accounts"
    erp_screen_name = "client_master"
    supported_request_types = ("client_insight", "sales_forecast", "crm_summary")

    def execute(self, request, *, context, memory_snapshot, config):
        return _stub_payload(self.key, request, capability="sales_and_crm_analysis", hints=["client pipeline"])


class PurchaseAIModule(BaseAIModule):
    key = "purchase_ai"
    display_name = "PurchaseAI"
    erp_module_name = "Store"
    erp_screen_name = "store"
    supported_request_types = ("vendor_analysis", "purchase_recommendation", "po_insight")

    def execute(self, request, *, context, memory_snapshot, config):
        return _stub_payload(self.key, request, capability="procurement_analysis", hints=["vendor scorecard"])


class InventoryAIModule(BaseAIModule):
    key = "inventory_ai"
    display_name = "InventoryAI"
    erp_module_name = "Store"
    erp_screen_name = "store"
    supported_request_types = ("predict_stock", "stock_alert", "inventory_summary")

    def execute(self, request, *, context, memory_snapshot, config):
        return _stub_payload(self.key, request, capability="inventory_forecasting", hints=["reorder levels"])


class HRAIModule(BaseAIModule):
    key = "hr_ai"
    display_name = "HRAI"
    erp_module_name = "HR"
    erp_screen_name = "workforce_dashboard"
    supported_request_types = ("workforce_summary", "attendance_insight", "payroll_insight")

    def execute(self, request, *, context, memory_snapshot, config):
        return _stub_payload(self.key, request, capability="workforce_analysis", hints=["headcount"])


class FinanceAIModule(BaseAIModule):
    key = "finance_ai"
    display_name = "FinanceAI"
    erp_module_name = "Accounts"
    erp_screen_name = "accounts_hub"
    supported_request_types = ("read_invoice", "ledger_insight", "cashflow_summary")

    def execute(self, request, *, context, memory_snapshot, config):
        return _stub_payload(self.key, request, capability="financial_analysis", hints=["invoices"])


class ProjectAIModule(BaseAIModule):
    key = "project_ai"
    display_name = "ProjectAI"
    erp_module_name = "Projects"
    erp_screen_name = "project_master"
    supported_request_types = ("summarize_project", "analyze_boq", "project_health")

    def execute(self, request, *, context, memory_snapshot, config):
        return _stub_payload(self.key, request, capability="project_intelligence", hints=["BOQ", "DPR"])


class TenderAIModule(BaseAIModule):
    key = "tender_ai"
    display_name = "TenderAI"
    erp_module_name = "Projects"
    erp_screen_name = "boq_management"
    supported_request_types = ("tender_recommendation", "bid_analysis", "tender_summary")

    def execute(self, request, *, context, memory_snapshot, config):
        return _stub_payload(self.key, request, capability="tender_intelligence", hints=["bid competitiveness"])


class DocumentAIModule(BaseAIModule):
    key = "document_ai"
    display_name = "DocumentAI"
    erp_module_name = "Settings"
    erp_screen_name = "document_management"
    supported_request_types = ("summarize_document", "extract_clauses", "document_qa")

    def execute(self, request, *, context, memory_snapshot, config):
        return _stub_payload(self.key, request, capability="document_understanding", hints=["summaries"])


class AnalyticsAIModule(BaseAIModule):
    key = "analytics_ai"
    display_name = "AnalyticsAI"
    erp_module_name = "Reports"
    erp_screen_name = "reports"
    supported_request_types = ("generate_report", "dashboard_insight", "kpi_analysis")

    def execute(self, request, *, context, memory_snapshot, config):
        return _stub_payload(self.key, request, capability="cross_module_analytics", hints=["KPIs"])


_BUILTIN_MODULES: tuple[type[BaseAIModule], ...] = (
    SalesAIModule,
    PurchaseAIModule,
    InventoryAIModule,
    HRAIModule,
    FinanceAIModule,
    ProjectAIModule,
    TenderAIModule,
    DocumentAIModule,
    AnalyticsAIModule,
)


class AIModuleRegistry:
    """Registry of AI modules with registration API for future expansion."""

    def __init__(self) -> None:
        self._modules: dict[str, BaseAIModule] = {}
        for module_cls in _BUILTIN_MODULES:
            self.register(module_cls())

    def register(self, module: BaseAIModule, *, replace: bool = False) -> None:
        key = module.key
        if key in self._modules and not replace:
            raise ValueError(f"AI module '{key}' is already registered.")
        self._modules[key] = module

    def unregister(self, key: str) -> None:
        self._modules.pop(key, None)

    def get(self, key: str) -> BaseAIModule | None:
        return self._modules.get(key)

    def require(self, key: str) -> BaseAIModule:
        module = self.get(key)
        if module is None:
            raise KeyError(f"AI module '{key}' is not registered.")
        return module

    def list_modules(self) -> list[dict[str, Any]]:
        return [
            {
                "key": module.key,
                "display_name": module.display_name,
                "erp_module_name": module.erp_module_name,
                "erp_screen_name": module.erp_screen_name,
                "supported_request_types": list(module.supported_request_types),
            }
            for module in self._modules.values()
        ]

    def keys(self) -> list[str]:
        return list(self._modules.keys())


_default_registry: AIModuleRegistry | None = None


def get_default_registry() -> AIModuleRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = AIModuleRegistry()
    return _default_registry


# ---------------------------------------------------------------------------
# MODULE-020 — request-type → enterprise prompt mapping
# ---------------------------------------------------------------------------

REQUEST_TYPE_PROMPT_MAP: dict[str, tuple[str, str]] = {
    "generate_report": ("analytics", "generate_report"),
    "dashboard_insight": ("analytics", "kpi_analysis"),
    "kpi_analysis": ("analytics", "kpi_analysis"),
    "predict_stock": ("inventory", "stock_prediction"),
    "stock_alert": ("inventory", "reorder_alert"),
    "inventory_summary": ("inventory", "consumption_variance"),
    "summarize_project": ("project", "project_summary"),
    "analyze_boq": ("project", "milestone_status"),
    "project_health": ("project", "delay_risk"),
    "read_invoice": ("finance", "invoice_read"),
    "ledger_insight": ("finance", "payment_summary"),
    "cashflow_summary": ("finance", "cashflow_snapshot"),
    "tender_recommendation": ("tender", "tender_recommendation"),
    "bid_analysis": ("tender", "bid_analysis"),
    "tender_summary": ("tender", "compliance_check"),
    "vendor_analysis": ("purchase", "vendor_analysis"),
    "purchase_recommendation": ("purchase", "po_recommendation"),
    "po_insight": ("purchase", "rfq_comparison"),
    "client_insight": ("sales", "client_follow_up"),
    "sales_forecast": ("sales", "pipeline_forecast"),
    "crm_summary": ("sales", "quotation_summary"),
    "workforce_summary": ("hr", "attendance_summary"),
    "attendance_insight": ("hr", "attendance_summary"),
    "payroll_insight": ("hr", "payroll_query"),
    "summarize_document": ("document", "document_summarize"),
    "extract_clauses": ("document", "extract_fields"),
    "document_qa": ("document", "classify_document"),
}

MODULE_KEY_PROMPT_DEFAULTS: dict[str, tuple[str, str]] = {
    "sales_ai": ("sales", "quotation_summary"),
    "purchase_ai": ("purchase", "vendor_analysis"),
    "inventory_ai": ("inventory", "stock_prediction"),
    "finance_ai": ("finance", "invoice_read"),
    "hr_ai": ("hr", "attendance_summary"),
    "project_ai": ("project", "project_summary"),
    "tender_ai": ("tender", "tender_recommendation"),
    "document_ai": ("document", "document_summarize"),
    "analytics_ai": ("analytics", "generate_report"),
}


def _prompt_variables_from_context(
    request: AIRequest,
    context: dict[str, Any],
) -> dict[str, Any]:
    variables: dict[str, Any] = dict(request.prompt_variables)
    company = context.get("company") or {}
    user = context.get("user") or {}
    variables.setdefault(
        "company_name",
        company.get("company_name") or company.get("name") or "MAXEK Construction Pvt Ltd",
    )
    variables.setdefault("company_gstin", company.get("gstin") or company.get("company_gstin") or "")
    variables.setdefault("user_name", user.get("username") or user.get("staff_name") or "ERP User")
    variables.setdefault("user_role", user.get("role") or user.get("designation") or "User")
    variables.setdefault("department", user.get("department") or "")
    variables.setdefault("branch", company.get("branch_name") or company.get("branch") or "Head Office")
    variables.setdefault("financial_year", context.get("financial_year") or "2025-26")
    variables.setdefault("reporting_currency", company.get("currency") or "INR")
    variables.setdefault("user_query", request.prompt)
    return variables


def _default_for_variable(name: str, request: AIRequest, context: dict[str, Any]) -> str:
    """Supply stub-safe defaults when ERP context lacks prompt variables."""
    project_bundle = context.get("project") or {}
    project_row = project_bundle.get("project") if isinstance(project_bundle, dict) else project_bundle
    if not isinstance(project_row, dict):
        project_row = {}
    defaults = {
        "material_name": "General Material",
        "current_stock": "0",
        "reorder_level": "0",
        "lead_time_days": "7",
        "project_name": project_row.get("project_name") or "Active Project",
        "forecast_days": "30",
        "quotation_no": "QT-DRAFT",
        "client_name": "Client",
        "quotation_amount": "0",
        "invoice_no": "INV-DRAFT",
        "invoice_amount": "0",
        "vendor_name": "Vendor",
        "document_title": "Document",
        "baseline_end_date": "2026-06-30",
        "forecast_end_date": "2026-09-15",
        "user_query": request.prompt,
    }
    return defaults.get(name, "N/A")


def resolve_prompt_for_request(
    request: AIRequest,
    *,
    module_key: str,
    request_type: str,
    context: dict[str, Any],
    language: str = "en",
) -> str:
    """Render enterprise system prompt for a routed AI request (MODULE-020)."""
    register_all_prompts()
    domain, action = REQUEST_TYPE_PROMPT_MAP.get(request_type) or MODULE_KEY_PROMPT_DEFAULTS.get(
        module_key, ("system", "base")
    )
    variables = _prompt_variables_from_context(request, context)
    try:
        template = AIRegistry.get_template(domain, action)
        for var in template.expected_variables:
            variables.setdefault(var, _default_for_variable(var, request, context))
        return get_prompt(domain, action, language=language, variables=variables)
    except Exception:
        base = get_prompt("system", "base", language=language, variables=variables)
        safety = get_prompt("system", "safety", language=language, variables=variables)
        return f"{base}\n\n{safety}"


def list_registered_prompts(domain: str | None = None) -> list[dict[str, Any]]:
    """List MODULE-020 prompt metadata."""
    return list_prompts(domain)
