"""Unit tests for AI Provider Interface (MODULE-021)."""

from __future__ import annotations

import io
import logging
import os
import unittest
from unittest import mock

from app.ai.config import AIEngineConfig, StubEmbeddingProvider, StubLLMProvider
from app.ai.engine import AICoreEngine
from app.ai.providers import (
    AIEmbeddingError,
    AIInvalidResponse,
    AIProviderError,
    AIProviderTimeout,
    AIProviderUnavailable,
    EmbedDocumentsRequest,
    EmbedTextRequest,
    GenerateJsonRequest,
    GenerateTextRequest,
    MockProvider,
    MockProviderOptions,
    ProviderConfig,
    default_provider_config,
    get_embedding_provider,
    get_llm_provider,
    get_provider,
    list_registered_providers,
    normalize_provider_id,
    sanitize_config_dict,
)
from app.ai.providers.provider_factory import _NotImplementedProvider


class TestMockProviderText(unittest.TestCase):
    def test_generate_text_returns_preview(self) -> None:
        provider = MockProvider()
        response = provider.generate_text(GenerateTextRequest(prompt="predict stock for cement"))
        self.assertIn("MockProvider", response.text)
        self.assertIn("cement", response.text)
        self.assertEqual(response.provider, "mock")

    def test_generate_text_test_mode(self) -> None:
        provider = MockProvider(options=MockProviderOptions(test_mode=True))
        response = provider.generate_text(GenerateTextRequest(prompt="hello"))
        self.assertIn("[TEST:", response.text)

    def test_generate_json_returns_sample(self) -> None:
        provider = MockProvider()
        response = provider.generate_json(GenerateJsonRequest(prompt="summarize"))
        self.assertEqual(response.data["status"], "ok")
        self.assertIn("summary", response.data)

    def test_generate_stream_yields_chunks(self) -> None:
        provider = MockProvider()
        chunks = list(provider.generate_stream(GenerateTextRequest(prompt="one two three")))
        self.assertGreater(len(chunks), 0)
        self.assertTrue(chunks[-1].is_final)
        combined = "".join(c.text for c in chunks)
        self.assertIn("MockProvider", combined)

    def test_embed_text_fixed_dimensions(self) -> None:
        provider = MockProvider(options=MockProviderOptions(embedding_dimensions=8))
        response = provider.embed_text(EmbedTextRequest(text="cement"))
        self.assertEqual(len(response.embeddings), 1)
        self.assertEqual(len(response.embeddings[0]), 8)
        self.assertEqual(response.dimensions, 8)

    def test_embed_documents_batch(self) -> None:
        provider = MockProvider()
        response = provider.embed_documents(
            EmbedDocumentsRequest(documents=["doc-a", "doc-b"])
        )
        self.assertEqual(len(response.embeddings), 2)

    def test_embed_documents_empty_raises(self) -> None:
        provider = MockProvider()
        with self.assertRaises(AIEmbeddingError):
            provider.embed_documents(EmbedDocumentsRequest(documents=[]))

    def test_validate_response_types(self) -> None:
        provider = MockProvider()
        text_resp = provider.generate_text(GenerateTextRequest(prompt="x"))
        self.assertTrue(provider.validate_response(text_resp, expected_type="text"))
        json_resp = provider.generate_json(GenerateJsonRequest(prompt="x"))
        self.assertTrue(provider.validate_response(json_resp, expected_type="json"))
        embed_resp = provider.embed_text(EmbedTextRequest(text="x"))
        self.assertTrue(provider.validate_response(embed_resp, expected_type="embedding"))

    def test_health_check_healthy(self) -> None:
        provider = MockProvider()
        result = provider.health_check()
        self.assertTrue(result.healthy)
        self.assertEqual(result.provider, "mock")


