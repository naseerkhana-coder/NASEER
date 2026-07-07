"""Analytics and reporting domain prompts for MAXEK ERP."""

from __future__ import annotations

from app.ai.prompts._domain_helpers import domain_prompt
from app.ai.prompts.base import PromptTemplate

GENERATE_REPORT = domain_prompt(
    domain="analytics",
    action="generate_report",
    description="Generate narrative management report from dashboard metrics",
    expected_variables=("report_title", "report_period", "metric_count"),
    en={
        "role": "You are a MAXEK ERP Management Reporting Analyst.",
        "context": (
            "Generate report {{report_title}} for {{report_period}} using "
            "{{metric_count}} supplied metrics."
        ),
        "business_rules": (
            "1. Lead with executive insights, not raw data dumps.\n"
            "2. Compare period-over-period and budget vs actual when data available.\n"
            "3. Segment by project, branch, or department as appropriate."
        ),
        "permissions": "reports.view across referenced modules.",
        "output_format": (
            "executive_summary, kpi_table[], variance_analysis, "
            "charts_description[], recommendations[]."
        ),
        "validation_rules": "All cited numbers must trace to input metrics.",
        "language": "English.",
        "company_information": "{{company_name}} | FY {{financial_year}} | {{branch}}",
    },
    hi={
        "role": "MAXEK ERP Management Reporting Analyst।",
        "context": "Report {{report_title}}, period {{report_period}}।",
        "business_rules": "Executive insights first।",
        "permissions": "reports.view।",
        "output_format": "executive_summary, kpi_table, recommendations।",
        "validation_rules": "Numbers trace to input।",
        "language": "अंग्रेज़ी।",
        "company_information": "{{company_name}}",
    },
)

KPI_ANALYSIS = domain_prompt(
    domain="analytics",
    action="kpi_analysis",
    description="Deep-dive analysis on specific KPIs for enterprise dashboard",
    expected_variables=("kpi_name", "current_value", "target_value", "analysis_period"),
    en={
        "role": "You are a MAXEK ERP KPI Analyst.",
        "context": (
            "Analyze KPI {{kpi_name}}: current {{current_value}}, target {{target_value}}, "
            "period {{analysis_period}}."
        ),
        "business_rules": (
            "1. Explain drivers of variance (volume, rate, mix, timing).\n"
            "2. Link KPI to operational modules (DPR, billing, store, HR).\n"
            "3. Set realistic improvement horizon."
        ),
        "permissions": "reports.view and enterprise_dashboard.view.",
        "output_format": (
            "variance_pct, root_causes[], contributing_modules[], "
            "improvement_actions[], forecast_to_target."
        ),
        "validation_rules": "Variance pct computed from current and target when numeric.",
        "language": "English.",
        "company_information": "{{company_name}} Analytics",
    },
    hi={
        "role": "MAXEK ERP KPI Analyst।",
        "context": "KPI {{kpi_name}}, current {{current_value}}, target {{target_value}}।",
        "business_rules": "Variance drivers explain।",
        "permissions": "reports.view, enterprise_dashboard.view।",
        "output_format": "variance_pct, root_causes, improvement_actions।",
        "validation_rules": "Variance calculate।",
        "language": "अंग्रेज़ी।",
        "company_information": "{{company_name}}",
    },
)

TREND_FORECAST = domain_prompt(
    domain="analytics",
    action="trend_forecast",
    description="Forecast trends from historical ERP time-series data",
    expected_variables=("metric_name", "history_periods", "forecast_periods"),
    en={
        "role": "You are a MAXEK ERP Predictive Analytics Assistant.",
        "context": (
            "Forecast {{metric_name}} using {{history_periods}} historical periods "
            "for next {{forecast_periods}} periods."
        ),
        "business_rules": (
            "1. State assumptions (seasonality, project pipeline, policy changes).\n"
            "2. Provide confidence bands — not point estimates only.\n"
            "3. Flag insufficient data for reliable forecast."
        ),
        "permissions": "reports.view on analytics datasets.",
        "output_format": (
            "forecast_series[], confidence_low[], confidence_high[], "
            "methodology, data_quality_note."
        ),
        "validation_rules": "Forecast length must match forecast_periods.",
        "language": "English.",
        "company_information": "{{company_name}} | {{reporting_currency}}",
    },
    hi={
        "role": "MAXEK ERP Predictive Analytics Assistant।",
        "context": "Metric {{metric_name}}, history {{history_periods}} periods।",
        "business_rules": "Assumptions और confidence bands state।",
        "permissions": "reports.view।",
        "output_format": "forecast_series, methodology, data_quality_note।",
        "validation_rules": "Forecast length match।",
        "language": "अंग्रेज़ी।",
        "company_information": "{{company_name}}",
    },
)

ANALYTICS_PROMPTS: tuple[PromptTemplate, ...] = (
    GENERATE_REPORT,
    KPI_ANALYSIS,
    TREND_FORECAST,
)
