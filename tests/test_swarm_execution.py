"""Swarm mode runs independent subtasks in one parallel pass; single mode unchanged."""

from __future__ import annotations

import json

from langgraph.checkpoint.sqlite import SqliteSaver

from riptide_watergraph import HeuristicSwarmComposer, build_graph
from riptide_watergraph.interfaces.gateway import CompletionResult
from riptide_watergraph.tools import default_registry

from .conftest import MockGateway


def _responder(plan: list[str]):
    def responder(system: str, user: str) -> CompletionResult:
        if "planning orchestrator" in system:
            return CompletionResult(content=json.dumps(plan))
        if "You are a worker" in system:  # matches single and swarm workers
            return CompletionResult(content=f"done: {user}")
        return CompletionResult(content="final answer")

    return responder


def test_swarm_runs_all_subtasks():
    task = "search cats and count words and uppercase the title"
    plan = ["search cats", "count words", "uppercase the title"]
    gateway = MockGateway(_responder(plan))
    composer = HeuristicSwarmComposer(model="mock")

    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = build_graph(
            gateway=gateway,
            registry=default_registry(),
            composer=composer,
            model="mock",
            checkpointer=cp,
        )
        result = graph.invoke(
            {"task": task}, {"configurable": {"thread_id": "swarm"}}
        )

    assert result["swarm_decision"]["mode"] == "swarm"
    assert len(result["results"]) == 3
    subtasks = {r["subtask"] for r in result["results"]}
    assert subtasks == set(plan)
    assert result.get("final_answer") == "final answer"


def test_simple_task_uses_single_path():
    gateway = MockGateway(_responder(["compute 2 + 2"]))
    composer = HeuristicSwarmComposer(model="mock")

    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = build_graph(
            gateway=gateway,
            registry=default_registry(),
            composer=composer,
            model="mock",
            checkpointer=cp,
        )
        result = graph.invoke(
            {"task": "compute 2 + 2"}, {"configurable": {"thread_id": "single"}}
        )

    assert result["swarm_decision"]["mode"] == "single"
    assert len(result["results"]) == 1
