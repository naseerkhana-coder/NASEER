"""Enterprise prompt template foundation for MAXEK ERP AI (MODULE-020).

Provides reusable, versioned, multilingual prompt templates with inheritance,
variable substitution, and strict section validation. No external API calls.
"""

from __future__ import annotations

import re
import sqlite3
from abc import ABC
from dataclasses import dataclass, field
from typing import Any, ClassVar, Iterator

# Canonical section keys — every prompt template must define all eight.
REQUIRED_SECTIONS: tuple[str, ...] = (
    "role",
    "context",
    "business_rules",
    "permissions",
    "output_format",
    "validation_rules",
    "language",
    "company_information",
)

SECTION_LABELS: dict[str, str] = {
    "role": "Role",
    "context": "Context",
    "business_rules": "Business Rules",
    "permissions": "Permissions",
    "output_format": "Output Format",
    "validation_rules": "Validation Rules",
    "language": "Language",
    "company_information": "Company Information",
}

SUPPORTED_LANGUAGES: tuple[str, ...] = ("en", "hi")
DEFAULT_LANGUAGE = "en"
DEFAULT_FALLBACK_LANGUAGE = "en"

# Placeholders commonly injected from ERP context.
DEFAULT_COMPANY_VARIABLES: tuple[str, ...] = (
    "company_name",
    "company_gstin",
    "company_address",
    "company_phone",
    "user_name",
    "user_role",
    "department",
    "branch",
    "financial_year",
    "reporting_currency",
)

_DOUBLE_BRACE_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")
_SINGLE_BRACE_PATTERN = re.compile(r"(?<!\{)\{([a-zA-Z_][a-zA-Z0-9_]*)\}(?!\})")


class PromptError(Exception):
    """Base error for prompt management."""


class PromptValidationError(PromptError):
    """Raised when a prompt template fails section or variable validation."""


class PromptNotFoundError(PromptError):
    """Raised when no prompt matches domain, action, and version."""


@dataclass(frozen=True, order=True)
class PromptVersion:
    """Semantic prompt version (major.minor.patch)."""

    major: int
    minor: int
    patch: int

    def __str__(self) -> str:
        return f"v{self.major}.{self.minor}.{self.patch}"

    @classmethod
    def parse(cls, value: str) -> PromptVersion:
        cleaned = value.strip().lower()
        if cleaned.startswith("v"):
            cleaned = cleaned[1:]
        parts = cleaned.split(".")
        if len(parts) != 3:
            raise ValueError(f"Invalid prompt version format: {value!r}")
        try:
            major, minor, patch = (int(p) for p in parts)
        except ValueError as exc:
            raise ValueError(f"Invalid prompt version format: {value!r}") from exc
        return cls(major=major, minor=minor, patch=patch)


@dataclass
class PromptSections:
    """Eight mandatory sections for a prompt in one language."""

    role: str
    context: str
    business_rules: str
    permissions: str
    output_format: str
    validation_rules: str
    language: str
    company_information: str

    def validate(self, *, language_code: str, template_id: str) -> None:
        """Ensure every required section is non-empty."""
        for key in REQUIRED_SECTIONS:
            value = getattr(self, key, None)
            if value is None or not str(value).strip():
                raise PromptValidationError(
                    f"Prompt {template_id!r} [{language_code}] missing required section: {key!r}"
                )

    def as_dict(self) -> dict[str, str]:
        return {key: getattr(self, key) for key in REQUIRED_SECTIONS}

    def merge(self, override: PromptSections | None) -> PromptSections:
        """Return a copy with non-empty fields from *override* applied."""
        if override is None:
            return PromptSections(**self.as_dict())
        merged = self.as_dict()
        for key in REQUIRED_SECTIONS:
            value = getattr(override, key, "")
            if value and str(value).strip():
                merged[key] = value
        return PromptSections(**merged)


@dataclass
class PromptTemplate(ABC):
    """Versioned, multilingual prompt template with optional parent inheritance."""

    domain: str
    action: str
    version: PromptVersion
    translations: dict[str, PromptSections]
    parent: PromptTemplate | None = None
    description: str = ""
    expected_variables: tuple[str, ...] = field(default_factory=tuple)

    def template_id(self) -> str:
        return f"{self.domain}.{self.action}"

    def validate_structure(self) -> None:
        """Validate translations and inheritance chain."""
        if not self.translations:
            raise PromptValidationError(
                f"Prompt {self.template_id()!r} has no language translations"
            )
        if self.parent is not None:
            self.parent.validate_structure()
            for lang in self.translations:
                self.resolve_sections(lang).validate(
                    language_code=lang,
                    template_id=self.template_id(),
                )
        else:
            for lang, sections in self.translations.items():
                sections.validate(language_code=lang, template_id=self.template_id())

    def resolve_sections(self, language: str) -> PromptSections:
        """Merge parent chain then pick language with fallback."""
        base = PromptSections(
            role="",
            context="",
            business_rules="",
            permissions="",
            output_format="",
            validation_rules="",
            language="",
            company_information="",
        )
        if self.parent is not None:
            base = self.parent.resolve_sections(language)

        lang = language if language in self.translations else DEFAULT_FALLBACK_LANGUAGE
        if lang not in self.translations:
            available = ", ".join(sorted(self.translations))
            raise PromptValidationError(
                f"Prompt {self.template_id()!r} has no translation for {language!r} "
                f"(available: {available})"
            )
        return base.merge(self.translations[lang])

    def render(
        self,
        *,
        language: str = DEFAULT_LANGUAGE,
        variables: dict[str, Any] | None = None,
    ) -> str:
        """Build the final prompt string with variables substituted."""
        self.validate_structure()
        sections = self.resolve_sections(language)
        merged_vars = _default_variables()
        if variables:
            merged_vars.update(variables)
        _validate_expected_variables(self.expected_variables, merged_vars, self.template_id())

        parts: list[str] = []
        for key in REQUIRED_SECTIONS:
            label = SECTION_LABELS[key]
            content = substitute_variables(getattr(sections, key), merged_vars)
            parts.append(f"## {label}\n{content.strip()}")
        return "\n\n".join(parts)

    def metadata(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "action": self.action,
            "version": str(self.version),
            "description": self.description,
            "languages": sorted(self.translations.keys()),
            "expected_variables": list(self.expected_variables),
            "parent": self.parent.template_id() if self.parent else None,
        }


