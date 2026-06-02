"""R3: structured (typed) final outputs."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from langgraph.checkpoint.sqlite import SqliteSaver

from riptide_watergraph import SingleAgentComposer, build_graph
from riptide_watergraph.interfaces.gateway import CompletionResult, Message, ModelGateway
from riptide_watergraph.tools import default_registry

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"answer": {"type": "string"}, "score": {"type": "integer"}},
    "required": ["answer", "score"],
}


class SchemaGateway(ModelGateway):
    """Worker answers directly; finalize emits JSON when asked for a schema."""

    def __init__(self, structured_reply: str) -> None:
        self.structured_reply = structured_reply

    async def complete(self, *, model: str, messages: list[Message],
                       tools: list[dict[str, Any]] | None = None, **kwargs: Any
                       ) -> CompletionResult:
        system = next((m.content or "" for m in messages if m.role == "system"), "")
        if "planning orchestrator" in system:
            return CompletionResult(content=json.dumps(["do the thing"]))
        if "You are a worker" in system:
            return CompletionResult(content="the thing is done")
        if "JSON Schema" in system:
            return CompletionResult(content=self.structured_reply)
        return CompletionResult(content="final text answer")

    async def stream(self, *, model: str, messages: list[Message], **kwargs: Any
                    ) -> AsyncIterator[str]:
        yield "x"


def _run(gateway: ModelGateway, final_schema: dict[str, Any] | None) -> dict:
    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = build_graph(
            gateway=gateway,
            registry=default_registry(),
            composer=SingleAgentComposer(model="mock"),
            model="mock",
            checkpointer=cp,
            final_schema=final_schema,
        )
        return graph.invoke({"task": "q"}, {"configurable": {"thread_id": "s"}})


def test_structured_output_validates_against_schema():
    gw = SchemaGateway(json.dumps({"answer": "ok", "score": 5}))
    result = _run(gw, SCHEMA)
    assert result["structured_output"] == {"answer": "ok", "score": 5}
    assert result["final_answer"]  # plain-text answer still produced as a fallback


def test_structured_output_retries_then_gives_up_on_invalid():
    # Reply is valid JSON but violates the schema (missing required "score") -> dropped.
    gw = SchemaGateway(json.dumps({"answer": "ok"}))
    result = _run(gw, SCHEMA)
    assert result.get("structured_output") in (None, {})  # never validated
    assert result["final_answer"]  # text answer unaffected


def test_no_schema_means_no_structured_output():
    gw = SchemaGateway(json.dumps({"answer": "ok", "score": 5}))
    result = _run(gw, None)
    assert "structured_output" not in result or not result.get("structured_output")
