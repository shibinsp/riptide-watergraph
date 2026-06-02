"""Server error-path + SSE-failure coverage for server/app.py.

BudgetExceeded is injected by monkeypatching the imported run_task/stream_task/run_workflow/
stream_workflow names; connection/test failures by faking the gateway. All offline.
"""

from __future__ import annotations

import importlib

import pytest

from riptide_watergraph.config import McpServerConfig
from riptide_watergraph.observability.cost import BudgetExceeded

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def appmod(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CHECKPOINT_PATH", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("RIPTIDE_WATERGRAPH_DISABLE_TRACING", "1")
    m = importlib.import_module("riptide_watergraph.server.app")
    return m


@pytest.fixture
def client(appmod):
    return TestClient(appmod.app)


def _budget(*a, **k):
    raise BudgetExceeded("t", 1.0, 0.5)


# ---------- SSE budget-error branches ----------

def test_run_stream_budget_error(appmod, client, monkeypatch):
    monkeypatch.setattr(appmod, "run_task", _budget)
    body = client.get("/run/stream", params={"task": "x", "offline": True}).text
    assert '"event": "error"' in body


def test_run_trace_budget_error(appmod, client, monkeypatch):
    monkeypatch.setattr(appmod, "stream_task", _budget)
    body = client.get("/api/run/trace", params={"task": "x", "offline": True}).text
    assert '"event": "error"' in body


def test_post_message_budget_402(appmod, client, monkeypatch):
    monkeypatch.setattr(appmod, "run_task", _budget)
    assert client.post("/sessions/s1/messages", json={"task": "x", "offline": True}).status_code == 402


def test_session_stream_budget_error(appmod, client, monkeypatch):
    monkeypatch.setattr(appmod, "stream_task", _budget)
    body = client.get("/api/sessions/s1/messages/stream", params={"task": "x", "offline": True}).text
    assert '"event": "error"' in body


# ---------- tool runner: invalid args ----------

def test_tool_runner_invalid_args_400(client):
    r = client.post("/api/tools/sha256/invoke", json={"arguments": {}})  # missing required 'text'
    assert r.status_code == 400


# ---------- connection validation + apply + test ----------

def test_connection_validation_errors(appmod, client):
    appmod._connection.update({"provider": "offline", "model": "", "api_base": "", "api_key": ""})
    assert client.post("/api/connection", json={"provider": "openai", "model": ""}).status_code == 400
    assert client.post("/api/connection",
                       json={"provider": "openai", "model": "gpt-4o"}).status_code == 400  # no key
    appmod._connection.update({"provider": "offline", "model": "", "api_base": "", "api_key": ""})


def test_connection_apply_sets_api_base(appmod, client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)
    r = client.post("/api/connection", json={"provider": "custom", "model": "m",
                                             "api_key": "k", "api_base": "http://local"})
    assert r.status_code == 200
    import os
    assert os.environ.get("OPENAI_API_BASE") == "http://local"
    appmod._connection.update({"provider": "offline", "model": "", "api_base": "", "api_key": ""})


class _FailGateway:
    def __init__(self, exc):
        self._exc = exc

    async def complete(self, **kwargs):
        raise self._exc


def test_connection_test_import_error(appmod, client, monkeypatch):
    monkeypatch.setattr(appmod, "LiteLLMGateway", lambda **k: _FailGateway(ImportError("no litellm")))
    r = client.post("/api/connection/test", json={"provider": "openai", "model": "gpt-4o"}).json()
    assert r["ok"] is False and "litellm" in r["detail"]


def test_connection_test_generic_error(appmod, client, monkeypatch):
    monkeypatch.setattr(appmod, "LiteLLMGateway", lambda **k: _FailGateway(RuntimeError("boom")))
    r = client.post("/api/connection/test", json={"provider": "openai", "model": "gpt-4o"}).json()
    assert r["ok"] is False and "RuntimeError" in r["detail"]


# ---------- MCP connect failure + the real _build_mcp_client ----------

def test_mcp_connect_builder_raises_400(appmod, client, monkeypatch):
    monkeypatch.setenv("RIPTIDE_ENABLE_MCP_CONNECT", "1")
    monkeypatch.setenv("RIPTIDE_MCP_SERVERS", '[{"name":"fs","command":"x","prefix":"fs."}]')

    def boom(cfg):
        raise RuntimeError("spawn failed")
    monkeypatch.setattr(appmod, "_build_mcp_client", boom)
    assert client.post("/api/mcp/connect", json={"name": "fs"}).status_code == 400


def test_build_mcp_client_constructs_stdio_client(appmod):
    # The real builder (not monkeypatched) — constructing the client needs no SDK/subprocess.
    client_obj = appmod._build_mcp_client(McpServerConfig(name="x", command="echo", args=["a"]))
    assert client_obj.command == "echo"


# ---------- workflow run errors ----------

_CYCLE = {"name": "c", "nodes": [{"id": "a"}, {"id": "b"}],
          "edges": [{"source": "a", "target": "b"}, {"source": "b", "target": "a"}]}


def test_workflow_run_cycle_422(client):
    assert client.post("/api/workflows/run", json={"spec": _CYCLE, "offline": True}).status_code == 422


def test_workflow_run_budget_402(appmod, client, monkeypatch):
    monkeypatch.setattr(appmod, "run_workflow", _budget)
    spec = {"name": "ok", "nodes": [{"id": "a", "role": "generalist", "subtask": "do"}], "edges": []}
    assert client.post("/api/workflows/run", json={"spec": spec, "offline": True}).status_code == 402


def test_workflow_delete_404(client):
    assert client.delete("/api/workflows/does-not-exist").status_code == 404


def test_workflow_stream_invalid_spec_and_budget(appmod, client, monkeypatch):
    bad = client.get("/api/workflows/run/stream", params={"spec": "not json", "offline": True}).text
    assert '"event": "error"' in bad
    monkeypatch.setattr(appmod, "stream_workflow", _budget)
    spec = '{"name":"ok","nodes":[{"id":"a","role":"generalist","subtask":"do"}],"edges":[]}'
    body = client.get("/api/workflows/run/stream", params={"spec": spec, "offline": True}).text
    assert '"event": "error"' in body
