"""Studio Tool Runner endpoint + live-trace SSE (offline, no network)."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from riptide_watergraph.server import app  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CHECKPOINT_PATH", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("RIPTIDE_WATERGRAPH_DISABLE_TRACING", "1")
    return TestClient(app)


def test_tool_runner_runs_readonly_tool(client):
    r = client.post("/api/tools/sha256/invoke", json={"arguments": {"text": "hello"}})
    assert r.status_code == 200
    assert r.json()["result"] == (
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824")


def test_tool_runner_refuses_side_effecting(client):
    r = client.post("/api/tools/write_file/invoke",
                    json={"arguments": {"path": "x.txt", "content": "y"}})
    assert r.status_code == 400


def test_tool_runner_unknown_tool_404(client):
    r = client.post("/api/tools/nope/invoke", json={"arguments": {}})
    assert r.status_code == 404


def test_trace_streams_nodes_then_result(client):
    r = client.get("/api/run/trace", params={"task": "compute 21 * 2", "offline": True})
    assert r.status_code == 200
    events = [json.loads(line[len("data: "):])
              for line in r.text.splitlines() if line.startswith("data: ")]
    kinds = [e["event"] for e in events]
    assert "node" in kinds
    assert kinds[-1] == "result"
    assert events[-1]["result"]["final_answer"]
