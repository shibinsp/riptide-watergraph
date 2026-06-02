"""Enterprise connector catalog: gated registration, stubs, and side-effect flags."""

from __future__ import annotations

from riptide_watergraph.tools import default_registry
from riptide_watergraph.tools.enterprise import enterprise_specs


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("RIPTIDE_ENABLE_ENTERPRISE", raising=False)
    assert enterprise_specs() == []


def test_enabled_returns_large_catalog(monkeypatch):
    monkeypatch.setenv("RIPTIDE_ENABLE_ENTERPRISE", "1")
    specs = enterprise_specs()
    assert len(specs) >= 500
    names = {s.name for s in specs}
    assert "salesforce.get" in names and "slack.send" not in names  # actions are generic verbs
    assert "github.create" in names and "snowflake.run_query" not in names


def test_every_connector_has_category_and_vendor_tag(monkeypatch):
    monkeypatch.setenv("RIPTIDE_ENABLE_ENTERPRISE", "1")
    for s in enterprise_specs():
        assert s.category  # domain
        assert "enterprise" in s.tags
        assert "." in s.name  # vendor.action


def test_read_actions_inline_write_actions_gated(monkeypatch):
    monkeypatch.setenv("RIPTIDE_ENABLE_ENTERPRISE", "1")
    by_name = {s.name: s for s in enterprise_specs()}
    assert by_name["salesforce.list"].side_effecting is False
    assert by_name["salesforce.get"].side_effecting is False
    assert by_name["salesforce.create"].side_effecting is True
    assert by_name["salesforce.delete"].side_effecting is True


def test_stub_handler_returns_string(monkeypatch):
    monkeypatch.setenv("RIPTIDE_ENABLE_ENTERPRISE", "1")
    spec = next(s for s in enterprise_specs() if s.name == "jira.create")
    out = spec.handler(payload="{}")
    assert isinstance(out, str) and "stub" in out


def test_registered_only_when_flagged(monkeypatch):
    monkeypatch.delenv("RIPTIDE_ENABLE_ENTERPRISE", raising=False)
    base = len(default_registry().all_specs())
    monkeypatch.setenv("RIPTIDE_ENABLE_ENTERPRISE", "1")
    enabled = len(default_registry().all_specs())
    assert enabled - base >= 500


def test_invoke_through_registry(monkeypatch):
    import asyncio
    monkeypatch.setenv("RIPTIDE_ENABLE_ENTERPRISE", "1")
    reg = default_registry()
    result = asyncio.run(reg.invoke("github.get", {"id": "42"}))
    assert isinstance(result, str) and "github.get" in result
