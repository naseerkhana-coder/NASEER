# MODULE-021 — AI Provider Interface

Enterprise-grade pluggable AI provider layer for MAXEK ERP. This module defines
the abstract provider contract, a development mock, factory wiring, and
MODULE-019 adapter bridges. **No real external API integrations** are included
in this module — OpenAI, Anthropic, Google Gemini, Azure OpenAI, and Local LLM
providers are registered as stubs only.

## Quick start

```python
from app.ai.providers import get_provider, ProviderConfig

provider = get_provider(ProviderConfig(provider="mock"))
response = provider.generate_text(
    GenerateTextRequest(prompt="Summarize project status")
)
print(response.text)
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `mock` | Provider id (`mock`, `openai`, `anthropic`, …) |
| `AI_MODEL` | `maxek-mock-v1` | Chat/completion model name |
| `AI_EMBEDDING_MODEL` | `maxek-mock-embed-v1` | Embedding model name |
| `AI_TEMPERATURE` | `0.4` | Sampling temperature |
| `AI_MAX_TOKENS` | `4096` | Max output tokens |
| `AI_TIMEOUT` | `30` | Request timeout (seconds) |
| `AI_STREAMING_ENABLED` | `false` | Enable streaming |

## Security

- API keys and secrets must be supplied via environment variables when real
  providers are implemented (e.g. `OPENAI_API_KEY`). They are **never** logged
  or included in `ProviderConfig.to_dict()` / `__repr__`.
- Use `sanitize_config_dict()` before logging arbitrary config mappings.

## Integration with MODULE-019

`AICoreEngine` uses `get_llm_provider()` and `get_embedding_provider()` by
default when no explicit providers are injected. Existing `StubLLMProvider` and
`StubEmbeddingProvider` remain available for backward compatibility.

## Registered providers

| Provider | Status |
|----------|--------|
| `mock` / `stub` | Fully implemented (dev/test) |
| `openai` | Stub — raises on use |
| `anthropic` | Stub — raises on use |
| `google` / `gemini` | Stub — raises on use |
| `azure` / `azure_openai` | Stub — raises on use |
| `local` / `local_llm` | Stub — raises on use |

## Mock provider options

```python
from app.ai.providers import MockProvider, MockProviderOptions

provider = MockProvider(options=MockProviderOptions(
    latency_seconds=0.05,
    simulate_error="timeout",  # timeout | unavailable | invalid_response | embedding
    test_mode=True,
))
```

## Exception hierarchy

```
AIProviderError
├── AIProviderTimeout
├── AIProviderUnavailable
├── AIInvalidResponse
└── AIEmbeddingError
```
