"""Chat backend: enriched session turns, streaming chat, and clear (offline)."""

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


def test_message_stores_enriched_turn_with_knobs(client):
    r = client.post(
        "/sessions/c1/messages",
        json={"task": "compute 21 * 2", "offline": True, "memory": False,
              "critic": True, "temperature": 0.5},
    )
    assert r.status_code == 200
    assert r.json()["verdicts"]  # critic knob honored on a chat turn
    turns = client.get("/sessions/c1").json()["turns"]
    assert len(turns) == 1
    assert {"task", "answer", "mode", "plan", "roles", "results", "verdicts"} <= set(turns[0])


def test_streaming_chat_appends_turn(client):
    r = client.get("/api/sessions/c2/messages/stream",
                   params={"task": "compute 21 * 2", "offline": True})
    assert r.status_code == 200
    events = [json.loads(line[6:]) for line in r.text.splitlines() if line.startswith("data: ")]
    kinds = [e["event"] for e in events]
    assert "node" in kinds and kinds[-1] == "result"
    assert events[-1]["result"]["final_answer"]
    assert len(client.get("/sessions/c2").json()["turns"]) == 1


def test_multi_turn_history_and_clear(client):
    client.post("/sessions/c3/messages", json={"task": "first", "offline": True})
    client.post("/sessions/c3/messages", json={"task": "second", "offline": True})
    assert len(client.get("/sessions/c3").json()["turns"]) == 2
    assert client.delete("/sessions/c3").json()["status"] == "cleared"
    assert client.get("/sessions/c3").json()["turns"] == []


def test_run_accepts_sampling(client):
    r = client.post("/run", json={"task": "hi", "offline": True, "memory": False,
                                  "temperature": 0.8, "top_p": 0.9, "max_tokens": 128})
    assert r.status_code == 200
