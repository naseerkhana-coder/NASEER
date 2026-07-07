"""Provider factory and MODULE-019 adapter bridges (MODULE-021)."""

from __future__ import annotations

from typing import Any

from app.ai.config import AIEngineConfig, EmbeddingProvider, LLMProvider
from app.ai.providers.base import (
    AIProvider,
    EmbedTextRequest,
    GenerateTextRequest,
)
from app.ai.providers.config import ProviderConfig, default_provider_config
from app.ai.providers.exceptions import AIProviderUnavailable
from app.ai.providers.mock_provider import MockProvider, MockProviderOptions

# Registered provider identifiers (only mock is fully implemented).
PROVIDER_MOCK = "mock"
PROVIDER_OPENAI = "openai"
PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_GOOGLE = "google"
PROVIDER_GEMINI = "gemini"
PROVIDER_AZURE = "azure"
PROVIDER_AZURE_OPENAI = "azure_openai"
PROVIDER_LOCAL = "local"
PROVIDER_LOCAL_LLM = "local_llm"
PROVIDER_STUB = "stub"

_SUPPORTED_PROVIDERS = frozenset(
    {
        PROVIDER_MOCK,
        PROVIDER_STUB,
        PROVIDER_OPENAI,
        PROVIDER_ANTHROPIC,
        PROVIDER_GOOGLE,
        PROVIDER_GEMINI,
        PROVIDER_AZURE,
        PROVIDER_AZURE_OPENAI,
        PROVIDER_LOCAL,
        PROVIDER_LOCAL_LLM,
    }
)

# Aliases map to canonical provider ids.
_PROVIDER_ALIASES: dict[str, str] = {
    "stub": PROVIDER_MOCK,
    "mock": PROVIDER_MOCK,
    "openai": PROVIDER_OPENAI,
    "anthropic": PROVIDER_ANTHROPIC,
    "claude": PROVIDER_ANTHROPIC,
    "google": PROVIDER_GOOGLE,
    "gemini": PROVIDER_GEMINI,
    "google_gemini": PROVIDER_GEMINI,
    "azure": PROVIDER_AZURE,
    "azure_openai": PROVIDER_AZURE_OPENAI,
    "local": PROVIDER_LOCAL,
    "local_llm": PROVIDER_LOCAL_LLM,
    "ollama": PROVIDER_LOCAL_LLM,
}


class _NotImplementedProvider(AIProvider):
    """Placeholder that raises on every call until a real integration is added."""

    def __init__(self, provider_id: str) -> None:
        self.provider_name = provider_id

    def _raise(self) -> None:
        raise AIProviderUnavailable(
            f"Provider '{self.provider_name}' is registered but not yet implemented. "
            "Set AI_PROVIDER=mock for development.",
            provider=self.provider_name,
        )

    def generate_text(self, request, *, config=None):
        self._raise()

    def generate_json(self, request, *, config=None):
        self._raise()

    def generate_stream(self, request, *, config=None):
        self._raise()
        yield  # pragma: no cover — unreachable; satisfies generator type

    def embed_text(self, request, *, config=None):
        self._raise()

    def embed_documents(self, request, *, config=None):
        self._raise()

    def validate_response(self, response, *, expected_type: str = "text") -> bool:
        self._raise()
        return False  # pragma: no cover

    def health_check(self, *, config=None):
        self._raise()
        return None  # pragma: no cover


def normalize_provider_id(provider: str) -> str:
    """Normalize a provider string to a canonical id."""
    key = (provider or PROVIDER_MOCK).strip().lower()
    return _PROVIDER_ALIASES.get(key, key)


def list_registered_providers() -> list[str]:
    """Return sorted list of known provider identifiers."""
    return sorted(_SUPPORTED_PROVIDERS)


