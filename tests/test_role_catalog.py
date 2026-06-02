"""The role catalog: 100+ specialists, valid tool references, sound routing."""

from __future__ import annotations

import os

from riptide_watergraph.swarm.roles import all_roles, get_role, role_for
from riptide_watergraph.tools import default_registry


def test_catalog_has_100_plus_roles():
    roles = all_roles()
    assert len(roles) >= 100
    names = [r.name for r in roles]
    assert len(names) == len(set(names))  # unique names


def test_every_role_references_real_tools():
    os.environ["RIPTIDE_ENABLE_EXEC"] = "1"  # so coder's exec tools count as registered
    try:
        valid = {s.name for s in default_registry().all_specs()}
    finally:
        del os.environ["RIPTIDE_ENABLE_EXEC"]
    for role in all_roles():
        if role.tools is None:
            continue
        unknown = [t for t in role.tools if t not in valid]
        assert not unknown, f"role {role.name} references unknown tools: {unknown}"


def test_every_role_prompt_marks_a_worker():
    # The graph + scripted gateways match on the "You are a worker" phrasing.
    assert all("You are a worker" in r.system_prompt for r in all_roles())


def test_roles_have_categories_and_descriptions():
    for r in all_roles():
        assert r.category
        if r.name != "generalist":
            assert r.description


def test_role_for_routes_specialists():
    assert role_for("write a SQL query for the report") == "sql_developer"
    assert role_for("deploy the service to kubernetes") == "devops_engineer"
    assert role_for("audit for security vulnerabilities") == "security_analyst"
    assert role_for("write the readme documentation") == "technical_writer"
    assert role_for("fix the bug in app.py") == "coder"
    assert role_for("tell me a joke") == "generalist"


def test_get_role_resolves_catalog_and_falls_back():
    assert get_role("data_engineer").name == "data_engineer"
    assert get_role("does_not_exist").name == "generalist"
