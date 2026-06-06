"""Track v0.11.0: real token-streaming + interactive HITL endpoints."""

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


# ---------- /api/chat/stream (direct token streaming) ----------

def test_chat_stream_offline_yields_token_then_done(client):
    """The offline DemoGateway yields the answer as a single token event."""
    body = client.get("/api/chat/stream", params={
        "message": "compute 21 * 2",
        "offline": True,
    }).text
    events = [ln[6:] for ln in body.splitlines() if ln.startswith("data: ")]
    parsed = [json.loads(e) for e in events]
    kinds = [e["event"] for e in parsed]
    assert "token" in kinds
    assert kinds[-1] == "done"


def test_chat_stream_with_sampling_params(client):
    """Sampling params are accepted without error (offline ignores them)."""
    r = client.get("/api/chat/stream", params={
        "message": "hello",
        "offline": True,
        "temperature": 0.5,
        "max_tokens": 100,
    })
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]


def test_chat_stream_error_event_on_exception(client, appmod, monkeypatch):
    """A gateway exception surfaces as an error SSE event (never crashes)."""
    async def bad_stream(**kwargs):
        raise RuntimeError("simulated failure")
        yield "unreachable"

    # Patch stream_chat_tokens in the server module's namespace (it's already imported).
    monkeypatch.setattr(appmod, "stream_chat_tokens", bad_stream)
    body = client.get("/api/chat/stream", params={"message": "x", "offline": True}).text
    events = [json.loads(ln[6:]) for ln in body.splitlines() if ln.startswith("data: ")]
    assert any(e["event"] == "error" for e in events)


# ---------- /api/run/interactive + /api/run/{thread_id}/resume ----------

def test_interactive_run_completes_without_interrupt(client):
    """A purely read-only task finishes immediately (returns RunResult fields)."""
    r = client.post("/api/run/interactive", json={
        "task": "compute 21 * 2",
        "offline": True,
        "memory": False,
    })
    assert r.status_code == 200
    body = r.json()
    # Completed run has 'final_answer', not 'status: pending_approval'
    assert "final_answer" in body


def test_interactive_run_returns_pending_shape(client, appmod, monkeypatch):
    """run_interactive returning PendingApproval is serialised correctly."""
    from riptide_watergraph.service import PendingApproval

    def fake_interactive(*a, **k):
        return PendingApproval(thread_id="tid-test",
                               action={"type": "tool_approval", "tool": "write_note",
                                       "arguments": {"path": "x"}, "subtask": "save"})
    monkeypatch.setattr(appmod, "run_interactive", fake_interactive)

    r = client.post("/api/run/interactive", json={
        "task": "save a note", "offline": True, "memory": False})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "pending_approval"
    assert body["thread_id"] == "tid-test"
    assert body["action"]["tool"] == "write_note"


def test_resume_approved_returns_result(client, appmod, monkeypatch):
    """Approving the pending action resumes and completes the run."""
    from riptide_watergraph.service import RunResult

    def fake_resume(thread_id, *, approved, answer, task, settings=None):
        assert approved is True
        return RunResult(tenant_id="default", final_answer="done: note saved",
                         mode="single")
    monkeypatch.setattr(appmod, "resume_interactive", fake_resume)

    r = client.post("/api/run/tid-test/resume",
                    json={"approved": True, "answer": None, "task": "save a note"})
    assert r.status_code == 200
    assert r.json()["final_answer"] == "done: note saved"


def test_resume_denied_returns_result(client, appmod, monkeypatch):
    """Denying the action still returns a valid RunResult."""
    from riptide_watergraph.service import RunResult

    def fake_resume(thread_id, *, approved, answer, task, settings=None):
        assert approved is False
        return RunResult(tenant_id="default", final_answer="(action denied)", mode="single")
    monkeypatch.setattr(appmod, "resume_interactive", fake_resume)

    r = client.post("/api/run/tid-test/resume",
                    json={"approved": False, "answer": None, "task": "save a note"})
    assert r.status_code == 200
    assert r.json()["final_answer"] == "(action denied)"


def test_resume_propagates_error_as_400(client, appmod, monkeypatch):
    """A bad thread_id (not in the checkpointer) raises and returns 400."""
    def bad_resume(*a, **k):
        raise ValueError("no checkpoint for thread")
    monkeypatch.setattr(appmod, "resume_interactive", bad_resume)

    r = client.post("/api/run/bad-thread/resume",
                    json={"approved": True, "answer": None, "task": ""})
    assert r.status_code == 400


def test_interactive_run_budget_exceeded_returns_402(client, appmod, monkeypatch):
    """BudgetExceeded from run_interactive bubbles out as HTTP 402."""
    from riptide_watergraph.observability.cost import BudgetExceeded

    def _budget(*a, **k):
        raise BudgetExceeded("t", 1.0, 0.5)
    monkeypatch.setattr(appmod, "run_interactive", _budget)

    r = client.post("/api/run/interactive",
                    json={"task": "x", "offline": True, "memory": False})
    assert r.status_code == 402


def test_resume_budget_exceeded_returns_402(client, appmod, monkeypatch):
    """BudgetExceeded from resume_interactive bubbles out as HTTP 402."""
    from riptide_watergraph.observability.cost import BudgetExceeded

    def _budget(*a, **k):
        raise BudgetExceeded("t", 1.0, 0.5)
    monkeypatch.setattr(appmod, "resume_interactive", _budget)

    r = client.post("/api/run/tid-test/resume",
                    json={"approved": True, "answer": None, "task": ""})
    assert r.status_code == 402
