"""R4: clarifying-question human-in-the-loop."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from riptide_watergraph import SingleAgentComposer, build_graph
from riptide_watergraph.interfaces.gateway import CompletionResult, Message, ModelGateway
from riptide_watergraph.tools import default_registry

from .conftest import tool_call


class ClarifyGateway(ModelGateway):
    """Worker asks a clarifying question, then answers using the human's reply.

    ``always_ask`` keeps emitting ``ask_human`` even after the answer arrives, to exercise
    the one-question-per-subtask cap.
    """

    def __init__(self, always_ask: bool = False) -> None:
        self.always_ask = always_ask
        self.ask_count = 0

    async def complete(self, *, model: str, messages: list[Message],
                       tools: list[dict[str, Any]] | None = None, **kwargs: Any
                       ) -> CompletionResult:
        system = next((m.content or "" for m in messages if m.role == "system"), "")
        user = next((m.content or "" for m in messages if m.role == "user"), "")
        if "planning orchestrator" in system:
            return CompletionResult(content=json.dumps(["do the ambiguous thing"]))
        if "You are a worker" in system:
            answered = "Human clarification:" in user
            if not answered or self.always_ask:
                self.ask_count += 1
                return CompletionResult(
                    tool_calls=[tool_call("ask_human", {"question": "Which target?"})]
                )
            return CompletionResult(content=f"final: {user.split('Human clarification:')[1]}")
        return CompletionResult(content="composed")

    async def stream(self, *, model: str, messages: list[Message], **kwargs: Any
                    ) -> AsyncIterator[str]:
        yield "x"


def _graph(gateway: ModelGateway, cp: Any):
    return build_graph(
        gateway=gateway,
        registry=default_registry(),
        composer=SingleAgentComposer(model="mock"),
        model="mock",
        checkpointer=cp,
    )


def test_clarify_interrupts_then_uses_the_answer():
    gw = ClarifyGateway()
    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = _graph(gw, cp)
        config = {"configurable": {"thread_id": "c1"}}

        result = graph.invoke({"task": "ambiguous"}, config)
        assert "__interrupt__" in result
        payload = result["__interrupt__"][0].value
        assert payload["type"] == "clarification"
        assert payload["question"] == "Which target?"

        result = graph.invoke(Command(resume={"answer": "use target X"}), config)
        assert "__interrupt__" not in result
        out = result["results"][0]["output"]
        assert out.startswith("final:")
        assert "use target X" in out  # the human's answer flowed into the subtask
        assert result["clarifications"]["0"] == "use target X"


def test_clarification_capped_at_one_per_subtask():
    # The model keeps asking, but the cap stops a second interrupt and the run terminates.
    gw = ClarifyGateway(always_ask=True)
    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = _graph(gw, cp)
        config = {"configurable": {"thread_id": "c2"}}

        result = graph.invoke({"task": "ambiguous"}, config)
        assert "__interrupt__" in result

        result = graph.invoke(Command(resume={"answer": "X"}), config)
        assert "__interrupt__" not in result  # no second clarification interrupt
        assert gw.ask_count == 2  # asked once before + once on re-run (then capped)
        assert result["clarifications"]["0"] == "X"


class _DirectGateway(ModelGateway):
    """Never emits ask_human — behaves exactly as before the clarify feature."""

    async def complete(self, *, model: str, messages: list[Message],
                       tools: list[dict[str, Any]] | None = None, **kwargs: Any
                       ) -> CompletionResult:
        system = next((m.content or "" for m in messages if m.role == "system"), "")
        if "planning orchestrator" in system:
            return CompletionResult(content=json.dumps(["clear task"]))
        if "You are a worker" in system:
            return CompletionResult(content="done directly")
        return CompletionResult(content="composed")

    async def stream(self, *, model: str, messages: list[Message], **kwargs: Any
                    ) -> AsyncIterator[str]:
        yield "x"


def test_no_clarification_when_worker_answers_directly():
    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = _graph(_DirectGateway(), cp)
        result = graph.invoke({"task": "clear"}, {"configurable": {"thread_id": "c3"}})
        assert "__interrupt__" not in result
        assert result["results"][0]["output"] == "done directly"
