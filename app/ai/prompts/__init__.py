"""Enterprise Prompt Management public API (MODULE-020).

Usage::

    from app.ai.prompts import get_prompt, list_prompts

    text = get_prompt(
        "sales",
        "quotation_summary",
        language="en",
        variables={
            "quotation_no": "QT-2025-001",
            "client_name": "NHAI",
            "project_name": "Highway Package 12",
            "quotation_amount": "4.5 Cr",
        },
    )
"""

from __future__ import annotations

from typing import Any

from app.ai.prompts.analytics import ANALYTICS_PROMPTS
from app.ai.prompts.base import (
    DEFAULT_LANGUAGE,
    REQUIRED_SECTIONS,
    SUPPORTED_LANGUAGES,
    PromptMetadataStore,
    PromptNotFoundError,
    PromptRegistry,
    PromptTemplate,
    PromptValidationError,
    PromptVersion,
    substitute_variables,
)
from app.ai.prompts.crm import CRM_PROMPTS
from app.ai.prompts.document import DOCUMENT_PROMPTS
from app.ai.prompts.finance import FINANCE_PROMPTS
from app.ai.prompts.hr import HR_PROMPTS
from app.ai.prompts.inventory import INVENTORY_PROMPTS
from app.ai.prompts.project import PROJECT_PROMPTS
from app.ai.prompts.purchase import PURCHASE_PROMPTS
from app.ai.prompts.sales import SALES_PROMPTS
from app.ai.prompts.system import SYSTEM_PROMPTS
from app.ai.prompts.tender import TENDER_PROMPTS

# All registered prompt bundles — order: system first (inheritance root).
ALL_PROMPT_BUNDLES: tuple[tuple[PromptTemplate, ...], ...] = (
    SYSTEM_PROMPTS,
    SALES_PROMPTS,
    PURCHASE_PROMPTS,
    INVENTORY_PROMPTS,
    FINANCE_PROMPTS,
    CRM_PROMPTS,
    HR_PROMPTS,
    PROJECT_PROMPTS,
    TENDER_PROMPTS,
    DOCUMENT_PROMPTS,
    ANALYTICS_PROMPTS,
)

_REGISTERED = False


def register_all_prompts(*, force: bool = False) -> int:
    """Register all domain prompts into :class:`PromptRegistry`.

    Returns the number of templates registered.
    """
    global _REGISTERED
    if _REGISTERED and not force:
        return sum(len(bundle) for bundle in ALL_PROMPT_BUNDLES)

    if force:
        PromptRegistry.clear()

    count = 0
    for bundle in ALL_PROMPT_BUNDLES:
        for template in bundle:
            PromptRegistry.register(template)
            count += 1

    _REGISTERED = True
    return count


def get_prompt(
    domain: str,
    action: str,
    *,
    version: str | PromptVersion | None = None,
    language: str = DEFAULT_LANGUAGE,
    variables: dict[str, Any] | None = None,
) -> str:
    """Resolve and render a prompt by domain and action."""
    register_all_prompts()
    return PromptRegistry.render(
        domain,
        action,
        version=version,
        language=language,
        variables=variables,
    )


def get_prompt_template(
    domain: str,
    action: str,
    version: str | PromptVersion | None = None,
) -> PromptTemplate:
    """Return the raw template object for inspection or custom rendering."""
    register_all_prompts()
    return PromptRegistry.get_template(domain, action, version)


def list_prompts(domain: str | None = None) -> list[dict[str, Any]]:
    """List registered prompt metadata, optionally filtered by domain."""
    register_all_prompts()
    items = PromptRegistry.list_templates()
    if domain is not None:
        domain_key = domain.strip().lower()
        items = [item for item in items if item["domain"] == domain_key]
    return sorted(items, key=lambda x: (x["domain"], x["action"]))


# Auto-register on import so AI core can resolve prompts immediately.
register_all_prompts()

__all__ = [
    "ALL_PROMPT_BUNDLES",
    "DEFAULT_LANGUAGE",
    "REQUIRED_SECTIONS",
    "SUPPORTED_LANGUAGES",
    "PromptMetadataStore",
    "PromptNotFoundError",
    "PromptRegistry",
    "PromptTemplate",
    "PromptValidationError",
    "PromptVersion",
    "get_prompt",
    "get_prompt_template",
    "list_prompts",
    "register_all_prompts",
    "substitute_variables",
]
