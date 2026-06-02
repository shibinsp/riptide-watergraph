"""R2: self-consistency / voting."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from langgraph.checkpoint.sqlite import SqliteSaver

from riptide_watergraph import SingleAgentComposer, build_graph
from riptide_watergraph.interfaces.gateway import CompletionResult, Message, ModelGateway
from riptide_watergraph.tools import default_registry

from .conftest import tool_call


class SequenceGateway(ModelGateway):
    """Returns a scripted sequence of worker answers; fixed plan + finalize."""

    def __init__(self, worker_answers: list[CompletionResult]) -> None:
        self.worker_answers = worker_answers
        self.i = 0

    async def complete(self, *, model: str, messages: list[Message],
                       tools: list[dict[str, Any]] | None = None, **kwargs: Any
                       ) -> CompletionResult:
        system = next((m.content or "" for m in messages if m.role == "system"), "")
        if "planning orchestrator" in system:
            return CompletionResult(content=json.dumps(["answer the question"]))
        if "You are a worker" in system:
            ans = self.worker_answers[min(self.i, len(self.worker_answers) - 1)]
            self.i += 1
            return ans
        return CompletionResult(content="final")

    async def stream(self, *, model: str, messages: list[Message], **kwargs: Any
                    ) -> AsyncIterator[str]:
        yield "x"


def _run(gateway, vote_k):
    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = build_graph(
            gateway=gateway,
            registry=default_registry(),
            composer=SingleAgentComposer(model="mock"),
            model="mock",
            checkpointer=cp,
            vote_k=vote_k,
        )
        return graph.invoke({"task": "q"}, {"configurable": {"thread_id": "v"}})


def test_majority_vote_wins():
    gw = SequenceGateway([
        CompletionResult(content="42"),
        CompletionResult(content="42"),
        CompletionResult(content="7"),
    ])
    result = _run(gw, vote_k=3)
    assert result["results"][0]["output"] == "42"  # 2/3 majority
    assert gw.i == 3  # sampled three times


def test_voting_abandoned_when_a_tool_is_requested():
    # Every worker call wants a tool -> voting is skipped, tool executes exactly once
    # (samples don't run tools; only the single normal ReAct pass does).
    gw = SequenceGateway(
        [CompletionResult(tool_calls=[tool_call("calculator", {"expression": "2 + 2"})])]
    )
    result = _run(gw, vote_k=3)
    assert result["results"][0]["output"] == "4.0"
    assert result["metrics"]["tool_calls_total"] == 1
