"""E1: role-specialized agents — assignment, tool scoping, and graph wiring."""

from __future__ import annotations

import asyncio
import json

from langgraph.checkpoint.sqlite import SqliteSaver

from riptide_watergraph import HeuristicSwarmComposer, build_graph
from riptide_watergraph.interfaces.gateway import CompletionResult
from riptide_watergraph.swarm.roles import get_role, role_for
from riptide_watergraph.tools import default_registry

from .conftest import MockGateway


def test_role_for_keyword_mapping():
    assert role_for("search the web for cats") == "researcher"
    assert role_for("compute 21 * 2") == "analyst"
    assert role_for("write a short note") == "scribe"
    assert role_for("ponder the meaning of life") == "generalist"


def test_get_role_tools_scope():
    assert get_role("analyst").tools == ["calculator"]
    assert get_role("generalist").tools is None  # all tools
    assert "You are a worker" in get_role("researcher").system_prompt  # preserves contract


def test_retrieve_respects_allowed():
    reg = default_registry()
    hits = asyncio.run(reg.retrieve("do anything", k=5, allowed={"calculator"}))
    assert {h.name for h in hits} == {"calculator"}


def test_graph_assigns_roles_per_subtask():
    plan = ["search cats", "compute 2 + 2", "write a summary"]

    def responder(system: str, user: str) -> CompletionResult:
        if "planning orchestrator" in system:
            return CompletionResult(content=json.dumps(plan))
        if "You are a worker" in system:
            return CompletionResult(content=f"done: {user}")
        return CompletionResult(content="final")

    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = build_graph(
            gateway=MockGateway(responder),
            registry=default_registry(),
            composer=HeuristicSwarmComposer(model="mock"),
            model="mock",
            checkpointer=cp,
        )
        result = graph.invoke({"task": "many things"}, {"configurable": {"thread_id": "roles"}})

    # Heuristic composer -> single-agent here (orchestrator still assigns roles per subtask).
    assert result["roles"] == ["researcher", "analyst", "scribe"]
