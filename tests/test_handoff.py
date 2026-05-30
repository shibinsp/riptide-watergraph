"""E4: agent-to-agent handoff (sequential worker)."""

from __future__ import annotations

import json

from langgraph.checkpoint.sqlite import SqliteSaver

from riptide_watergraph import SingleAgentComposer, build_graph
from riptide_watergraph.interfaces.gateway import CompletionResult
from riptide_watergraph.tools import default_registry

from .conftest import MockGateway, tool_call


def test_worker_hands_off_then_specialist_answers():
    """The generalist hands off to the analyst, who then answers."""

    def responder(system: str, user: str) -> CompletionResult:
        if "planning orchestrator" in system:
            return CompletionResult(content=json.dumps(["do the thing"]))
        if "You are a worker" in system:
            # Specialist (analyst) answers; everyone else hands off to the analyst.
            if "analyst" in system:
                return CompletionResult(content="analyst result")
            return CompletionResult(
                tool_calls=[tool_call("handoff", {"role": "analyst", "reason": "math"})]
            )
        return CompletionResult(content="final")

    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = build_graph(
            gateway=MockGateway(responder),
            registry=default_registry(),
            composer=SingleAgentComposer(model="mock"),
            model="mock",
            checkpointer=cp,
        )
        result = graph.invoke({"task": "x"}, {"configurable": {"thread_id": "h1"}})

    assert result["roles"][0] == "analyst"  # role was re-assigned via handoff
    assert any("analyst result" in r["output"] for r in result["results"])


def test_handoff_cap_stops_a_second_handoff():
    """If the agent keeps handing off, the cap forces it to be handled."""

    def always_handoff(system: str, user: str) -> CompletionResult:
        if "planning orchestrator" in system:
            return CompletionResult(content=json.dumps(["do the thing"]))
        if "You are a worker" in system:
            return CompletionResult(
                tool_calls=[tool_call("handoff", {"role": "scribe"})]
            )
        return CompletionResult(content="final")

    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = build_graph(
            gateway=MockGateway(always_handoff),
            registry=default_registry(),
            composer=SingleAgentComposer(model="mock"),
            model="mock",
            checkpointer=cp,
            max_rounds=2,
        )
        result = graph.invoke({"task": "x"}, {"configurable": {"thread_id": "h2"}})

    # Exactly one handoff happened; the second was capped and the subtask completed.
    assert result["handoffs"] == {"0": 1}
    assert any("handoff limit reached" in r["output"] for r in result["results"])
