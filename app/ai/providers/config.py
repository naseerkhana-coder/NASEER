"""Provider-specific configuration (MODULE-021).

Loads settings from environment variables. Credentials (API keys) must be
supplied via environment variables when real providers are enabled; they are
never logged or included in repr/to_dict output.

Environment keys:
    AI_PROVIDER          — provider id (default: mock)
    AI_MODEL             — chat/completion model name
    AI_EMBEDDING_MODEL   — embedding model name
    AI_TEMPERATURE       — sampling temperature (0.0–2.0)
    AI_MAX_TOKENS        — max output tokens
    AI_TIMEOUT           — request timeout in seconds
    AI_STREAMING_ENABLED — enable streaming responses (true/false)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

# Keys that must never appear in logs or serialized config output.
_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "api_secret",
        "openai_api_key",
        "anthropic_api_key",
        "google_api_key",
        "azure_api_key",
        "password",
        "token",
        "secret",
    }
)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class ProviderConfig:
    """Runtime configuration for AI provider selection and behaviour."""

    provider: str = "mock"
    model: str = "maxek-mock-v1"
    embedding_model: str = "maxek-mock-embed-v1"
    temperature: float = 0.4
    max_tokens: int = 4096
    timeout: float = 30.0
    streaming_enabled: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_env(cls, *, overrides: dict[str, Any] | None = None) -> ProviderConfig:
        """Build config from environment with optional overrides."""
        overrides = overrides or {}
        return cls(
            provider=str(overrides.get("provider") or os.environ.get("AI_PROVIDER", "mock")).strip().lower(),
            model=str(overrides.get("model") or os.environ.get("AI_MODEL", "maxek-mock-v1")),
            embedding_model=str(
                overrides.get("embedding_model")
                or os.environ.get("AI_EMBEDDING_MODEL", "maxek-mock-embed-v1")
            ),
            temperature=float(
                overrides.get("temperature")
                if overrides.get("temperature") is not None
                else _env_float("AI_TEMPERATURE", 0.4)
            ),
            max_tokens=int(
                overrides.get("max_tokens")
                if overrides.get("max_tokens") is not None
                else _env_int("AI_MAX_TOKENS", 4096)
            ),
            timeout=float(
                overrides.get("timeout")
                if overrides.get("timeout") is not None
                else _env_float("AI_TIMEOUT", 30.0)
            ),
            streaming_enabled=bool(
                overrides.get("streaming_enabled")
                if overrides.get("streaming_enabled") is not None
                else _env_bool("AI_STREAMING_ENABLED", False)
            ),
            extra=dict(overrides.get("extra") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a log-safe dictionary (no credentials)."""
        return {
            "provider": self.provider,
            "model": self.model,
            "embedding_model": self.embedding_model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
            "streaming_enabled": self.streaming_enabled,
        }

    def __repr__(self) -> str:
        safe = self.to_dict()
        return f"ProviderConfig({safe})"


def sanitize_config_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Redact sensitive keys from a config mapping for logging."""
    cleaned: dict[str, Any] = {}
    for key, value in data.items():
        lower = key.lower()
        if lower in _SENSITIVE_KEYS or any(s in lower for s in ("api_key", "secret", "password", "token")):
            cleaned[key] = "[REDACTED]"
        elif isinstance(value, dict):
            cleaned[key] = sanitize_config_dict(value)
        else:
            cleaned[key] = value
    return cleaned


def default_provider_config() -> ProviderConfig:
    """Return provider config loaded from the current environment."""
    return ProviderConfig.from_env()
