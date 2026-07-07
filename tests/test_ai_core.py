"""Unit tests for AI Core Engine (MODULE-019)."""

from __future__ import annotations

import json
import sqlite3
import unittest

from app.ai.config import AIEngineConfig, StubEmbeddingProvider, StubLLMProvider
from app.ai.context import build_erp_context
from app.ai.logger import sanitize_context
from app.ai.engine import AICoreEngine, process_ai_request
from app.ai.logger import ensure_ai_logger_schema, list_ai_execution_logs, log_ai_execution
from app.ai.memory import MemoryManager, ensure_ai_memory_schema
from app.ai.permissions import (
    PermissionResult,
    verify_ai_permissions,
    verify_company_access,
    verify_record_ownership,
)
from app.ai.registry import (
    AIRequest,
    AIModuleRegistry,
    AnalyticsAIModule,
    BaseAIModule,
    InventoryAIModule,
    get_default_registry,
)
from app.ai.router import detect_request_type, resolve_module_key, route_request


class _CustomAIModule(BaseAIModule):
    key = "custom_ai"
    display_name = "CustomAI"
    erp_module_name = "Reports"
    erp_screen_name = "reports"
    supported_request_types = ("custom_action",)

    def execute(self, request, *, context, memory_snapshot, config):
        return {"custom": True, "prompt_len": len(request.prompt)}


def _memory_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def _seed_user_company_db() -> sqlite3.Connection:
    db = _memory_db()
    db.execute(
        """
        CREATE TABLE users(
            id INTEGER PRIMARY KEY,
            username TEXT,
            company_id INTEGER,
            department_id INTEGER,
            created_by TEXT
        )
        """
    )
    db.execute(
        "INSERT INTO users(id, username, company_id, department_id, created_by) VALUES(1,'alice',10,5,'alice')"
    )
    db.execute(
        "CREATE TABLE projects(id INTEGER PRIMARY KEY, project_name TEXT, company_id INTEGER, created_by TEXT)"
    )
    db.execute(
        "INSERT INTO projects(id, project_name, company_id, created_by) VALUES(100,'Tower A',10,'alice')"
    )
    db.commit()
    return db


class TestAIRegistry(unittest.TestCase):
    def test_builtin_modules_registered(self):
        registry = get_default_registry()
        keys = set(registry.keys())
        expected = {
            "sales_ai",
            "purchase_ai",
            "inventory_ai",
            "hr_ai",
            "finance_ai",
            "project_ai",
            "tender_ai",
            "document_ai",
            "analytics_ai",
        }
        self.assertTrue(expected.issubset(keys))

    def test_register_custom_module(self):
        registry = AIModuleRegistry()
        registry.register(_CustomAIModule())
        module = registry.require("custom_ai")
        self.assertEqual(module.display_name, "CustomAI")

    def test_duplicate_registration_raises(self):
        registry = AIModuleRegistry()
        registry.register(_CustomAIModule())
        with self.assertRaises(ValueError):
            registry.register(_CustomAIModule())

    def test_replace_registration(self):
        registry = AIModuleRegistry()
        registry.register(_CustomAIModule())
        registry.register(_CustomAIModule(), replace=True)
        self.assertEqual(registry.require("custom_ai").display_name, "CustomAI")


class TestAIRouter(unittest.TestCase):
    def test_explicit_request_type_routes_inventory(self):
        request = AIRequest(prompt="", request_type="predict_stock")
        module_key, request_type = resolve_module_key(request)
        self.assertEqual(module_key, "inventory_ai")
        self.assertEqual(request_type, "predict_stock")

    def test_keyword_detection_generate_report(self):
        request = AIRequest(prompt="Please generate report for last quarter")
        self.assertEqual(detect_request_type(request), "generate_report")
        routing = route_request(request)
        self.assertEqual(routing["module_key"], "analytics_ai")

    def test_keyword_detection_vendor_analysis(self):
        request = AIRequest(prompt="Run vendor analysis for steel suppliers")
        module_key, _ = resolve_module_key(request)
        self.assertEqual(module_key, "purchase_ai")

    def test_keyword_detection_analyze_boq(self):
        request = AIRequest(prompt="analyze boq for package-2")
        module_key, request_type = resolve_module_key(request)
        self.assertEqual(module_key, "project_ai")
        self.assertEqual(request_type, "analyze_boq")

    def test_general_prompt_defaults_to_analytics(self):
        request = AIRequest(prompt="hello there")
        module_key, request_type = resolve_module_key(request)
        self.assertEqual(module_key, "analytics_ai")
        self.assertEqual(request_type, "general")