def get_provider(
    config: ProviderConfig | None = None,
    *,
    mock_options: MockProviderOptions | None = None,
) -> AIProvider:
    """
    Instantiate an AI provider from configuration.

    Only ``mock`` (and alias ``stub``) returns a working provider.
    All other registered providers return a placeholder that raises
    ``AIProviderUnavailable`` on use.
    """
    cfg = config or default_provider_config()
    provider_id = normalize_provider_id(cfg.provider)

    if provider_id in {PROVIDER_MOCK, PROVIDER_STUB}:
        return MockProvider(options=mock_options, config=cfg)

    if provider_id in _SUPPORTED_PROVIDERS:
        return _NotImplementedProvider(provider_id)

    raise AIProviderUnavailable(
        f"Unknown AI provider '{cfg.provider}'. "
        f"Supported values: {', '.join(sorted(_SUPPORTED_PROVIDERS))}",
        provider=cfg.provider,
    )


class AIProviderLLMAdapter:
    """Bridge AIProvider → MODULE-019 LLMProvider protocol."""

    provider_name: str

    def __init__(self, provider: AIProvider, *, config: ProviderConfig | None = None) -> None:
        self._provider = provider
        self._config = config or default_provider_config()
        self.provider_name = provider.provider_name

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        config: AIEngineConfig | None = None,
    ) -> str:
        engine_cfg = config
        provider_cfg = self._merge_engine_config(engine_cfg)
        response = self._provider.generate_text(
            GenerateTextRequest(
                prompt=prompt,
                system=system,
                temperature=provider_cfg.temperature,
                max_tokens=provider_cfg.max_tokens,
            ),
            config=provider_cfg,
        )
        return response.text

    def _merge_engine_config(self, engine_cfg: AIEngineConfig | None) -> ProviderConfig:
        if engine_cfg is None:
            return self._config
        return ProviderConfig(
            provider=self._config.provider,
            model=engine_cfg.model_version or self._config.model,
            embedding_model=self._config.embedding_model,
            temperature=engine_cfg.temperature,
            max_tokens=engine_cfg.token_limit,
            timeout=self._config.timeout,
            streaming_enabled=engine_cfg.streaming,
            extra=dict(engine_cfg.extra),
        )


class AIProviderEmbeddingAdapter:
    """Bridge AIProvider → MODULE-019 EmbeddingProvider protocol."""

    provider_name: str

    def __init__(self, provider: AIProvider, *, config: ProviderConfig | None = None) -> None:
        self._provider = provider
        self._config = config or default_provider_config()
        self.provider_name = provider.provider_name

    def embed(self, text: str, *, config: AIEngineConfig | None = None) -> list[float]:
        provider_cfg = self._config
        if config is not None:
            provider_cfg = ProviderConfig(
                provider=self._config.provider,
                model=config.model_version or self._config.model,
                embedding_model=self._config.embedding_model,
                temperature=config.temperature,
                max_tokens=config.token_limit,
                timeout=self._config.timeout,
                streaming_enabled=config.streaming,
            )
        response = self._provider.embed_text(
            EmbedTextRequest(text=text),
            config=provider_cfg,
        )
        return response.embeddings[0] if response.embeddings else []


def get_llm_provider(
    config: ProviderConfig | None = None,
    *,
    mock_options: MockProviderOptions | None = None,
) -> LLMProvider:
    """Return an LLMProvider backed by the provider factory."""
    provider = get_provider(config, mock_options=mock_options)
    return AIProviderLLMAdapter(provider, config=config or default_provider_config())


def get_embedding_provider(
    config: ProviderConfig | None = None,
    *,
    mock_options: MockProviderOptions | None = None,
) -> EmbeddingProvider:
    """Return an EmbeddingProvider backed by the provider factory."""
    provider = get_provider(config, mock_options=mock_options)
    return AIProviderEmbeddingAdapter(provider, config=config or default_provider_config())


def provider_config_from_engine(engine_config: AIEngineConfig) -> ProviderConfig:
    """Map MODULE-019 engine config fields to provider config."""
    base = default_provider_config()
    llm_id = normalize_provider_id(engine_config.llm_provider or base.provider)
    return ProviderConfig(
        provider=llm_id,
        model=engine_config.model_version or base.model,
        embedding_model=base.embedding_model,
        temperature=engine_config.temperature,
        max_tokens=engine_config.token_limit,
        timeout=base.timeout,
        streaming_enabled=engine_config.streaming,
        extra=dict(engine_config.extra),
    )