class TestMockProviderSimulation(unittest.TestCase):
    def test_latency_simulation(self) -> None:
        provider = MockProvider(options=MockProviderOptions(latency_seconds=0.01))
        import time

        started = time.perf_counter()
        provider.generate_text(GenerateTextRequest(prompt="slow"))
        elapsed = time.perf_counter() - started
        self.assertGreaterEqual(elapsed, 0.01)

    def test_simulate_timeout(self) -> None:
        provider = MockProvider(options=MockProviderOptions(simulate_error="timeout"))
        with self.assertRaises(AIProviderTimeout):
            provider.generate_text(GenerateTextRequest(prompt="fail"))

    def test_simulate_unavailable(self) -> None:
        provider = MockProvider(options=MockProviderOptions(simulate_error="unavailable"))
        with self.assertRaises(AIProviderUnavailable):
            provider.generate_json(GenerateJsonRequest(prompt="fail"))

    def test_simulate_invalid_response(self) -> None:
        provider = MockProvider(options=MockProviderOptions(simulate_error="invalid_response"))
        with self.assertRaises(AIInvalidResponse):
            provider.embed_text(EmbedTextRequest(text="fail"))

    def test_simulate_embedding_error(self) -> None:
        provider = MockProvider(options=MockProviderOptions(simulate_error="embedding"))
        with self.assertRaises(AIEmbeddingError):
            provider.embed_documents(EmbedDocumentsRequest(documents=["x"]))

    def test_health_check_unhealthy_on_simulated_error(self) -> None:
        provider = MockProvider(options=MockProviderOptions(simulate_error="unavailable"))
        result = provider.health_check()
        self.assertFalse(result.healthy)


class TestProviderFactory(unittest.TestCase):
    def test_factory_selects_mock_by_default(self) -> None:
        provider = get_provider(ProviderConfig(provider="mock"))
        self.assertIsInstance(provider, MockProvider)

    def test_factory_stub_alias_returns_mock(self) -> None:
        provider = get_provider(ProviderConfig(provider="stub"))
        self.assertIsInstance(provider, MockProvider)

    def test_factory_openai_stub_raises_on_use(self) -> None:
        provider = get_provider(ProviderConfig(provider="openai"))
        self.assertIsInstance(provider, _NotImplementedProvider)
        with self.assertRaises(AIProviderUnavailable):
            provider.generate_text(GenerateTextRequest(prompt="x"))

    def test_factory_anthropic_stub_raises(self) -> None:
        provider = get_provider(ProviderConfig(provider="anthropic"))
        with self.assertRaises(AIProviderUnavailable):
            provider.generate_json(GenerateJsonRequest(prompt="x"))

    def test_factory_gemini_stub_raises(self) -> None:
        provider = get_provider(ProviderConfig(provider="gemini"))
        with self.assertRaises(AIProviderUnavailable):
            provider.embed_text(EmbedTextRequest(text="x"))

    def test_factory_azure_openai_stub_raises(self) -> None:
        provider = get_provider(ProviderConfig(provider="azure_openai"))
        with self.assertRaises(AIProviderUnavailable):
            provider.health_check()

    def test_factory_local_llm_stub_raises(self) -> None:
        provider = get_provider(ProviderConfig(provider="local_llm"))
        with self.assertRaises(AIProviderUnavailable):
            list(provider.generate_stream(GenerateTextRequest(prompt="x")))

    def test_unknown_provider_raises(self) -> None:
        with self.assertRaises(AIProviderUnavailable):
            get_provider(ProviderConfig(provider="unknown-vendor"))

    def test_list_registered_providers(self) -> None:
        providers = list_registered_providers()
        self.assertIn("mock", providers)
        self.assertIn("openai", providers)
        self.assertIn("anthropic", providers)

    def test_normalize_provider_id_aliases(self) -> None:
        self.assertEqual(normalize_provider_id("stub"), "mock")
        self.assertEqual(normalize_provider_id("claude"), "anthropic")
        self.assertEqual(normalize_provider_id("ollama"), "local_llm")


class TestProviderAdapters(unittest.TestCase):
    def test_llm_adapter_complete(self) -> None:
        adapter = get_llm_provider(ProviderConfig(provider="mock"))
        text = adapter.complete("hello world", system="You are helpful.")
        self.assertIn("MockProvider", text)
        self.assertEqual(adapter.provider_name, "mock")

    def test_embedding_adapter_embed(self) -> None:
        adapter = get_embedding_provider(ProviderConfig(provider="mock"))
        vector = adapter.embed("cement bags")
        self.assertEqual(len(vector), 8)

    def test_llm_adapter_respects_engine_config(self) -> None:
        adapter = get_llm_provider(ProviderConfig(provider="mock", model="custom-model"))
        text = adapter.complete(
            "test",
            config=AIEngineConfig(model_version="engine-model-v2", temperature=0.1),
        )
        self.assertIn("engine-model-v2", text)


