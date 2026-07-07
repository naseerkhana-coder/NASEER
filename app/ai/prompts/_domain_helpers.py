"""Shared helpers for domain prompt module definitions."""

from __future__ import annotations

from app.ai.prompts.base import PromptSections, PromptTemplate, PromptVersion
from app.ai.prompts.system import SYSTEM_BASE_PROMPT

DOMAIN_VERSION = PromptVersion(1, 0, 0)


def domain_prompt(
    *,
    domain: str,
    action: str,
    description: str,
    en: dict[str, str],
    hi: dict[str, str],
    expected_variables: tuple[str, ...] = (),
    version: PromptVersion | None = None,
    parent: PromptTemplate | None = None,
) -> PromptTemplate:
    """Build a domain prompt with English and Hindi translations."""
    parent_template = parent if parent is not None else SYSTEM_BASE_PROMPT
    en_sections = PromptSections(**en)
    hi_sections = PromptSections(**hi)
    return PromptTemplate(
        domain=domain,
        action=action,
        version=version or DOMAIN_VERSION,
        description=description,
        parent=parent_template,
        translations={"en": en_sections, "hi": hi_sections},
        expected_variables=expected_variables,
    )
