"""E2: critic / verification pass."""

from __future__ import annotations

import json

from langgraph.checkpoint.sqlite import SqliteSaver

from riptide_watergraph import HeuristicSwarmComposer, SingleAgentComposer, build_graph
from riptide_watergraph.interfaces.gateway import CompletionResult
from riptide_watergraph.tools import default_registry

from .conftest import MockGateway, tool_call


def _responder(system: str, user: str) -> CompletionResult:
    if "planning orchestrator" in system:
        return CompletionResult(content=json.dumps(["alpha", "beta"]))
    if "You are a worker" in system:
        if "alpha" in user:
            return CompletionResult(content="a solid answer")
        # beta: emit a call to an unknown tool -> invalid -> failing output
        return CompletionResult(tool_calls=[tool_call("nonexistent_tool", {})])
    if "You are a critic" in system:
        # fail results that look invalid; pass otherwise
        verdict = "fail" if "invalid" in user.lower() else "pass"
        return CompletionResult(content=json.dumps({"verdict": verdict, "reason": "t"}))
    return CompletionResult(content="final answer")


def test_critic_marks_pass_and_fail():
    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = build_graph(
            gateway=MockGateway(_responder),
            registry=default_registry(),
            composer=HeuristicSwarmComposer(model="mock"),
            model="mock",
            checkpointer=cp,
            enable_critic=True,
        )
        result = graph.invoke({"task": "two things"}, {"configurable": {"thread_id": "c1"}})

    verdicts = result["verdicts"]
    by_subtask = {v["subtask"]: v["verdict"] for v in verdicts}
    assert by_subtask["alpha"] == "pass"
    assert by_subtask["beta"] == "fail"
    # The failed subtask is excluded and noted in the final answer.
    assert "failed verification" in result["final_answer"]


def test_no_critic_leaves_graph_unchanged():
    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = build_graph(
            gateway=MockGateway(_responder),
            registry=default_registry(),
            composer=SingleAgentComposer(model="mock"),
            model="mock",
            checkpointer=cp,
        )
        result = graph.invoke({"task": "alpha"}, {"configurable": {"thread_id": "c2"}})

    assert "verdicts" not in result or not result.get("verdicts")
