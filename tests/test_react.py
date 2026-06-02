"""R1: iterative tool-use (ReAct) loop."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from langgraph.checkpoint.sqlite import SqliteSaver

from riptide_watergraph import SingleAgentComposer, build_graph
from riptide_watergraph.interfaces.gateway import CompletionResult, Message, ModelGateway
from riptide_watergraph.tools import default_registry

from .conftest import tool_call


class ReActGateway(ModelGateway):
    """Calls the calculator first; once it sees the tool observation, answers."""

    async def complete(self, *, model: str, messages: list[Message],
                       tools: list[dict[str, Any]] | None = None, **kwargs: Any
                       ) -> CompletionResult:
        system = next((m.content or "" for m in messages if m.role == "system"), "")
        if "planning orchestrator" in system:
            return CompletionResult(content=json.dumps(["compute the total"]))
        if "You are a worker" in system:
            observation = next((m.content for m in messages if m.role == "tool"), None)
            if observation is not None:
                return CompletionResult(content=f"final: {observation}")
            return CompletionResult(tool_calls=[tool_call("calculator", {"expression": "2 + 2"})])
        return CompletionResult(content="done")

    async def stream(self, *, model: str, messages: list[Message], **kwargs: Any
                    ) -> AsyncIterator[str]:
        yield "done"


def _run_with(max_steps: int) -> dict:
    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = build_graph(
            gateway=ReActGateway(),
            registry=default_registry(),
            composer=SingleAgentComposer(model="mock"),
            model="mock",
            checkpointer=cp,
            max_steps=max_steps,
        )
        return graph.invoke({"task": "compute"}, {"configurable": {"thread_id": f"r{max_steps}"}})


def test_react_loop_feeds_tool_result_back_and_synthesizes():
    result = _run_with(max_steps=4)
    out = result["results"][0]["output"]
    assert out.startswith("final:")  # the model synthesized after observing the tool
    assert "4.0" in out  # ...and the observation (calculator result) flowed back


def test_single_step_default_records_raw_tool_output():
    # max_steps=1 is the legacy single-shot path: records the tool output directly.
    result = _run_with(max_steps=1)
    assert result["results"][0]["output"] == "4.0"
