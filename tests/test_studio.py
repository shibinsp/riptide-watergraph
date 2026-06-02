"""Like Water Studio: SPA serving + studio API endpoints + run detail fields (offline)."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from riptide_watergraph.config import get_settings  # noqa: E402
from riptide_watergraph.observability.cost import CostTracker, UsageRecord  # noqa: E402
from riptide_watergraph.server import app  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CHECKPOINT_PATH", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("RIPTIDE_WATERGRAPH_DISABLE_TRACING", "1")
    return TestClient(app)


def test_index_serves_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "Like Water Studio" in r.text


def test_static_assets_served(client):
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/styles.css").status_code == 200


def test_api_meta(client):
    m = client.get("/api/meta").json()
    assert m["tool_count"] == 12  # 6 examples + 6 agentic dev tools (exec off)
    assert len(m["role_names"]) == 5
    assert m["models"]  # non-empty
    assert "react_steps" in m["defaults"]
    assert m["connection"]["provider"] == "offline"


def test_api_tools_returns_twelve(client):
    tools = client.get("/api/tools").json()
    assert len(tools) == 12
    names = {t["name"] for t in tools}
    assert {"read_file", "write_file", "apply_edit", "search_code"} <= names
    for t in tools:
        assert set(t) == {"name", "version", "description", "side_effecting", "json_schema"}
        assert "handler" not in t


def test_api_roles_includes_coder(client):
    roles = client.get("/api/roles").json()
    assert {r["name"] for r in roles} == {"generalist", "researcher", "analyst", "scribe", "coder"}


def test_api_eval_offline_pass_rate(client):
    rep = client.post("/api/eval", json={"offline": True}).json()
    assert rep["pass_rate"] == 1.0
    assert rep["n_total"] == 4


def test_api_costs_returns_dict(client):
    CostTracker(get_settings().usage_log_path).record(
        UsageRecord(tenant_id="acme", task="t", cost_usd=0.01)
    )
    costs = client.get("/api/costs").json()
    assert isinstance(costs, dict)
    assert "acme" in costs


def test_run_with_critic_returns_verdicts(client):
    r = client.post(
        "/run",
        json={"task": "compute 21 * 2", "offline": True, "memory": False, "critic": True},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["verdicts"]  # critic ran and produced a verdict (proves run_task forwarding)


def test_run_populates_plan_and_results(client):
    r = client.post(
        "/run",
        json={"task": "search cats and count the words and uppercase the title",
              "offline": True, "memory": False},
    )
    data = r.json()
    assert data["plan"]
    assert data["results"]
    assert data["mode"] == "swarm"


def test_connection_default_is_offline(client):
    c = client.get("/api/connection").json()
    assert c["provider"] == "offline"
    assert c["configured"] is False
    assert c["key_masked"] is None


def test_connection_set_masks_key_and_applies_env(client):
    import os

    try:
        c = client.post(
            "/api/connection",
            json={"provider": "openai", "model": "gpt-4o", "api_key": "sk-test-ABCD1234"},
        ).json()
        assert c["configured"] is True
        assert c["key_masked"].endswith("1234")
        # GET must never echo the raw secret.
        assert "sk-test-ABCD1234" not in client.get("/api/connection").text
        # The key + model are mirrored to the environment for the next run.
        assert os.environ.get("OPENAI_API_KEY") == "sk-test-ABCD1234"
        assert os.environ.get("RIPTIDE_WATERGRAPH_MODEL") == "gpt-4o"
    finally:
        # Reset so global state / env don't leak into other tests or the live server.
        client.post("/api/connection", json={"provider": "offline", "model": ""})


def test_connection_custom_requires_base_url(client):
    r = client.post("/api/connection", json={"provider": "custom", "model": "x", "api_key": "k"})
    assert r.status_code == 400
    client.post("/api/connection", json={"provider": "offline", "model": ""})


def test_connection_test_offline_ok(client):
    r = client.post("/api/connection/test", json={"provider": "offline"}).json()
    assert r["ok"] is True
