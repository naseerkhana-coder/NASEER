"""Unit tests for project creation helper logic."""

from datetime import datetime

import pytest

from app import (
    _apply_gov_completion_fields,
    _legacy_project_guarantee_rows,
    PROJECT_GUARANTEE_TYPES,
)


def test_apply_gov_completion_date_mode():
    end, completion_time, months, mode = _apply_gov_completion_fields(
        "2025-01-01", "", "date", "", "2026-06-30",
    )
    assert mode == "date"
    assert end == "2026-06-30"
    assert completion_time == ""
    assert months is None


def test_apply_gov_completion_months_computes_end_date():
    end, completion_time, months, mode = _apply_gov_completion_fields(
        "2025-01-15", "", "months", "6", "",
    )
    assert mode == "months"
    assert months == 6.0
    assert completion_time == "6"
    assert end == "2025-07-15"


def test_legacy_guarantee_rows_from_bank_fields():
    rows = _legacy_project_guarantee_rows({
        "guarantee_type": "Bank Guarantee",
        "bank_guarantee_amount": 100000,
        "bank_guarantee_number": "BG-1",
    })
    assert len(rows) == 1
    assert rows[0]["guarantee_type"] == "Bank Guarantee"
    assert rows[0]["amount"] == 100000


def test_project_guarantee_types_include_pending_bill():
    assert "Pending Bill" in PROJECT_GUARANTEE_TYPES
