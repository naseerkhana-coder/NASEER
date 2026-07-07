"""Extensible widget registry for Enterprise Dashboard (MODULE-008).

Future modules register widgets without modifying dashboard core:

    from dashboard_widget_registry import DashboardWidgetRegistry, WidgetSpec

    DashboardWidgetRegistry.register(
        WidgetSpec(
            key="my_module_summary",
            title="My Module",
            category="operations",
            default_width=4,
            default_height=2,
        ),
        provider=my_module_widget_data,
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

WidgetProvider = Callable[[Any, dict[str, Any]], dict[str, Any]]
PermissionCheck = Callable[[Any, dict[str, Any]], bool]


@dataclass(frozen=True)
class WidgetSpec:
    key: str
    title: str
    category: str
    default_width: int = 4
    default_height: int = 2
    min_width: int = 2
    min_height: int = 1
    supported_roles: tuple[str, ...] = ()
    permission_endpoint: str = ""
    permission_action: str = "view"
    permission_module: str = ""
    refresh_seconds: int = 300
    description: str = ""


@dataclass
class RegisteredWidget:
    spec: WidgetSpec
    provider: WidgetProvider
    permission_check: PermissionCheck | None = None


class DashboardWidgetRegistry:
    """Central registry for dashboard widgets — plugin entry point for modules."""

    _widgets: dict[str, RegisteredWidget] = {}

    @classmethod
    def register(
        cls,
        spec: WidgetSpec,
        provider: WidgetProvider,
        *,
        permission_check: PermissionCheck | None = None,
    ) -> None:
        if not spec.key or not spec.key.strip():
            raise ValueError("Widget key is required")
        key = spec.key.strip()
        if key in cls._widgets:
            raise ValueError(f"Widget already registered: {key}")
        cls._widgets[key] = RegisteredWidget(
            spec=spec,
            provider=provider,
            permission_check=permission_check,
        )

    @classmethod
    def unregister(cls, key: str) -> bool:
        return cls._widgets.pop(key, None) is not None

    @classmethod
    def get(cls, key: str) -> RegisteredWidget | None:
        return cls._widgets.get(key)

    @classmethod
    def all_specs(cls) -> list[WidgetSpec]:
        return [w.spec for w in cls._widgets.values()]

    @classmethod
    def all_keys(cls) -> list[str]:
        return list(cls._widgets.keys())

    @classmethod
    def clear(cls) -> None:
        """Test helper — clears all registrations."""
        cls._widgets.clear()
