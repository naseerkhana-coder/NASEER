"""Enterprise AI provider exceptions (MODULE-021)."""

from __future__ import annotations


class AIProviderError(Exception):
    """Base exception for all AI provider failures."""

    def __init__(self, message: str, *, provider: str | None = None) -> None:
        self.provider = provider
        super().__init__(message)


class AIProviderTimeout(AIProviderError):
    """Raised when a provider request exceeds the configured timeout."""


class AIProviderUnavailable(AIProviderError):
    """Raised when a provider is not configured, not implemented, or unreachable."""


class AIInvalidResponse(AIProviderError):
    """Raised when a provider returns malformed or unusable output."""


class AIEmbeddingError(AIProviderError):
    """Raised when text or document embedding fails."""