class TestProviderConfig(unittest.TestCase):
    def test_config_from_env(self) -> None:
        env = {
            "AI_PROVIDER": "mock",
            "AI_MODEL": "env-model",
            "AI_EMBEDDING_MODEL": "env-embed",
            "AI_TEMPERATURE": "0.7",
            "AI_MAX_TOKENS": "2048",
            "AI_TIMEOUT": "15",
            "AI_STREAMING_ENABLED": "true",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            cfg = ProviderConfig.from_env()
        self.assertEqual(cfg.provider, "mock")
        self.assertEqual(cfg.model, "env-model")
        self.assertEqual(cfg.embedding_model, "env-embed")
        self.assertAlmostEqual(cfg.temperature, 0.7)
        self.assertEqual(cfg.max_tokens, 2048)
        self.assertAlmostEqual(cfg.timeout, 15.0)
        self.assertTrue(cfg.streaming_enabled)

    def test_config_to_dict_no_secrets(self) -> None:
        cfg = ProviderConfig(
            provider="mock",
            extra={"openai_api_key": "sk-secret", "region": "us-east-1"},
        )
        safe = cfg.to_dict()
        self.assertNotIn("openai_api_key", safe)
        self.assertNotIn("sk-secret", repr(cfg))

    def test_sanitize_config_dict_redacts_keys(self) -> None:
        raw = {
            "provider": "openai",
            "api_key": "sk-live",
            "nested": {"anthropic_api_key": "ant-secret", "model": "gpt-4"},
        }
        cleaned = sanitize_config_dict(raw)
        self.assertEqual(cleaned["api_key"], "[REDACTED]")
        self.assertEqual(cleaned["nested"]["anthropic_api_key"], "[REDACTED]")
        self.assertEqual(cleaned["nested"]["model"], "gpt-4")

    def test_default_provider_config_callable(self) -> None:
        cfg = default_provider_config()
        self.assertEqual(cfg.provider, "mock")


class TestExceptionHierarchy(unittest.TestCase):
    def test_hierarchy(self) -> None:
        self.assertTrue(issubclass(AIProviderTimeout, AIProviderError))
        self.assertTrue(issubclass(AIProviderUnavailable, AIProviderError))
        self.assertTrue(issubclass(AIInvalidResponse, AIProviderError))
        self.assertTrue(issubclass(AIEmbeddingError, AIProviderError))

    def test_provider_attribute(self) -> None:
        err = AIProviderUnavailable("down", provider="openai")
        self.assertEqual(err.provider, "openai")


class TestSecurityNoKeysInLogs(unittest.TestCase):
    def test_config_repr_never_logs_api_key(self) -> None:
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logger = logging.getLogger("test.ai.providers.security")
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        cfg = ProviderConfig(provider="openai", extra={"api_key": "sk-test-secret-key"})
        logger.info("Provider config: %s", cfg)
        logger.info("Provider dict: %s", cfg.to_dict())
        handler.flush()
        output = stream.getvalue()
        self.assertNotIn("sk-test-secret-key", output)
        self.assertNotIn("sk-test", output)
        logger.handlers.clear()


class TestEngineIntegration(unittest.TestCase):
    def test_engine_uses_factory_providers_by_default(self) -> None:
        import sqlite3

        from app.ai.logger import ensure_ai_logger_schema
        from app.ai.memory import ensure_ai_memory_schema
        from app.ai.registry import AIRequest

        db = sqlite3.connect(":memory:")
        ensure_ai_memory_schema(db)
        ensure_ai_logger_schema(db)
        engine = AICoreEngine(db)
        self.assertEqual(engine.llm_provider.provider_name, "mock")
        response = engine.execute(
            AIRequest(prompt="generate report", user_id=1, company_id=10, is_admin=True)
        )
        self.assertTrue(response.success)
        self.assertIn("MockProvider", response.data.get("llm_preview", ""))

    def test_engine_explicit_stub_providers_still_work(self) -> None:
        import sqlite3

        from app.ai.logger import ensure_ai_logger_schema
        from app.ai.memory import ensure_ai_memory_schema
        from app.ai.registry import AIRequest

        db = sqlite3.connect(":memory:")
        ensure_ai_memory_schema(db)
        ensure_ai_logger_schema(db)
        engine = AICoreEngine(
            db,
            llm_provider=StubLLMProvider(),
            embedding_provider=StubEmbeddingProvider(),
        )
        response = engine.execute(
            AIRequest(prompt="predict stock", user_id=1, company_id=10, is_admin=True)
        )
        self.assertTrue(response.success)
        self.assertIn("StubLLM", response.data.get("llm_preview", ""))


if __name__ == "__main__":
    unittest.main()