class TestAIContext(unittest.TestCase):
    def test_build_context_graceful_without_services(self):
        db = _memory_db()
        db.execute("CREATE TABLE clients(id INTEGER PRIMARY KEY, client_name TEXT, status TEXT)")
        db.execute("INSERT INTO clients(id, client_name, status) VALUES(1,'Acme','Active')")
        db.commit()
        context = build_erp_context(db, client_id=1, session_data={"user_id": 1, "company_id": 10})
        self.assertIsInstance(context, dict)
        self.assertIn("crm", context)
        self.assertEqual(context["company"], None)

    def test_sanitize_context_redacts_sensitive_keys(self):
        raw = {"user": {"username": "alice", "password": "secret"}, "token": "abc"}
        cleaned = sanitize_context(raw)
        self.assertEqual(cleaned["user"]["password"], "[REDACTED]")
        self.assertEqual(cleaned["token"], "[REDACTED]")


class TestAIMemory(unittest.TestCase):
    def setUp(self):
        self.db = _memory_db()
        self.memory = MemoryManager(self.db)

    def test_conversation_memory_roundtrip(self):
        self.memory.append_conversation(
            session_id="sess-1",
            role="user",
            content="predict stock for cement",
            user_id=1,
            company_id=10,
            module_key="inventory_ai",
            request_type="predict_stock",
        )
        history = self.memory.get_conversation("sess-1")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["role"], "user")

    def test_erp_memory_upsert(self):
        self.memory.set_erp_memory("last_forecast", {"item": "cement"}, company_id=10, user_id=1)
        self.memory.set_erp_memory("last_forecast", {"item": "steel"}, company_id=10, user_id=1)
        payload = self.memory.get_erp_memory("last_forecast", company_id=10, user_id=1)
        self.assertEqual(payload["item"], "steel")

    def test_session_memory_and_preferences(self):
        self.memory.set_session_memory("sess-2", {"turn": 1}, user_id=1, company_id=10)
        self.assertEqual(self.memory.get_session_memory("sess-2")["turn"], 1)
        prefs = self.memory.save_user_preferences(1, preferred_module="project_ai", temperature=0.2)
        self.assertEqual(prefs["preferred_module"], "project_ai")
        self.assertAlmostEqual(prefs["temperature"], 0.2)

    def test_memory_snapshot_contains_sections(self):
        self.memory.append_conversation(session_id="sess-3", role="user", content="hi")
        snapshot = self.memory.build_memory_snapshot(session_id="sess-3", user_id=1, company_id=10)
        self.assertIn("conversation", snapshot)
        self.assertIn("preferences", snapshot)


class TestAIPermissions(unittest.TestCase):
    def test_company_access_denied_for_mismatch(self):
        db = _seed_user_company_db()
        allowed = verify_company_access(db, 1, 99)
        self.assertFalse(allowed)

    def test_company_access_allowed_for_match(self):
        db = _seed_user_company_db()
        allowed = verify_company_access(db, 1, 10)
        self.assertTrue(allowed)

    def test_record_ownership_by_created_by(self):
        db = _seed_user_company_db()
        allowed = verify_record_ownership(
            db,
            1,
            record_table="projects",
            record_id=100,
            username="alice",
        )
        self.assertTrue(allowed)

    def test_record_ownership_denied_for_other_user(self):
        db = _seed_user_company_db()
        allowed = verify_record_ownership(
            db,
            1,
            record_table="projects",
            record_id=100,
            username="bob",
        )
        self.assertFalse(allowed)

    def test_verify_ai_permissions_admin_bypass(self):
        db = _seed_user_company_db()
        request = AIRequest(
            prompt="generate report",
            user_id=1,
            company_id=10,
            is_admin=True,
        )
        result = verify_ai_permissions(db, request, AnalyticsAIModule())
        self.assertTrue(result.allowed)

    def test_verify_ai_permissions_company_denied(self):
        db = _seed_user_company_db()
        request = AIRequest(
            prompt="predict stock",
            user_id=1,
            company_id=99,
            is_admin=False,
        )
        result = verify_ai_permissions(db, request, InventoryAIModule())
        self.assertFalse(result.allowed)
        self.assertIn("Company", result.reason)


