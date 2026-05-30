"""Phase C: LLM composer, dependency-wave execution + blackboard, model routing."""

from __future__ import annotations

import json

from langgraph.checkpoint.sqlite import SqliteSaver

from riptide_watergraph import (
    LLMSwarmComposer,
    SingleAgentComposer,
    build_graph,
)
from riptide_watergraph.interfaces.gateway import CompletionResult, ModelGateway
from riptide_watergraph.tools import default_registry

from .conftest import MockGateway


async def test_llm_composer_parses_plan_and_deps():
    def responder(system: str, user: str) -> CompletionResult:
        assert "planning composer" in system
        return CompletionResult(
            content=json.dumps(
                {
                    "mode": "swarm",
                    "subtasks": [
                        {"task": "research A", "depends_on": []},
                        {"task": "research B", "depends_on": []},
                        {"task": "summarize", "depends_on": [0, 1]},
                    ],
                }
            )
        )

    composer = LLMSwarmComposer(MockGateway(responder), model="mock")
    decision = await composer.decide("do research then summarize")
    assert decision.mode == "swarm"
    assert decision.plan == ["research A", "research B", "summarize"]
    assert decision.dependencies == [[], [], [0, 1]]


async def test_llm_composer_falls_back_to_single_on_bad_output():
    composer = LLMSwarmComposer(
        MockGateway(lambda s, u: CompletionResult(content="not json")), model="mock"
    )
    decision = await composer.decide("just one thing")
    assert decision.mode == "single"
    assert decision.plan == ["just one thing"]


def test_blackboard_flows_to_dependent_subtask():
    def responder(system: str, user: str) -> CompletionResult:
        if "planning composer" in system:
            return CompletionResult(
                content=json.dumps(
                    {
                        "mode": "swarm",
                        "subtasks": [
                            {"task": "A", "depends_on": []},
                            {"task": "B", "depends_on": [0]},
                        ],
                    }
                )
            )
        if "You are a worker" in system:
            if user == "A":
                return CompletionResult(content="result-A")
            # B: did it see A's output via the blackboard context?
            saw = "Context from prior steps" in system and "result-A" in system
            return CompletionResult(content="B-saw-A" if saw else "B-blind")
        return CompletionResult(content="final")

    gw = MockGateway(responder)
    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = build_graph(
            gateway=gw,
            registry=default_registry(),
            composer=LLMSwarmComposer(gw, model="mock"),
            model="mock",
            checkpointer=cp,
        )
        result = graph.invoke({"task": "A then B"}, {"configurable": {"thread_id": "bb"}})

    assert result["swarm_decision"]["mode"] == "swarm"
    by_subtask = {r["subtask"]: r["output"] for r in result["results"]}
    assert by_subtask["A"] == "result-A"
    assert by_subtask["B"] == "B-saw-A"  # the dependent worker saw upstream output


class _RecordingGateway(ModelGateway):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []  # (model, role)

    async def complete(self, *, model, messages, **kwargs):
        system = next((m.content or "" for m in messages if m.role == "system"), "")
        role = "worker" if "You are a worker" in system else "planner"
        self.calls.append((model, role))
        if "planning orchestrator" in system:
            return CompletionResult(content=json.dumps(["do the thing"]))
        return CompletionResult(content="ok")

    async def stream(self, *, model, messages, **kwargs):
        yield "ok"


def test_model_routing_planner_vs_worker():
    gw = _RecordingGateway()
    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = build_graph(
            gateway=gw,
            registry=default_registry(),
            composer=SingleAgentComposer(model="P"),
            model="base",
            checkpointer=cp,
            planner_model="P",
            worker_model="W",
        )
        graph.invoke({"task": "x"}, {"configurable": {"thread_id": "route"}})

    worker_models = {m for m, role in gw.calls if role == "worker"}
    planner_models = {m for m, role in gw.calls if role == "planner"}
    assert worker_models == {"W"}  # workers used the worker model
    assert planner_models == {"P"}  # orchestrator + finalize used the planner model
