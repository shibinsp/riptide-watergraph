"""OpenAI-compatible ``POST /v1/chat/completions`` endpoint (non-stream + SSE)."""

from __future__ import annotations

import importlib
import json

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CHECKPOINT_PATH", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("RIPTIDE_WATERGRAPH_DISABLE_TRACING", "1")
    from riptide_watergraph.server import app
    return TestClient(app)


@pytest.fixture
def appmod():
    return importlib.import_module("riptide_watergraph.server.app")


def test_chat_completion_non_stream_shape(client):
    """A non-stream request returns a well-formed chat.completion object."""
    r = client.post("/v1/chat/completions", json={
        "model": "demo",
        "messages": [{"role": "user", "content": "compute 21 * 2"}],
        "offline": True,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["object"] == "chat.completion"
    assert body["id"].startswith("chatcmpl-")
    assert body["model"] == "demo"
    choice = body["choices"][0]
    assert choice["finish_reason"] == "stop"
    assert choice["message"]["role"] == "assistant"
    assert isinstance(choice["message"]["content"], str) and choice["message"]["content"]
    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
        assert k in body["usage"]


def test_chat_completion_uses_history(client):
    """Earlier user/assistant messages are accepted as history (last msg is the task)."""
    r = client.post("/v1/chat/completions", json={
        "messages": [
            {"role": "system", "content": "be terse"},
            {"role": "user", "content": "remember the number 7"},
            {"role": "assistant", "content": "ok"},
            {"role": "user", "content": "what is 21 * 2?"},
        ],
        "offline": True,
    })
    assert r.status_code == 200
    assert r.json()["choices"][0]["message"]["content"]


def test_chat_completion_stream_chunks_then_done(client):
    """A streaming request yields chat.completion.chunk SSE deltas then [DONE]."""
    body = client.post("/v1/chat/completions", json={
        "model": "demo",
        "messages": [{"role": "user", "content": "compute 21 * 2"}],
        "stream": True,
        "offline": True,
    }).text
    lines = [ln[6:] for ln in body.splitlines() if ln.startswith("data: ")]
    assert lines[-1] == "[DONE]"
    chunks = [json.loads(x) for x in lines[:-1]]
    assert all(c["object"] == "chat.completion.chunk" for c in chunks)
    # at least one content delta, and the final chunk closes with finish_reason=stop
    assert any(c["choices"][0]["delta"].get("content") for c in chunks)
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"


def test_chat_completion_empty_messages_400(client):
    """An empty messages array is rejected with 400."""
    r = client.post("/v1/chat/completions", json={"messages": [], "offline": True})
    assert r.status_code == 400


def test_chat_completion_budget_exceeded_402(client, appmod, monkeypatch):
    """A BudgetExceeded from run_task surfaces as HTTP 402."""
    from riptide_watergraph.observability.cost import BudgetExceeded

    def _budget(*a, **k):
        raise BudgetExceeded("t", 1.0, 0.5)
    monkeypatch.setattr(appmod, "run_task", _budget)

    r = client.post("/v1/chat/completions", json={
        "messages": [{"role": "user", "content": "x"}], "offline": True})
    assert r.status_code == 402


def test_chat_completion_stream_error_chunk(client, appmod, monkeypatch):
    """A gateway exception during streaming surfaces as an error delta, never a crash."""
    async def bad_stream(*a, **k):
        raise RuntimeError("boom")
        yield "unreachable"  # pragma: no cover

    monkeypatch.setattr(appmod, "stream_chat_tokens", bad_stream)
    body = client.post("/v1/chat/completions", json={
        "messages": [{"role": "user", "content": "x"}],
        "stream": True, "offline": True,
    }).text
    lines = [ln[6:] for ln in body.splitlines() if ln.startswith("data: ")]
    assert lines[-1] == "[DONE]"
    chunks = [json.loads(x) for x in lines[:-1]]
    assert any("[error]" in (c["choices"][0]["delta"].get("content") or "") for c in chunks)
