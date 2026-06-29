"""Tenant context helpers for bulk import — scoping inserts and queries."""

from __future__ import annotations

from typing import Any

from tenant_isolation import get_tenant_context


def get_import_customer_id(session=None, jwt_payload: dict[str, Any] | None = None) -> int | None:
    """Return customer_id for import scoping when tenant context is set."""
    ctx = get_tenant_context(session=session, jwt_payload=jwt_payload)
    raw = ctx.get("customer_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def tenant_filter_sql(
    table_alias: str,
    customer_id: int | None,
    *,
    prefix_and: bool = True,
) -> tuple[str, list[Any]]:
    """Build SQL fragment filtering by customer_id when set."""
    if customer_id is None:
        return "", []
    alias = f"{table_alias}." if table_alias else ""
    clause = f"{alias}customer_id=?"
    if prefix_and:
        clause = f" AND {clause}"
    return clause, [customer_id]


def apply_customer_id(params: tuple | list, customer_id: int | None) -> tuple[Any, ...]:
    """Append customer_id to INSERT values when tenant is active."""
    values = list(params)
    if customer_id is not None:
        values.append(customer_id)
    return tuple(values)
