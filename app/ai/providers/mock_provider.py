"""Development and testing mock AI provider (MODULE-021)."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

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
from app.ai.providers.config import ProviderConfig
from app.ai.providers.exceptions import (
    AIEmbeddingError,
    AIInvalidResponse,
    AIProviderError,
    AIProviderTimeout,
    AIProviderUnavailable,
)

_DEFAULT_EMBED_DIM = 8
_SAMPLE_JSON = {
    "status": "ok",
    "summary": "Mock structured response for MAXEK ERP.",
    "confidence": 0.95,
    "items": [{"id": 1, "label": "sample"}],
}


@dataclass
class MockProviderOptions:
    """Behaviour toggles for MockProvider (dev/test only)."""

    latency_seconds: float = 0.0
    simulate_error: str | None = None
    test_mode: bool = False
    embedding_dimensions: int = _DEFAULT_EMBED_DIM
    extra: dict[str, Any] = field(default_factory=dict)


class MockProvider(AIProvider):
    """
    Deterministic mock provider for offline development and unit tests.

    Supports configurable latency, error simulation, and test-mode responses.
    Never calls external APIs.
    """

    provider_name = "mock"

    def __init__(
        self,
        *,
        options: MockProviderOptions | None = None,
        config: ProviderConfig | None = None,
    ) -> None:
        self._options = options or MockProviderOptions()
        self._config = config or ProviderConfig()

    def _resolve_config(self, config: ProviderConfig | None) -> ProviderConfig:
        return config or self._config

    def _maybe_delay(self) -> None:
        delay = self._options.latency_seconds
        if delay > 0:
            time.sleep(delay)

    def _maybe_raise(self) -> None:
        code = (self._options.simulate_error or "").strip().lower()
        if not code:
            return
        if code == "timeout":
            raise AIProviderTimeout("Simulated provider timeout", provider=self.provider_name)
        if code == "unavailable":
            raise AIProviderUnavailable("Simulated provider unavailable", provider=self.provider_name)
        if code == "invalid_response":
            raise AIInvalidResponse("Simulated invalid response", provider=self.provider_name)
        if code == "embedding":
            raise AIEmbeddingError("Simulated embedding failure", provider=self.provider_name)
        raise AIProviderError(f"Simulated provider error: {code}", provider=self.provider_name)

    def _deterministic_embedding(self, text: str, dimensions: int) -> list[float]:
        seed = sum(ord(ch) for ch in (text or "")) or 1
        return [float((seed * (index + 1)) % 997) / 997.0 for index in range(dimensions)]

    def generate_text(
        self,
        request: GenerateTextRequest,
        *,
        config: ProviderConfig | None = None,
    ) -> GenerateTextResponse:
        cfg = self._resolve_config(config)
        self._maybe_delay()
        self._maybe_raise()

        preview = (request.prompt or "").strip()
        if len(preview) > 120:
            preview = preview[:117] + "..."

        if self._options.test_mode:
            text = f"[TEST:{cfg.model}] {preview or '(empty)'}"
        else:
            text = (
                f"[MockProvider:{cfg.model}] Processed request ({len(request.prompt or '')} chars). "
                f"Preview: {preview or '(empty)'}"
            )

        return GenerateTextResponse(
            text=text,
            model=cfg.model,
            provider=self.provider_name,
            usage={"prompt_tokens": len(request.prompt or ""), "completion_tokens": len(text)},
            metadata={"test_mode": self._options.test_mode},
        )

    def generate_json(
        self,
        request: GenerateJsonRequest,
        *,
        config: ProviderConfig | None = None,
    ) -> GenerateJsonResponse:
        cfg = self._resolve_config(config)
        self._maybe_delay()
        self._maybe_raise()

        payload = dict(_SAMPLE_JSON)
        payload["prompt_preview"] = (request.prompt or "")[:80]
        if request.schema_hint:
            payload["schema_hint_keys"] = list(request.schema_hint.keys())
        if self._options.test_mode:
            payload["test_mode"] = True

        raw = json.dumps(payload)
        return GenerateJsonResponse(
            data=payload,
            model=cfg.model,
            provider=self.provider_name,
            raw_text=raw,
            metadata={"test_mode": self._options.test_mode},
        )

    def generate_stream(
        self,
        request: GenerateTextRequest,
        *,
        config: ProviderConfig | None = None,
    ) -> Iterator[StreamChunk]:
        cfg = self._resolve_config(config)
        self._maybe_delay()
        self._maybe_raise()

        full = self.generate_text(request, config=cfg).text
        words = full.split(" ")
        if not words:
            yield StreamChunk(text="", index=0, is_final=True)
            return

        for index, word in enumerate(words):
            chunk_text = word if index == 0 else f" {word}"
            is_final = index == len(words) - 1
            yield StreamChunk(text=chunk_text, index=index, is_final=is_final)

    def embed_text(
        self,
        request: EmbedTextRequest,
        *,
        config: ProviderConfig | None = None,
    ) -> EmbedResponse:
        cfg = self._resolve_config(config)
        self._maybe_delay()
        self._maybe_raise()

        dimensions = self._options.embedding_dimensions
        vector = self._deterministic_embedding(request.text, dimensions)
        model = request.model or cfg.embedding_model
        return EmbedResponse(
            embeddings=[vector],
            model=model,
            provider=self.provider_name,
            dimensions=dimensions,
        )

    def embed_documents(
        self,
        request: EmbedDocumentsRequest,
        *,
        config: ProviderConfig | None = None,
    ) -> EmbedResponse:
        cfg = self._resolve_config(config)
        self._maybe_delay()
        self._maybe_raise()

        if not request.documents:
            raise AIEmbeddingError("No documents supplied for embedding", provider=self.provider_name)

        dimensions = self._options.embedding_dimensions
        model = request.model or cfg.embedding_model
        vectors = [self._deterministic_embedding(doc, dimensions) for doc in request.documents]
        return EmbedResponse(
            embeddings=vectors,
            model=model,
            provider=self.provider_name,
            dimensions=dimensions,
            metadata={"document_count": len(request.documents)},
        )

    def validate_response(self, response: Any, *, expected_type: str = "text") -> bool:
        if expected_type == "text":
            if isinstance(response, GenerateTextResponse):
                return bool(response.text.strip())
            return isinstance(response, str) and bool(str(response).strip())

        if expected_type == "json":
            if isinstance(response, GenerateJsonResponse):
                return isinstance(response.data, dict)
            if isinstance(response, dict):
                return True
            if isinstance(response, str):
                try:
                    json.loads(response)
                    return True
                except json.JSONDecodeError:
                    return False
            return False

        if expected_type == "embedding":
            if isinstance(response, EmbedResponse):
                return bool(response.embeddings) and response.dimensions > 0
            if isinstance(response, list):
                return bool(response) and all(isinstance(v, (int, float)) for v in response)
            return False

        return False

    def health_check(self, *, config: ProviderConfig | None = None) -> HealthCheckResult:
        cfg = self._resolve_config(config)
        started = time.perf_counter()
        try:
            self._maybe_raise()
            latency_ms = (time.perf_counter() - started) * 1000
            return HealthCheckResult(
                healthy=True,
                provider=self.provider_name,
                message="Mock provider is available.",
                latency_ms=latency_ms,
                details={"model": cfg.model, "test_mode": self._options.test_mode},
            )
        except AIProviderError as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            return HealthCheckResult(
                healthy=False,
                provider=self.provider_name,
                message=str(exc),
                latency_ms=latency_ms,
            )
