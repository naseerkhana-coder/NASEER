"""MAXEK ERP AI Core Engine (MODULE-019)."""

from __future__ import annotations

from app.ai.config import (
    AIEngineConfig,
    EmbeddingProvider,
    LLMProvider,
    StubEmbeddingProvider,
    StubLLMProvider,
    default_engine_config,
)
from app.ai.context import build_erp_context, serialize_context
from app.ai.engine import AICoreEngine, process_ai_request
from app.ai.logger import ensure_ai_logger_schema, list_ai_execution_logs, log_ai_execution, sanitize_context
from app.ai.memory import MemoryManager, ensure_ai_core_schema, ensure_ai_memory_schema
from app.ai.permissions import PermissionResult, verify_ai_permissions
from app.ai.registry import (
    AIRequest,
    AIResponse,
    AIModuleRegistry,
    BaseAIModule,
    get_default_registry,
)
from app.ai.prompts import get_prompt, list_prompts, register_all_prompts
from app.ai.router import REQUEST_TYPE_ROUTES, detect_request_type, resolve_module_key, route_request

__all__ = [
    "AIEngineConfig",
    "AICoreEngine",
    "AIModuleRegistry",
    "AIRequest",
    "AIResponse",
    "BaseAIModule",
    "EmbeddingProvider",
    "LLMProvider",
    "MemoryManager",
    "PermissionResult",
    "REQUEST_TYPE_ROUTES",
    "StubEmbeddingProvider",
    "StubLLMProvider",
    "build_erp_context",
    "default_engine_config",
    "detect_request_type",
    "get_prompt",
    "ensure_ai_core_schema",
    "ensure_ai_logger_schema",
    "ensure_ai_memory_schema",
    "get_default_registry",
    "list_ai_execution_logs",
    "list_prompts",
    "log_ai_execution",
    "process_ai_request",
    "register_all_prompts",
    "resolve_module_key",
    "route_request",
    "sanitize_context",
    "serialize_context",
    "verify_ai_permissions",
]