class TestAILogger(unittest.TestCase):
    def test_log_persists_execution(self):
        db = _memory_db()
        log_id = log_ai_execution(
            db,
            user_id=1,
            company_id=10,
            session_id="sess-log",
            module_key="analytics_ai",
            request_type="generate_report",
            prompt="generate report",
            context={"company": {"company_name": "Omega"}},
            response_status="completed",
            success=True,
            execution_ms=12,
        )
        self.assertGreater(log_id, 0)
        logs = list_ai_execution_logs(db, user_id=1)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["module_key"], "analytics_ai")


class TestAIEngine(unittest.TestCase):
    def setUp(self):
        self.db = _memory_db()
        ensure_ai_memory_schema(self.db)
        ensure_ai_logger_schema(self.db)

    def test_engine_executes_inventory_request(self):
        engine = AICoreEngine(
            self.db,
            config=AIEngineConfig(temperature=0.3),
            llm_provider=StubLLMProvider(),
            embedding_provider=StubEmbeddingProvider(),
        )
        request = AIRequest(
            prompt="predict stock for cement bags",
            user_id=1,
            company_id=10,
            session_id="engine-1",
            is_admin=True,
        )
        response = engine.execute(request, session_data={"username": "admin"})
        self.assertTrue(response.success)
        self.assertEqual(response.module_key, "inventory_ai")
        self.assertEqual(response.status, "completed")
        self.assertIn("llm_preview", response.data)

    def test_engine_denies_without_company_access(self):
        db = _seed_user_company_db()
        ensure_ai_memory_schema(db)
        ensure_ai_logger_schema(db)
        engine = AICoreEngine(db)
        request = AIRequest(
            prompt="predict stock",
            user_id=1,
            company_id=99,
            session_id="engine-deny",
        )
        response = engine.execute(request)
        self.assertFalse(response.success)
        self.assertEqual(response.status, "denied")

    def test_engine_validation_error_on_empty_prompt(self):
        engine = AICoreEngine(self.db)
        request = AIRequest(prompt="", user_id=1, is_admin=True)
        response = engine.execute(request)
        self.assertFalse(response.success)
        self.assertEqual(response.status, "validation_error")

    def test_process_ai_request_wrapper(self):
        response = process_ai_request(
            self.db,
            {"prompt": "summarize project progress", "is_admin": True, "user_id": 1, "company_id": 10},
        )
        self.assertTrue(response.success)
        self.assertEqual(response.module_key, "project_ai")

    def test_engine_logs_execution(self):
        engine = AICoreEngine(self.db)
        request = AIRequest(prompt="generate report", user_id=7, company_id=10, is_admin=True)
        engine.execute(request)
        logs = list_ai_execution_logs(self.db, user_id=7)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["response_status"], "completed")

    def test_custom_module_via_registry(self):
        registry = AIModuleRegistry()
        registry.register(_CustomAIModule())
        engine = AICoreEngine(self.db, registry=registry)
        request = AIRequest(
            prompt="custom",
            request_type="custom_action",
            is_admin=True,
        )
        # custom_action not in REQUEST_TYPE_ROUTES — falls back to analytics in router
        # Register route by using explicit module execution path via registry key override:
        registry.register(
            type(
                "RoutedCustom",
                (_CustomAIModule,),
                {"key": "analytics_ai", "display_name": "RoutedCustom"},
            )(),
            replace=True,
        )
        response = engine.execute(request)
        self.assertTrue(response.success)
        self.assertTrue(response.data.get("custom"))


class TestAISchemaBootstrap(unittest.TestCase):
    def test_ensure_ai_memory_schema_idempotent(self):
        db = _memory_db()
        ensure_ai_memory_schema(db)
        ensure_ai_memory_schema(db)
        tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'ai_%'"
            ).fetchall()
        }
        self.assertIn("ai_conversation_memory", tables)
        self.assertIn("ai_user_preferences", tables)


if __name__ == "__main__":
    unittest.main()
