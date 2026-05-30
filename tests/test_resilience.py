"""Phase A: resilient gateway, tool-error isolation, real cost from usage."""

from __future__ import annotations

import json

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver

from riptide_watergraph import ResilientGateway, SingleAgentComposer, build_graph
from riptide_watergraph.interfaces.gateway import CompletionResult, ModelGateway
from riptide_watergraph.interfaces.tools import ToolSpec
from riptide_watergraph.observability.cost import cost_from_usage
from riptide_watergraph.tools.registry import StaticToolRegistry

from .conftest import MockGateway, tool_call


class FlakyGateway(ModelGateway):
    """Fails the first ``fail_times`` calls, then succeeds."""

    def __init__(self, fail_times: int) -> None:
        self.fail_times = fail_times
        self.calls = 0

    async def complete(self, **kwargs):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("transient boom")
        return CompletionResult(content="ok")

    async def stream(self, **kwargs):
        yield "ok"


async def test_resilient_retries_then_succeeds():
    inner = FlakyGateway(fail_times=2)
    g = ResilientGateway(inner, max_attempts=3, base_backoff_s=0.0)
    result = await g.complete(model="m", messages=[])
    assert result.content == "ok"
    assert inner.calls == 3


async def test_resilient_gives_up_after_max_attempts():
    inner = FlakyGateway(fail_times=5)
    g = ResilientGateway(inner, max_attempts=2, base_backoff_s=0.0)
    with pytest.raises(RuntimeError):
        await g.complete(model="m", messages=[])
    assert inner.calls == 2


def test_cost_from_usage_uses_price_table():
    usage = {"prompt_tokens": 1000, "completion_tokens": 1000, "total_tokens": 2000}
    cost = cost_from_usage("gpt-4o-mini", usage)
    assert cost == pytest.approx(0.00015 + 0.0006)
    assert cost_from_usage("gpt-4o-mini", None) == 0.0


def test_tool_failure_is_isolated_not_crashing():
    """A tool that raises yields an error result, not a crashed run."""

    def boom(**kwargs):
        raise ValueError("kaboom")

    registry = StaticToolRegistry()
    registry.register(
        ToolSpec(
            name="boom",
            description="always fails",
            json_schema={"type": "object", "properties": {}, "additionalProperties": True},
            side_effecting=False,
            handler=boom,
        )
    )

    def responder(system: str, user: str) -> CompletionResult:
        if "planning orchestrator" in system:
            return CompletionResult(content=json.dumps(["do the thing"]))
        if "You are a worker" in system:
            return CompletionResult(tool_calls=[tool_call("boom", {})])
        return CompletionResult(content="final")

    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = build_graph(
            gateway=MockGateway(responder),
            registry=registry,
            composer=SingleAgentComposer(model="mock"),
            model="mock",
            checkpointer=cp,
        )
        result = graph.invoke({"task": "x"}, {"configurable": {"thread_id": "boom"}})

    assert result.get("final_answer") == "final"  # run completed despite tool failure
    assert any("failed" in r["output"] for r in result["results"])
