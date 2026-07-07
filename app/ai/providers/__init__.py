"""AI Provider Interface (MODULE-021) — public exports."""

from __future__ import annotations

from app.ai.providers.base import (
    AIProvider,
    EmbedDocumentsRequest,
    EmbedResponse,
    EmbedTextRequest,
    GenerateJsonRequest,
    GenerateJsonResponse,
    GenerateTextRequest,
    GenerateTextResponse,
    HealthCheckResult,
    StreamChunk,
)
from app.ai.providers.config import ProviderConfig, default_provider_config, sanitize_config_dict
from app.ai.providers.exceptions import (
    AIEmbeddingError,
    AIInvalidResponse,
    AIProviderError,
    AIProviderTimeout,
    AIProviderUnavailable,
)
from app.ai.providers.mock_provider import MockProvider, MockProviderOptions
from app.ai.providers.provider_factory import (
    AIProviderEmbeddingAdapter,
    AIProviderLLMAdapter,
    get_embedding_provider,
    get_llm_provider,
    get_provider,
    list_registered_providers,
    normalize_provider_id,
    provider_config_from_engine,
)

__all__ = [
    "AIProvider",
    "AIProviderEmbeddingAdapter",
    "AIProviderError",
    "AIProviderLLMAdapter",
    "AIProviderTimeout",
    "AIProviderUnavailable",
    "AIEmbeddingError",
    "AIInvalidResponse",
    "EmbedDocumentsRequest",
    "EmbedResponse",
    "EmbedTextRequest",
    "GenerateJsonRequest",
    "GenerateJsonResponse",
    "GenerateTextRequest",
    "GenerateTextResponse",
    "HealthCheckResult",
    "MockProvider",
    "MockProviderOptions",
    "ProviderConfig",
    "StreamChunk",
    "default_provider_config",
    "get_embedding_provider",
    "get_llm_provider",
    "get_provider",
    "list_registered_providers",
    "normalize_provider_id",
    "provider_config_from_engine",
    "sanitize_config_dict",
]
