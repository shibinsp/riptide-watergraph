"""Workflow CRUD + run + SSE endpoints (offline, TestClient)."""

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


_DIAMOND = {
    "name": "diamond", "goal": "demo",
    "nodes": [
        {"id": "n1", "role": "researcher", "subtask": "search cats"},
        {"id": "n2", "role": "analyst", "subtask": "count the words"},
        {"id": "n3", "role": "scribe", "subtask": "uppercase the title"},
        {"id": "n4", "role": "scribe", "subtask": "write a summary"},
    ],
    "edges": [
        {"source": "n1", "target": "n2"}, {"source": "n1", "target": "n3"},
        {"source": "n2", "target": "n4"}, {"source": "n3", "target": "n4"},
    ],
}


def test_crud_round_trip(client):
    assert client.post("/api/workflows", json=_DIAMOND).status_code == 200
    assert "diamond" in client.get("/api/workflows").json()
    assert client.get("/api/workflows/diamond").json()["name"] == "diamond"
    assert client.delete("/api/workflows/diamond").json()["status"] == "deleted"
    assert client.get("/api/workflows/diamond").status_code == 404


def test_save_rejects_cycle_422(client):
    cyc = {"name": "c", "nodes": [{"id": "a"}, {"id": "b"}],
           "edges": [{"source": "a", "target": "b"}, {"source": "b", "target": "a"}]}
    assert client.post("/api/workflows", json=cyc).status_code == 422


def test_run_diamond_as_swarm(client):
    r = client.post("/api/workflows/run", json={"spec": _DIAMOND, "offline": True, "memory": False})
    assert r.status_code == 200
    data = r.json()
    assert data["mode"] == "swarm"
    assert len(data["plan"]) == 4
    assert len(data["results"]) == 4


def test_run_stream_emits_nodes_then_result(client):
    r = client.get("/api/workflows/run/stream",
                   params={"spec": json.dumps(_DIAMOND), "offline": True})
    assert r.status_code == 200
    events = [json.loads(line[6:]) for line in r.text.splitlines() if line.startswith("data: ")]
    kinds = [e["event"] for e in events]
    assert "node" in kinds and kinds[-1] == "result"
    assert events[-1]["result"]["mode"] == "swarm"


def test_run_stream_error_on_bad_spec(client):
    bad = {"name": "c", "nodes": [{"id": "a"}, {"id": "b"}],
           "edges": [{"source": "a", "target": "b"}, {"source": "b", "target": "a"}]}
    r = client.get("/api/workflows/run/stream", params={"spec": json.dumps(bad), "offline": True})
    events = [json.loads(line[6:]) for line in r.text.splitlines() if line.startswith("data: ")]
    assert events and events[-1]["event"] == "error"