def substitute_variables(text: str, variables: dict[str, Any]) -> str:
    """Replace ``{{var}}`` and ``{var}`` placeholders (word identifiers only)."""

    def _replace_double(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in variables:
            return match.group(0)
        return str(variables[key])

    def _replace_single(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in variables:
            return match.group(0)
        return str(variables[key])

    result = _DOUBLE_BRACE_PATTERN.sub(_replace_double, text)
    return _SINGLE_BRACE_PATTERN.sub(_replace_single, result)


def _default_variables() -> dict[str, Any]:
    return {
        "company_name": "MAXEK Construction Pvt Ltd",
        "company_gstin": "GSTIN-PLACEHOLDER",
        "company_address": "Corporate Office, India",
        "company_phone": "+91-0000000000",
        "user_name": "ERP User",
        "user_role": "Authorized User",
        "department": "Operations",
        "branch": "Head Office",
        "financial_year": "2025-26",
        "reporting_currency": "INR",
    }


def _validate_expected_variables(
    expected: tuple[str, ...],
    provided: dict[str, Any],
    template_id: str,
) -> None:
    missing = [name for name in expected if name not in provided]
    if missing:
        raise PromptValidationError(
            f"Prompt {template_id!r} missing required variables: {', '.join(missing)}"
        )


class PromptRegistry:
    """In-memory registry of prompt templates keyed by domain, action, version."""

    _templates: ClassVar[dict[tuple[str, str, str], PromptTemplate]] = {}
    _latest: ClassVar[dict[tuple[str, str], PromptVersion]] = {}

    @classmethod
    def register(cls, template: PromptTemplate) -> None:
        template.validate_structure()
        key = (template.domain, template.action, str(template.version))
        cls._templates[key] = template
        latest_key = (template.domain, template.action)
        current = cls._latest.get(latest_key)
        if current is None or template.version > current:
            cls._latest[latest_key] = template.version

    @classmethod
    def get_template(
        cls,
        domain: str,
        action: str,
        version: str | PromptVersion | None = None,
    ) -> PromptTemplate:
        domain_key = domain.strip().lower()
        action_key = action.strip().lower()
        if version is None:
            latest = cls._latest.get((domain_key, action_key))
            if latest is None:
                raise PromptNotFoundError(
                    f"No prompt registered for domain={domain_key!r}, action={action_key!r}"
                )
            version_str = str(latest)
        elif isinstance(version, PromptVersion):
            version_str = str(version)
        else:
            version_str = str(PromptVersion.parse(version))

        template = cls._templates.get((domain_key, action_key, version_str))
        if template is None:
            raise PromptNotFoundError(
                f"Prompt not found: domain={domain_key!r}, action={action_key!r}, "
                f"version={version_str!r}"
            )
        return template

    @classmethod
    def render(
        cls,
        domain: str,
        action: str,
        *,
        version: str | PromptVersion | None = None,
        language: str = DEFAULT_LANGUAGE,
        variables: dict[str, Any] | None = None,
    ) -> str:
        template = cls.get_template(domain, action, version)
        return template.render(language=language, variables=variables)

    @classmethod
    def list_templates(cls) -> list[dict[str, Any]]:
        return [t.metadata() for t in cls._templates.values()]

    @classmethod
    def iter_templates(cls) -> Iterator[PromptTemplate]:
        yield from cls._templates.values()

    @classmethod
    def clear(cls) -> None:
        """Reset registry — intended for tests only."""
        cls._templates.clear()
        cls._latest.clear()


class PromptMetadataStore:
    """Optional SQLite persistence for prompt version metadata audit trail."""

    @staticmethod
    def ensure_schema(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_prompt_metadata(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL,
                action TEXT NOT NULL,
                version TEXT NOT NULL,
                description TEXT,
                languages TEXT,
                parent_id TEXT,
                registered_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(domain, action, version)
            )
            """
        )
        conn.commit()

    @classmethod
    def sync_registry(cls, conn: sqlite3.Connection) -> int:
        """Persist current in-memory registry metadata; returns rows upserted."""
        cls.ensure_schema(conn)
        count = 0
        for template in PromptRegistry.iter_templates():
            conn.execute(
                """
                INSERT INTO ai_prompt_metadata(domain, action, version, description, languages, parent_id)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(domain, action, version) DO UPDATE SET
                    description=excluded.description,
                    languages=excluded.languages,
                    parent_id=excluded.parent_id
                """,
                (
                    template.domain,
                    template.action,
                    str(template.version),
                    template.description,
                    ",".join(sorted(template.translations.keys())),
                    template.parent.template_id() if template.parent else None,
                ),
            )
            count += 1
        conn.commit()
        return count
