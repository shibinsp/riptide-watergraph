"""E3: supervisor re-planning loop."""

from __future__ import annotations

import json

from langgraph.checkpoint.sqlite import SqliteSaver

from riptide_watergraph import HeuristicSwarmComposer, build_graph
from riptide_watergraph.interfaces.gateway import CompletionResult
from riptide_watergraph.tools import default_registry

from .conftest import MockGateway, tool_call


def _responder(system: str, user: str) -> CompletionResult:
    if "planning orchestrator" in system:
        return CompletionResult(content=json.dumps(["alpha", "beta"]))
    if "You are a supervisor" in system:
        return CompletionResult(content=json.dumps(["fix beta"]))
    if "You are a critic" in system:
        verdict = "fail" if "invalid" in user.lower() else "pass"
        return CompletionResult(content=json.dumps({"verdict": verdict, "reason": "t"}))
    if "You are a worker" in system:
        if "beta" in user and "fix" not in user:  # original beta fails
            return CompletionResult(tool_calls=[tool_call("nonexistent_tool", {})])
        return CompletionResult(content=f"ok: {user}")
    return CompletionResult(content="final answer")


def test_supervisor_adds_one_corrective_round_then_finalizes():
    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = build_graph(
            gateway=MockGateway(_responder),
            registry=default_registry(),
            composer=HeuristicSwarmComposer(model="mock"),
            model="mock",
            checkpointer=cp,
            enable_supervisor=True,  # implies critic
            max_rounds=2,
        )
        result = graph.invoke({"task": "two things"}, {"configurable": {"thread_id": "s1"}})

    assert result["round"] == 2  # one corrective round, then the cap stops it
    assert "fix beta" in result["plan"]  # corrective subtask appended
    verdicts = {v["subtask"]: v["verdict"] for v in result["verdicts"]}
    assert verdicts["beta"] == "fail"
    assert verdicts["fix beta"] == "pass"  # the correction was verified
    assert "failed verification" in result["final_answer"]


def test_supervisor_respects_round_cap():
    # Corrective subtasks that also fail must still terminate at max_rounds.
    def always_fail(system: str, user: str) -> CompletionResult:
        if "planning orchestrator" in system:
            return CompletionResult(content=json.dumps(["beta"]))
        if "You are a supervisor" in system:
            return CompletionResult(content=json.dumps(["retry beta"]))
        if "You are a critic" in system:
            return CompletionResult(content=json.dumps({"verdict": "fail", "reason": "t"}))
        if "You are a worker" in system:
            return CompletionResult(tool_calls=[tool_call("nonexistent_tool", {})])
        return CompletionResult(content="final")

    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = build_graph(
            gateway=MockGateway(always_fail),
            registry=default_registry(),
            composer=HeuristicSwarmComposer(model="mock"),
            model="mock",
            checkpointer=cp,
            enable_supervisor=True,
            max_rounds=3,
        )
        result = graph.invoke({"task": "x"}, {"configurable": {"thread_id": "s2"}})

    assert result["round"] == 3  # stopped exactly at the cap, no infinite loop
