"""Model sampling (temperature/top_p/max_tokens) threads to every gateway call."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from langgraph.checkpoint.sqlite import SqliteSaver

from riptide_watergraph import SingleAgentComposer, build_graph
from riptide_watergraph.interfaces.gateway import CompletionResult, Message, ModelGateway
from riptide_watergraph.tools import default_registry


class CapturingGateway(ModelGateway):
    """Records the sampling kwargs each completion is called with."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def complete(self, *, model: str, messages: list[Message],
                       tools: list[dict[str, Any]] | None = None,
                       temperature: float = 0.0, **kwargs: Any) -> CompletionResult:
        self.calls.append({"temperature": temperature, **kwargs})
        system = next((m.content or "" for m in messages if m.role == "system"), "")
        if "planning orchestrator" in system:
            return CompletionResult(content=json.dumps(["do it"]))
        if "You are a worker" in system:
            return CompletionResult(content="done")
        return CompletionResult(content="final")

    async def stream(self, *, model: str, messages: list[Message], **kwargs: Any
                    ) -> AsyncIterator[str]:
        yield "x"


def _run(sampling):
    gw = CapturingGateway()
    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = build_graph(
            gateway=gw, registry=default_registry(),
            composer=SingleAgentComposer(model="m"), model="m", checkpointer=cp,
            sampling=sampling,
        )
        graph.invoke({"task": "q"}, {"configurable": {"thread_id": "s"}})
    return gw


def test_sampling_reaches_every_call():
    gw = _run({"temperature": 0.7, "top_p": 0.9, "max_tokens": 256})
    assert gw.calls  # the graph made at least one completion
    assert all(c["temperature"] == 0.7 for c in gw.calls)
    assert all(c.get("top_p") == 0.9 and c.get("max_tokens") == 256 for c in gw.calls)


def test_default_sampling_is_deterministic():
    gw = _run(None)
    assert all(c["temperature"] == 0.0 for c in gw.calls)
    assert all("top_p" not in c and "max_tokens" not in c for c in gw.calls)
