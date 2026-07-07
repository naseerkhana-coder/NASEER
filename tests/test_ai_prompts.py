"""Unit tests for Enterprise Prompt Management (MODULE-020)."""

from __future__ import annotations

import sqlite3
import unittest

from app.ai.engine import AICoreEngine, AIEngine, PromptRequest
from app.ai.prompts import (
    REQUIRED_SECTIONS,
    PromptMetadataStore,
    PromptNotFoundError,
    PromptRegistry,
    PromptValidationError,
    PromptVersion,
    get_prompt,
    get_prompt_template,
    list_prompts,
    register_all_prompts,
    substitute_variables,
)
from app.ai.prompts.base import PromptSections, PromptTemplate
from app.ai.prompts.system import SYSTEM_BASE_PROMPT
from app.ai.registry import AIRequest, list_registered_prompts, resolve_prompt_for_request


class TestPromptVersion(unittest.TestCase):
    def test_parse_and_order(self) -> None:
        v1 = PromptVersion.parse("v1.0.0")
        v2 = PromptVersion.parse("1.1.0")
        self.assertEqual(str(v1), "v1.0.0")
        self.assertLess(v1, v2)


class TestVariableSubstitution(unittest.TestCase):
    def test_double_and_single_brace(self) -> None:
        text = "Hello {{name}} at {company} — {{name}} again."
        result = substitute_variables(text, {"name": "Raj", "company": "MAXEK"})
        self.assertEqual(result, "Hello Raj at MAXEK — Raj again.")

    def test_unknown_variable_preserved(self) -> None:
        text = "Value: {{missing}}"
        self.assertEqual(substitute_variables(text, {}), "Value: {{missing}}")


class TestSectionValidation(unittest.TestCase):
    def test_missing_section_raises(self) -> None:
        sections = PromptSections(
            role="r",
            context="c",
            business_rules="b",
            permissions="p",
            output_format="o",
            validation_rules="v",
            language="en",
            company_information="",
        )
        with self.assertRaises(PromptValidationError):
            sections.validate(language_code="en", template_id="test.bad")


class TestInheritance(unittest.TestCase):
    def test_child_inherits_parent_role_when_not_overridden(self) -> None:
        child = PromptTemplate(
            domain="test",
            action="inherit",
            version=PromptVersion(1, 0, 0),
            parent=SYSTEM_BASE_PROMPT,
            translations={
                "en": PromptSections(
                    role="",
                    context="Child context for {{project_name}}.",
                    business_rules="Child rules.",
                    permissions="Child permissions.",
                    output_format="JSON.",
                    validation_rules="Validate.",
                    language="English.",
                    company_information="{{company_name}}.",
                )
            },
            expected_variables=("project_name",),
        )
        PromptRegistry.register(child)
        rendered = child.render(variables={"project_name": "Site A"})
        self.assertIn("MAXEK ERP AI Assistant", rendered)
        self.assertIn("Child context for Site A", rendered)


class TestPromptRegistry(unittest.TestCase):
    def setUp(self) -> None:
        PromptRegistry.clear()
        register_all_prompts(force=True)

    def test_register_count(self) -> None:
        items = list_prompts()
        self.assertEqual(len(items), 33)

    def test_get_prompt_sales_quotation(self) -> None:
        text = get_prompt(
            "sales",
            "quotation_summary",
            variables={
                "quotation_no": "QT-001",
                "client_name": "Client X",
                "project_name": "Bridge",
                "quotation_amount": "10 L",
            },
        )
        self.assertIn("## Role", text)
        self.assertIn("QT-001", text)
        for section in REQUIRED_SECTIONS:
            label = section.replace("_", " ").title()
            if section == "business_rules":
                label = "Business Rules"
            elif section == "output_format":
                label = "Output Format"
            elif section == "validation_rules":
                label = "Validation Rules"
            elif section == "company_information":
                label = "Company Information"
            self.assertIn(f"## {label}", text)

    def test_multilingual_hindi(self) -> None:
        text = get_prompt(
            "system",
            "base",
            language="hi",
        )
        self.assertIn("MAXEK ERP AI Assistant", text)

    def test_version_resolution_latest(self) -> None:
        template = get_prompt_template("finance", "invoice_read")
        self.assertEqual(str(template.version), "v1.0.0")

    def test_not_found_raises(self) -> None:
        with self.assertRaises(PromptNotFoundError):
            get_prompt("unknown", "missing")

    def test_missing_required_variable_raises(self) -> None:
        with self.assertRaises(PromptValidationError):
            get_prompt("sales", "quotation_summary", variables={"quotation_no": "Q1"})


class TestMetadataStore(unittest.TestCase):
    def test_sqlite_sync(self) -> None:
        PromptRegistry.clear()
        register_all_prompts(force=True)
        conn = sqlite3.connect(":memory:")
        count = PromptMetadataStore.sync_registry(conn)
        self.assertEqual(count, 33)
        row = conn.execute(
            "SELECT domain, action, version FROM ai_prompt_metadata WHERE domain='sales'"
        ).fetchall()
        self.assertTrue(any(r[1] == "quotation_summary" for r in row))


class TestAIEngineIntegration(unittest.TestCase):
    def setUp(self) -> None:
        PromptRegistry.clear()
        register_all_prompts(force=True)

    def test_engine_prepare_prompt_request(self) -> None:
        engine = AIEngine()
        response = engine.prepare(
            PromptRequest(
                domain="project",
                action="delay_risk",
                user_message="Assess delay for Q1.",
                variables={
                    "project_name": "Metro Phase 2",
                    "baseline_end_date": "2026-06-30",
                    "forecast_end_date": "2026-09-15",
                },
            )
        )
        self.assertIn("Metro Phase 2", response.system_prompt)
        self.assertEqual(response.domain, "project")
        self.assertEqual(response.action, "delay_risk")
        self.assertEqual(response.prompt_version, "v1.0.0")

    def test_registry_resolve_for_request(self) -> None:
        request = AIRequest(
            prompt="reorder alert for cement",
            request_type="stock_alert",
            prompt_variables={
                "material_name": "Cement OPC 53",
                "current_stock": "120",
                "reorder_level": "200",
                "lead_time_days": "7",
            },
        )
        text = resolve_prompt_for_request(
            request,
            module_key="inventory_ai",
            request_type="stock_alert",
            context={},
        )
        self.assertIn("Cement OPC 53", text)

    def test_list_registered_prompts(self) -> None:
        items = list_registered_prompts("sales")
        self.assertEqual(len(items), 3)


class TestDomainCoverage(unittest.TestCase):
    def setUp(self) -> None:
        PromptRegistry.clear()
        register_all_prompts(force=True)

    def test_all_domains_have_prompts(self) -> None:
        expected_domains = {
            "system",
            "sales",
            "purchase",
            "inventory",
            "finance",
            "crm",
            "hr",
            "project",
            "tender",
            "document",
            "analytics",
        }
        domains = {item["domain"] for item in list_prompts()}
        self.assertEqual(domains, expected_domains)

    def test_three_prompts_per_domain(self) -> None:
        for domain in (
            "sales",
            "purchase",
            "inventory",
            "finance",
            "crm",
            "hr",
            "project",
            "tender",
            "document",
            "analytics",
        ):
            items = list_prompts(domain)
            self.assertEqual(len(items), 3, f"Expected 3 prompts in {domain}")


if __name__ == "__main__":
    unittest.main()
