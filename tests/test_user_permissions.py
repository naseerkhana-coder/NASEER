"""Tests for department tab permission service (UI matrix backing store)."""

from __future__ import annotations

import sqlite3

import pytest

from user_permission_service import (
    PERMISSION_ROLE_TEMPLATES,
    actions_grant_tab_access,
    build_department_tab_catalog,
    empty_permission_actions,
    full_permission_actions,
    get_permission_role_template,
    get_user_configured_permission_departments,
    get_user_department_tab_state,
    save_user_department_tab_entries,
    save_user_permissions_matrix,
    view_only_permission_actions,
)


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE users(
            id INTEGER PRIMARY KEY,
            username TEXT
        )
        """
    )
    conn.execute("INSERT INTO users(id, username) VALUES (1, 'tester')")
    yield conn
    conn.close()


SAMPLE_CATALOG = [
    {
        "tab_key": "projects::Project Master",
        "endpoint": "projects",
        "label": "Project Master",
        "icon": "fa-folder",
        "active_endpoints": ["projects"],
    },
    {
        "tab_key": "dpr_entry::DPR Entry",
        "endpoint": "dpr_entry",
        "label": "DPR Entry",
        "icon": "fa-clipboard",
        "active_endpoints": ["dpr_entry"],
    },
]


def test_view_gate_controls_tab_grant():
    assert actions_grant_tab_access(view_only_permission_actions()) is True
    assert actions_grant_tab_access(empty_permission_actions()) is False
    assert actions_grant_tab_access(full_permission_actions()) is True


def test_build_department_tab_catalog_dedupes():
    portal = {
        "menu": [
            {"endpoint": "projects", "label": "Project Master"},
            {"endpoint": "projects", "label": "Project Master"},
        ],
        "quick_tabs": [],
    }
    tabs = build_department_tab_catalog("projects", portal=portal)
    assert len(tabs) == 1
    assert tabs[0]["tab_key"] == "projects::Project Master"


def test_save_and_load_permission_matrix(db):
    entries = [
        {
            "tab_key": "projects::Project Master",
            "actions": full_permission_actions(),
        },
        {
            "tab_key": "dpr_entry::DPR Entry",
            "actions": view_only_permission_actions(),
        },
    ]
    saved = save_user_department_tab_entries(db, 1, "projects", entries, SAMPLE_CATALOG)
    assert saved == 2

    state = get_user_department_tab_state(db, 1, "projects", SAMPLE_CATALOG)
    by_key = {row["tab_key"]: row for row in state}
    assert by_key["projects::Project Master"]["granted"] is True
    assert by_key["projects::Project Master"]["actions"]["create"] is True
    assert by_key["dpr_entry::DPR Entry"]["actions"]["view"] is True
    assert by_key["dpr_entry::DPR Entry"]["actions"]["create"] is False

    configured = get_user_configured_permission_departments(db, 1)
    assert configured == ["projects"]


def test_bulk_save_permissions_matrix(db):
    def resolver(_slug: str):
        return SAMPLE_CATALOG

    saved = save_user_permissions_matrix(
        db,
        1,
        {
            "projects": [
                {"tab_key": "projects::Project Master", "actions": view_only_permission_actions()},
            ]
        },
        catalog_resolver=resolver,
    )
    assert saved["projects"] == 1


def test_role_templates_defined():
    assert len(PERMISSION_ROLE_TEMPLATES) >= 8
    pm = get_permission_role_template("project_manager")
    assert pm is not None
    assert "projects" in pm["departments"]
    assert pm["actions"]["view"] is True
