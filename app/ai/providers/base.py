"""Abstract AI provider interface (MODULE-021)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from app.ai.providers.config import ProviderConfig


@dataclass
class GenerateTextRequest:
    """Input envelope for text generation."""

    prompt: str
    system: str = ""
    temperature: float | None = None
    max_tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerateTextResponse:
    """Output envelope for text generation."""

    text: str
    model: str
    provider: str
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerateJsonRequest:
    """Input envelope for structured JSON generation."""

    prompt: str
    system: str = ""
    schema_hint: dict[str, Any] | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerateJsonResponse:
    """Output envelope for structured JSON generation."""

    data: dict[str, Any]
    model: str
    provider: str
    raw_text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamChunk:
    """Single chunk from a streaming text response."""

    text: str
    index: int
    is_final: bool = False


@dataclass
class EmbedTextRequest:
    """Input envelope for single-text embedding."""

    text: str
    model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EmbedDocumentsRequest:
    """Input envelope for batch document embedding."""

    documents: list[str]
    model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EmbedResponse:
    """Output envelope for embedding operations."""

    embeddings: list[list[float]]
    model: str
    provider: str
    dimensions: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthCheckResult:
    """Result of a provider health probe."""

    healthy: bool
    provider: str
    message: str = ""
    latency_ms: float | None = None
    details: dict[str, Any] = field(default_factory=dict)


class AIProvider(ABC):
    """
    Abstract base class for all MAXEK ERP AI providers.

    Concrete implementations must support text generation, JSON generation,
    streaming, embeddings, response validation, and health checks.
    """

    provider_name: str

    @abstractmethod
    def generate_text(
        self,
        request: GenerateTextRequest,
        *,
        config: ProviderConfig | None = None,
    ) -> GenerateTextResponse:
        """Generate natural-language text from a prompt."""

    @abstractmethod
    def generate_json(
        self,
        request: GenerateJsonRequest,
        *,
        config: ProviderConfig | None = None,
    ) -> GenerateJsonResponse:
        """Generate structured JSON from a prompt."""

    @abstractmethod
    def generate_stream(
        self,
        request: GenerateTextRequest,
        *,
        config: ProviderConfig | None = None,
    ) -> Iterator[StreamChunk]:
        """Yield incremental text chunks for a prompt."""

    @abstractmethod
    def embed_text(
        self,
        request: EmbedTextRequest,
        *,
        config: ProviderConfig | None = None,
    ) -> EmbedResponse:
        """Return a vector embedding for a single text input."""

    @abstractmethod
    def embed_documents(
        self,
        request: EmbedDocumentsRequest,
        *,
        config: ProviderConfig | None = None,
    ) -> EmbedResponse:
        """Return vector embeddings for multiple documents."""

    @abstractmethod
    def validate_response(self, response: Any, *, expected_type: str = "text") -> bool:
        """Validate that a provider response meets basic quality checks."""

    @abstractmethod
    def health_check(self, *, config: ProviderConfig | None = None) -> HealthCheckResult:
        """Probe provider availability and return status."""
