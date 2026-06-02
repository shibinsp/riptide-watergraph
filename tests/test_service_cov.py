"""service.py coverage: composer selection + the auto-approve interrupt loops.

The approval branch is driven by an offline ``save a note`` run (write_note is side-effecting);
the clarification branch by injecting the ClarifyGateway (which emits ``ask_human``).
"""

from __future__ import annotations

import pytest

from riptide_watergraph import service

from .test_clarify import ClarifyGateway


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CHECKPOINT_PATH", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("RIPTIDE_WATERGRAPH_DISABLE_TRACING", "1")


def test_run_task_single_and_llm_composer(env):
    assert service.run_task("compute 21 * 2", offline=True, single=True,
                            memory_on=False).final_answer is not None
    assert service.run_task("compute 21 * 2", offline=True, llm_composer=True,
                            memory_on=False).final_answer is not None


def test_run_task_approval_loop(env):
    # write_note is side-effecting -> approval interrupt -> auto_approve loop (default True).
    res = service.run_task("save a note about water", offline=True, memory_on=False)
    assert res.final_answer is not None


def test_run_task_clarification_loop(env, monkeypatch):
    monkeypatch.setattr(service, "DemoGateway", lambda *a, **k: ClarifyGateway())
    res = service.run_task("ambiguous task", offline=True, single=True, memory_on=False)
    assert res.clarifications  # the auto-supplied clarification answer was recorded


def test_stream_task_approval_loop(env):
    events = list(service.stream_task("save a note about water", offline=True, memory_on=False))
    assert any(kind == "result" for kind, _ in events)


def test_stream_task_clarification_loop(env, monkeypatch):
    monkeypatch.setattr(service, "DemoGateway", lambda *a, **k: ClarifyGateway())
    events = list(service.stream_task("ambiguous task", offline=True, single=True, memory_on=False))
    assert any(kind == "result" for kind, _ in events)
