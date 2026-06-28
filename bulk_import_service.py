"""Shared bulk import framework — parse spreadsheets, validate, build templates."""

from __future__ import annotations

import io
import re
from datetime import datetime
from typing import Any, Callable

import pandas as pd
from openpyxl import Workbook
from werkzeug.datastructures import FileStorage

ImportErrorDict = dict[str, Any]
RowDict = dict[str, Any]

DATE_PATTERNS = (
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d-%m-%y",
    "%d/%m/%y",
)

PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$", re.I)
GSTIN_RE = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$",
    re.I,
)
ACCOUNT_RE = re.compile(r"^[0-9A-Za-z\-/]{4,20}$")


def normalize_header(name: str) -> str:
    text = str(name or "").strip().lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", "_", text)
    return text


def parse_upload(file_storage: FileStorage | None) -> tuple[list[RowDict], str | None]:
    """Parse uploaded xlsx/csv into row dicts with _row_num (1-based Excel row)."""
    if not file_storage or not file_storage.filename:
        return [], "No file uploaded."
    filename = file_storage.filename.lower()
    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(file_storage)
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(file_storage)
        else:
            return [], "Unsupported file type. Upload .xlsx, .xls, or .csv."
    except Exception as exc:
        return [], f"Could not read file: {exc}"

    if df.empty:
        return [], "File has no data rows."

    col_map = {normalize_header(c): c for c in df.columns}
    rows: list[RowDict] = []
    for idx, series in df.iterrows():
        row: RowDict = {"_row_num": int(idx) + 2}
        for norm, orig in col_map.items():
            val = series.get(orig)
            if pd.isna(val):
                row[norm] = ""
            elif isinstance(val, float) and val == int(val):
                row[norm] = str(int(val))
            else:
                row[norm] = str(val).strip() if val is not None else ""
        rows.append(row)
    return rows, None


def error_row(
    row_num: int | str,
    column: str,
    error: str,
    suggested_fix: str = "",
) -> ImportErrorDict:
    return {
        "row": row_num,
        "column": column,
        "error": error,
        "suggested_fix": suggested_fix or "Correct the value and re-validate.",
    }


def validate_required(
    row: RowDict,
    fields: list[tuple[str, str]],
) -> list[ImportErrorDict]:
    """fields: [(column_key, display_name), ...]"""
    errors: list[ImportErrorDict] = []
    row_num = row.get("_row_num", "?")
    for key, label in fields:
        if not str(row.get(key, "")).strip():
            errors.append(
                error_row(row_num, label, f"{label} is required.", f"Enter {label}.")
            )
    return errors


def validate_duplicates(
    rows: list[RowDict],
    key_field: str,
    display_column: str,
) -> list[ImportErrorDict]:
    seen: dict[str, int] = {}
    errors: list[ImportErrorDict] = []
    for row in rows:
        key = str(row.get(key_field, "")).strip().upper()
        if not key:
            continue
        row_num = row.get("_row_num", "?")
        if key in seen:
            errors.append(
                error_row(
                    row_num,
                    display_column,
                    f"Duplicate {display_column}: {key}.",
                    f"Use a unique {display_column} (also on row {seen[key]}).",
                )
            )
        else:
            seen[key] = int(row_num) if str(row_num).isdigit() else 0
    return errors


def validate_date_value(value: str, column: str, row_num: int | str) -> list[ImportErrorDict]:
    text = str(value or "").strip()
    if not text:
        return []
    for fmt in DATE_PATTERNS:
        try:
            datetime.strptime(text, fmt)
            return []
        except ValueError:
            continue
    return [
        error_row(
            row_num,
            column,
            f"Invalid date: {text}.",
            "Use YYYY-MM-DD or DD-MM-YYYY.",
        )
    ]


def validate_gst(value: str, column: str, row_num: int | str) -> list[ImportErrorDict]:
    text = str(value or "").strip().upper()
    if not text:
        return []
    if not GSTIN_RE.match(text):
        return [
            error_row(
                row_num,
                column,
                f"Invalid GSTIN: {text}.",
                "Enter a valid 15-character GSTIN.",
            )
        ]
    return []


def validate_pan(value: str, column: str, row_num: int | str) -> list[ImportErrorDict]:
    text = str(value or "").strip().upper()
    if not text:
        return []
    if not PAN_RE.match(text):
        return [
            error_row(
                row_num,
                column,
                f"Invalid PAN: {text}.",
                "Enter PAN as AAAAA9999A.",
            )
        ]
    return []


def validate_account(value: str, column: str, row_num: int | str) -> list[ImportErrorDict]:
    text = str(value or "").strip()
    if not text:
        return []
    if not ACCOUNT_RE.match(text):
        return [
            error_row(
                row_num,
                column,
                f"Invalid account number: {text}.",
                "Use 4–20 alphanumeric characters.",
            )
        ]
    return []


def validate_unit(
    value: str,
    column: str,
    row_num: int | str,
    allowed: list[str] | None = None,
) -> list[ImportErrorDict]:
    text = str(value or "").strip()
    if not text:
        return []
    if allowed and text not in allowed:
        return [
            error_row(
                row_num,
                column,
                f"Unknown unit: {text}.",
                f"Use one of: {', '.join(allowed[:8])}{'…' if len(allowed) > 8 else ''}.",
            )
        ]
    return []


def validate_project_ref(
    db,
    project_ref: str,
    column: str,
    row_num: int | str,
) -> list[ImportErrorDict]:
    text = str(project_ref or "").strip()
    if not text:
        return []
    row = db.execute(
        "SELECT id FROM projects WHERE project_code=? OR CAST(id AS TEXT)=? LIMIT 1",
        (text, text),
    ).fetchone()
    if not row:
        return [
            error_row(
                row_num,
                column,
                f"Project not found: {text}.",
                "Enter a valid project code or ID from Projects master.",
            )
        ]
    return []


def build_xlsx_template(columns: list[str], sample_row: list[Any] | None = None) -> io.BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = "Import"
    ws.append(columns)
    if sample_row:
        ws.append(sample_row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def validation_result(
    rows: list[RowDict],
    errors: list[ImportErrorDict],
    *,
    preview_limit: int = 100,
) -> dict[str, Any]:
    valid_count = max(0, len(rows) - len({e["row"] for e in errors if e.get("row")}))
    return {
        "ok": len(errors) == 0,
        "total_rows": len(rows),
        "error_count": len(errors),
        "valid_row_estimate": valid_count if not errors else max(0, len(rows) - len(errors)),
        "errors": errors,
        "preview": rows[:preview_limit],
    }


ModuleValidator = Callable[..., tuple[list[RowDict], list[ImportErrorDict]]]
ModuleSaver = Callable[..., dict[str, Any]]
