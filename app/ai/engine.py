"""AI Core Engine entry point (MODULE-019) and prompt resolver (MODULE-020)."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, replace
from typing import Any

from app.ai.config import (
    AIEngineConfig,
    EmbeddingProvider,
    LLMProvider,
    default_engine_config,
)
from app.ai.providers.provider_factory import (
    get_embedding_provider,
    get_llm_provider,
    provider_config_from_engine,
)
from app.ai.context import build_erp_context
from app.ai.logger import log_ai_execution
from app.ai.memory import MemoryManager
from app.ai.permissions import verify_ai_permissions
from app.ai.registry import (
    AIModuleRegistry,
    AIRequest,
    AIResponse,
    AIRegistry,
    get_default_registry,
    resolve_prompt_for_request,
)
from app.ai.router import resolve_module_key


# ---------------------------------------------------------------------------
# MODULE-020 — legacy prompt engine types (kept for prompt management tests)
# ---------------------------------------------------------------------------


@dataclass
class PromptRequest:
    """Prompt-backed AI request envelope (MODULE-020)."""

    domain: str
    action: str
    user_message: str = ""
    language: str = "en"
    variables: dict[str, Any] = field(default_factory=dict)
    prompt_version: str | None = None


@dataclass
class PromptResponse:
    """Resolved prompt package for downstream LLM adapter."""

    system_prompt: str
    user_message: str
    domain: str
    action: str
    prompt_version: str
    language: str
    metadata: dict[str, Any] = field(default_factory=dict)


class AIEngine:
    """Lightweight prompt resolver without external API calls (MODULE-020)."""

    def __init__(self) -> None:
        AIRegistry.register_prompts()

    def resolve_prompt(
        self,
        domain: str,
        action: str,
        *,
        version: str | None = None,
        language: str = "en",
        variables: dict[str, Any] | None = None,
    ) -> str:
        return AIRegistry.resolve_prompt(
            domain,
            action,
            version=version,
            language=language,
            variables=variables,
        )

    def prepare(self, request: PromptRequest) -> PromptResponse:
        template = AIRegistry.get_template(
            request.domain,
            request.action,
            request.prompt_version,
        )
        system_prompt = template.render(
            language=request.language,
            variables=request.variables,
        )
        return PromptResponse(
            system_prompt=system_prompt,
            user_message=request.user_message,
            domain=request.domain,
            action=request.action,
            prompt_version=str(template.version),
            language=request.language,
            metadata=template.metadata(),
        )

    def route(self, request: PromptRequest) -> PromptResponse:
        return self.prepare(request)


# Backward-compatible aliases for MODULE-020 tests
LegacyAIRequest = PromptRequest
LegacyAIResponse = PromptResponse


# ---------------------------------------------------------------------------
# MODULE-019 — central AI orchestrator
# ---------------------------------------------------------------------------


class AICoreEngine:
    """
    Central AI orchestrator.

    Receives every AI request, enforces permissions, builds context,
    routes to the correct module, persists memory, and audits execution.
    """

    def __init__(
        self,
        db,
        *,
        registry: AIModuleRegistry | None = None,
        config: AIEngineConfig | None = None,
        llm_provider: LLMProvider | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.db = db
        self.registry = registry or get_default_registry()
        self.config = config or default_engine_config()
        provider_cfg = provider_config_from_engine(self.config)
        self.llm_provider = llm_provider or get_llm_provider(provider_cfg)
        self.embedding_provider = embedding_provider or get_embedding_provider(provider_cfg)
        self.memory = MemoryManager(db)
        AIRegistry.register_prompts()

    def resolve_prompt(
        self,
        domain: str,
        action: str,
        *,
        version: str | None = None,
        language: str = "en",
        variables: dict[str, Any] | None = None,
    ) -> str:
        """Resolve MODULE-020 enterprise prompt (no external API calls)."""
        return AIRegistry.resolve_prompt(
            domain,
            action,
            version=version,
            language=language,
            variables=variables,
        )

    def execute(
        self,
        request: AIRequest,
        *,
        session_data: dict[str, Any] | None = None,
    ) -> AIResponse:
        started = time.perf_counter()
        session_data = session_data or {}
        session_id = request.session_id or session_data.get("ai_session_id") or str(uuid.uuid4())

        if not (request.prompt or "").strip() and not request.request_type:
            return self._finish(
                request,
                module_key="",
                request_type="",
                status="validation_error",
                success=False,
                message="prompt or request_type is required",
                data={},
                started=started,
                context={},
                session_id=session_id,
                error="Missing prompt",
            )

        module_key, request_type = resolve_module_key(request, registry=self.registry)
        request = replace(request, request_type=request_type, session_id=session_id)
        module = self.registry.require(module_key)

        permission = verify_ai_permissions(
            self.db,
            request,
            module,
            session_data=session_data,
        )
        if not permission.allowed:
            return self._finish(
                request,
                module_key=module_key,
                request_type=request_type,
                status="denied",
                success=False,
                message=permission.reason,
                data={"permission_checks": permission.checks or {}},
                started=started,
                context={},
                session_id=session_id,
                error=permission.reason,
            )

        context = build_erp_context(
            self.db,
            user_id=request.user_id,
            company_id=request.company_id,
            branch_id=request.branch_id,
            project_id=request.project_id,
            client_id=request.client_id,
            vendor_id=request.vendor_id,
            document_id=request.document_id,
            session_data=session_data,
            hints=request.context_hints,
        )
        memory_snapshot = self.memory.build_memory_snapshot(
            session_id=session_id,
            user_id=request.user_id,
            company_id=request.company_id,
        )

        prefs = memory_snapshot.get("preferences") or {}
        runtime_config = replace(
            self.config,
            temperature=float(prefs.get("temperature", self.config.temperature)),
            token_limit=int(prefs.get("token_limit", self.config.token_limit)),
            streaming=bool(prefs.get("streaming", self.config.streaming)),
        )

        try:
            system_prompt = resolve_prompt_for_request(
                request,
                module_key=module_key,
                request_type=request_type,
                context=context,
                language=str(request.metadata.get("language") or "en"),
            )
            module_payload = module.execute(
                request,
                context=context,
                memory_snapshot=memory_snapshot,
                config=runtime_config,
            )
            llm_text = self.llm_provider.complete(
                request.prompt,
                system=system_prompt,
                config=runtime_config,
            )
            embedding = self.embedding_provider.embed(request.prompt, config=runtime_config)
            from app.ai.prompts import get_prompt_template
            from app.ai.registry import MODULE_KEY_PROMPT_DEFAULTS, REQUEST_TYPE_PROMPT_MAP

            prompt_domain_action = REQUEST_TYPE_PROMPT_MAP.get(
                request_type
            ) or MODULE_KEY_PROMPT_DEFAULTS.get(module_key, ("system", "base"))
            try:
                prompt_version = str(get_prompt_template(*prompt_domain_action).version)
            except Exception:
                prompt_version = "v1.0.0"
            data = {
                **module_payload,
                "llm_preview": llm_text,
                "system_prompt_chars": len(system_prompt),
                "prompt_version": prompt_version,
                "embedding_dimensions": len(embedding),
                "routing": {
                    "module_key": module_key,
                    "display_name": module.display_name,
                    "request_type": request_type,
                },
                "permission_checks": permission.checks or {},
            }
            self._persist_success(request, session_id, module_key, request_type, data)
            return self._finish(
                request,
                module_key=module_key,
                request_type=request_type,
                status="completed",
                success=True,
                message=f"{module.display_name} completed request.",
                data=data,
                started=started,
                context=context,
                session_id=session_id,
            )
        except Exception as exc:
            return self._finish(
                request,
                module_key=module_key,
                request_type=request_type,
                status="error",
                success=False,
                message="AI execution failed.",
                data={},
                started=started,
                context=context,
                session_id=session_id,
                error=str(exc),
            )

    def _persist_success(
        self,
        request: AIRequest,
        session_id: str,
        module_key: str,
        request_type: str,
        data: dict[str, Any],
    ) -> None:
        self.memory.append_conversation(
            session_id=session_id,
            role="user",
            content=request.prompt,
            user_id=request.user_id,
            company_id=request.company_id,
            module_key=module_key,
            request_type=request_type,
        )
        self.memory.append_conversation(
            session_id=session_id,
            role="assistant",
            content=str(data.get("llm_preview") or data.get("note") or "completed"),
            user_id=request.user_id,
            company_id=request.company_id,
            module_key=module_key,
            request_type=request_type,
            metadata={"status": data.get("status")},
        )
        session_payload = self.memory.get_session_memory(session_id)
        session_payload["last_module"] = module_key
        session_payload["last_request_type"] = request_type
        self.memory.set_session_memory(
            session_id,
            session_payload,
            user_id=request.user_id,
            company_id=request.company_id,
        )

    def _finish(
        self,
        request: AIRequest,
        *,
        module_key: str,
        request_type: str,
        status: str,
        success: bool,
        message: str,
        data: dict[str, Any],
        started: float,
        context: dict[str, Any],
        session_id: str,
        error: str | None = None,
    ) -> AIResponse:
        execution_ms = int((time.perf_counter() - started) * 1000)
        log_ai_execution(
            self.db,
            user_id=request.user_id,
            company_id=request.company_id,
            session_id=session_id,
            module_key=module_key,
            request_type=request_type,
            prompt=request.prompt,
            context=context,
            response_status=status,
            success=success,
            execution_ms=execution_ms,
            error_message=error,
        )
        return AIResponse(
            success=success,
            module_key=module_key,
            request_type=request_type,
            status=status,
            message=message,
            data=data,
            execution_ms=execution_ms,
            error=error,
        )


def process_ai_request(
    db,
    payload: dict[str, Any],
    *,
    session_data: dict[str, Any] | None = None,
    engine: AICoreEngine | None = None,
) -> AIResponse:
    """Convenience wrapper that builds an AIRequest from a JSON payload."""
    request = AIRequest(
        prompt=str(payload.get("prompt") or ""),
        request_type=payload.get("request_type"),
        user_id=_coerce_int(payload.get("user_id")),
        company_id=_coerce_int(payload.get("company_id")),
        department_id=_coerce_int(payload.get("department_id")),
        branch_id=_coerce_int(payload.get("branch_id")),
        project_id=_coerce_int(payload.get("project_id")),
        client_id=_coerce_int(payload.get("client_id")),
        vendor_id=_coerce_int(payload.get("vendor_id")),
        document_id=_coerce_int(payload.get("document_id")),
        module_name=str(payload.get("module_name") or ""),
        screen_name=str(payload.get("screen_name") or ""),
        action=str(payload.get("action") or "view"),
        record_table=str(payload.get("record_table") or ""),
        record_id=_coerce_int(payload.get("record_id")),
        session_id=str(payload.get("session_id") or ""),
        is_admin=bool(payload.get("is_admin")),
        is_platform_super_admin=bool(payload.get("is_platform_super_admin")),
        context_hints=payload.get("context_hints") if isinstance(payload.get("context_hints"), dict) else {},
        metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        prompt_variables=payload.get("prompt_variables")
        if isinstance(payload.get("prompt_variables"), dict)
        else {},
    )
    runner = engine or AICoreEngine(db)
    return runner.execute(request, session_data=session_data)


def _coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
