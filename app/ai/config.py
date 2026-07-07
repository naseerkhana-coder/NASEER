"""AI Core configuration and provider interfaces (no external SDK calls)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class AIEngineConfig:
    """Runtime configuration for the AI Core engine."""

    llm_provider: str = "stub"
    embedding_provider: str = "stub"
    model_version: str = "maxek-stub-v1"
    temperature: float = 0.4
    token_limit: int = 4096
    streaming: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class LLMProvider(Protocol):
    """Pluggable large-language-model provider interface."""

    provider_name: str

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        config: AIEngineConfig | None = None,
    ) -> str:
        """Return model text for the given prompt."""
        ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Pluggable embedding provider interface."""

    provider_name: str

    def embed(self, text: str, *, config: AIEngineConfig | None = None) -> list[float]:
        """Return a vector embedding for the given text."""
        ...


class StubLLMProvider:
    """Default no-op LLM provider for offline / interface-only operation."""

    provider_name = "stub"

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        config: AIEngineConfig | None = None,
    ) -> str:
        preview = (prompt or "").strip()
        if len(preview) > 120:
            preview = preview[:117] + "..."
        return (
            f"[StubLLM:{config.model_version if config else 'maxek-stub-v1'}] "
            f"Processed request ({len(prompt or '')} chars). "
            f"Preview: {preview or '(empty)'}"
        )


class StubEmbeddingProvider:
    """Deterministic stub embeddings for testing and offline mode."""

    provider_name = "stub"

    def embed(self, text: str, *, config: AIEngineConfig | None = None) -> list[float]:
        seed = sum(ord(ch) for ch in (text or "")) or 1
        return [float((seed * (index + 1)) % 997) / 997.0 for index in range(8)]


def default_engine_config() -> AIEngineConfig:
    """Return engine config, honouring MODULE-021 provider env vars when set."""
    try:
        from app.ai.providers.config import default_provider_config

        provider_cfg = default_provider_config()
        return AIEngineConfig(
            llm_provider=provider_cfg.provider,
            embedding_provider=provider_cfg.provider,
            model_version=provider_cfg.model,
            temperature=provider_cfg.temperature,
            token_limit=provider_cfg.max_tokens,
            streaming=provider_cfg.streaming_enabled,
        )
    except ImportError:
        return AIEngineConfig()
