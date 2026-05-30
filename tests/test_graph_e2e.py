"""End-to-end graph test: plan -> worker -> approval interrupt -> resume -> finalize.

Uses a mocked gateway (no live API) and an in-memory SQLite checkpointer so the
interrupt/resume cycle is exercised exactly as in production.
"""

from __future__ import annotations

import json

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from riptide_watergraph import SingleAgentComposer, build_graph
from riptide_watergraph.interfaces.gateway import CompletionResult
from riptide_watergraph.interfaces.tools import ToolSpec
from riptide_watergraph.tools.registry import StaticToolRegistry

from .conftest import MockGateway, tool_call


def _build(responder, registry):
    composer = SingleAgentComposer(model="mock")
    gateway = MockGateway(responder)
    return gateway, composer, registry


def test_interrupt_resume_and_single_execution(tmp_path):
    note_path = tmp_path / "note.txt"
    write_calls = {"n": 0}

    def counting_write_note(path: str, text: str) -> str:
        write_calls["n"] += 1
        from pathlib import Path

        Path(path).write_text(text, encoding="utf-8")
        return f"wrote to {path}"

    registry = StaticToolRegistry()
    registry.register(
        ToolSpec(
            name="write_note",
            description="write a note",
            json_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}, "text": {"type": "string"}},
                "required": ["path", "text"],
                "additionalProperties": False,
            },
            side_effecting=True,
            handler=counting_write_note,
        )
    )

    def responder(system: str, user: str) -> CompletionResult:
        if "planning orchestrator" in system:
            return CompletionResult(content=json.dumps(["save a note about water"]))
        if "You are a worker" in system:
            return CompletionResult(
                tool_calls=[
                    tool_call("write_note", {"path": str(note_path), "text": "water"})
                ]
            )
        # finalize
        return CompletionResult(content="done: note saved")

    gateway, composer, registry = _build(responder, registry)
    config = {"configurable": {"thread_id": "t-e2e"}}

    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = build_graph(
            gateway=gateway,
            registry=registry,
            composer=composer,
            model="mock",
            checkpointer=cp,
        )

        # First invoke: should pause at the approval interrupt.
        result = graph.invoke({"task": "note about water"}, config)
        assert "__interrupt__" in result
        payload = result["__interrupt__"][0].value
        assert payload["tool"] == "write_note"
        assert write_calls["n"] == 0  # nothing executed before approval

        # Resume with approval -> executes the tool exactly once, then finalizes.
        result = graph.invoke(Command(resume={"approved": True}), config)
        assert "__interrupt__" not in result
        assert result["final_answer"] == "done: note saved"

    assert note_path.read_text(encoding="utf-8") == "water"
    assert write_calls["n"] == 1  # idempotency: executed exactly once across resume


def test_rejection_skips_side_effect(tmp_path):
    note_path = tmp_path / "note.txt"

    def responder(system: str, user: str) -> CompletionResult:
        if "planning orchestrator" in system:
            return CompletionResult(content=json.dumps(["save a note"]))
        if "You are a worker" in system:
            return CompletionResult(
                tool_calls=[
                    tool_call("write_note", {"path": str(note_path), "text": "x"})
                ]
            )
        return CompletionResult(content="finalized")

    from riptide_watergraph.tools import default_registry

    gateway = MockGateway(responder)
    composer = SingleAgentComposer(model="mock")
    config = {"configurable": {"thread_id": "t-reject"}}

    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = build_graph(
            gateway=gateway,
            registry=default_registry(),
            composer=composer,
            model="mock",
            checkpointer=cp,
        )
        result = graph.invoke({"task": "note"}, config)
        assert "__interrupt__" in result
        result = graph.invoke(Command(resume={"approved": False}), config)

    assert not note_path.exists()  # rejected -> no file written
    assert "final_answer" in result


def test_readonly_tool_runs_without_interrupt():
    def responder(system: str, user: str) -> CompletionResult:
        if "planning orchestrator" in system:
            return CompletionResult(content=json.dumps(["compute 21 * 2"]))
        if "You are a worker" in system:
            return CompletionResult(
                tool_calls=[tool_call("calculator", {"expression": "21 * 2"})]
            )
        return CompletionResult(content="the answer is 42")

    from riptide_watergraph.tools import default_registry

    gateway = MockGateway(responder)
    composer = SingleAgentComposer(model="mock")
    config = {"configurable": {"thread_id": "t-ro"}}

    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = build_graph(
            gateway=gateway,
            registry=default_registry(),
            composer=composer,
            model="mock",
            checkpointer=cp,
        )
        result = graph.invoke({"task": "math"}, config)

    assert "__interrupt__" not in result  # read-only tool: no approval needed
    assert result["final_answer"] == "the answer is 42"
    assert any("42" in r["output"] for r in result["results"])
