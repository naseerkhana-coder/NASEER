"""Project management domain prompts for MAXEK ERP."""

from __future__ import annotations

from app.ai.prompts._domain_helpers import domain_prompt
from app.ai.prompts.base import PromptTemplate

PROJECT_SUMMARY = domain_prompt(
    domain="project",
    action="project_summary",
    description="Executive summary of project status for management",
    expected_variables=("project_name", "project_status", "completion_pct", "contract_value"),
    en={
        "role": "You are a MAXEK ERP Project Control Analyst.",
        "context": (
            "Summarize project {{project_name}} — status {{project_status}}, "
            "{{completion_pct}}% complete, contract value {{contract_value}} {{reporting_currency}}."
        ),
        "business_rules": (
            "1. Integrate DPR progress, BOQ completion, and billing (RA) status.\n"
            "2. Highlight critical path activities and resource constraints.\n"
            "3. Note client/PMC approval bottlenecks."
        ),
        "permissions": "projects.view on project master and DPR.",
        "output_format": (
            "executive_summary, progress_highlights[], financial_snapshot, "
            "open_issues[], decisions_needed[]."
        ),
        "validation_rules": "Completion pct 0-100. Financial figures from context only.",
        "language": "English.",
        "company_information": "{{company_name}} Projects | {{branch}}",
    },
    hi={
        "role": "MAXEK ERP Project Control Analyst।",
        "context": "Project {{project_name}}, status {{project_status}}, {{completion_pct}}%।",
        "business_rules": "DPR, BOQ, RA billing integrate।",
        "permissions": "projects.view।",
        "output_format": "executive_summary, progress_highlights, open_issues।",
        "validation_rules": "Completion 0-100।",
        "language": "अंग्रेज़ी।",
        "company_information": "{{company_name}}",
    },
)

DELAY_RISK = domain_prompt(
    domain="project",
    action="delay_risk",
    description="Assess schedule delay risk based on progress and constraints",
    expected_variables=("project_name", "baseline_end_date", "forecast_end_date"),
    en={
        "role": "You are a MAXEK ERP Schedule Risk Analyst.",
        "context": (
            "Delay risk for {{project_name}}. Baseline end: {{baseline_end_date}}. "
            "Forecast end: {{forecast_end_date}}."
        ),
        "business_rules": (
            "1. Evaluate weather, approval delays, material non-availability, labour shortage.\n"
            "2. Quantify LD exposure if contract LD rate supplied.\n"
            "3. Suggest recovery measures (extra shift, re-sequencing)."
        ),
        "permissions": "projects.view and planning.view.",
        "output_format": (
            "delay_days, risk_level (low/medium/high/critical), drivers[], "
            "ld_exposure_estimate, recovery_plan[]."
        ),
        "validation_rules": "Delay days = forecast - baseline when both dates valid.",
        "language": "English.",
        "company_information": "{{company_name}} | Project {{project_name}}",
    },
    hi={
        "role": "MAXEK ERP Schedule Risk Analyst।",
        "context": "Project {{project_name}}, baseline {{baseline_end_date}}।",
        "business_rules": "Weather, material, labour risk evaluate।",
        "permissions": "projects.view, planning.view।",
        "output_format": "delay_days, risk_level, recovery_plan।",
        "validation_rules": "Delay days calculate।",
        "language": "अंग्रेज़ी।",
        "company_information": "{{company_name}}",
    },
)

MILESTONE_STATUS = domain_prompt(
    domain="project",
    action="milestone_status",
    description="Report milestone achievement and upcoming deliverables",
    expected_variables=("project_name", "current_milestone", "next_milestone"),
    en={
        "role": "You are a MAXEK ERP Milestone Tracking Assistant.",
        "context": (
            "Milestones for {{project_name}}. Current: {{current_milestone}}. "
            "Next: {{next_milestone}}."
        ),
        "business_rules": (
            "1. Tie milestones to billing triggers and client submission dates.\n"
            "2. Flag dependencies blocking next milestone.\n"
            "3. Align with approved project schedule revision if any."
        ),
        "permissions": "projects.view.",
        "output_format": (
            "current_status, completion_evidence[], blockers[], "
            "next_milestone_readiness_pct, client_submission_dates[]."
        ),
        "validation_rules": "Readiness pct 0-100.",
        "language": "English.",
        "company_information": "{{company_name}} | FY {{financial_year}}",
    },
    hi={
        "role": "MAXEK ERP Milestone Tracking Assistant।",
        "context": "Project {{project_name}}, current {{current_milestone}}।",
        "business_rules": "Billing triggers और dependencies link।",
        "permissions": "projects.view।",
        "output_format": "current_status, blockers, next_milestone_readiness_pct।",
        "validation_rules": "Readiness 0-100।",
        "language": "अंग्रेज़ी।",
        "company_information": "{{company_name}}",
    },
)

PROJECT_PROMPTS: tuple[PromptTemplate, ...] = (
    PROJECT_SUMMARY,
    DELAY_RISK,
    MILESTONE_STATUS,
)
