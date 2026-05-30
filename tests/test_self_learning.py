"""Self-learning proof: the agent fails a task, reflects, stores a lesson, then
succeeds on a repeat — driven entirely by memory recall + reflection (no weight
updates, no human in the loop).

The gateway's correctness is *conditioned on the recalled lesson*: with no lesson it
emits a malformed tool call (failure); once the distilled lesson is injected it emits a
valid call (success). This proves the closed loop end-to-end and deterministically.
Genuine quality gains with a real model rest on the same wiring.
"""

from __future__ import annotations

import json

from langgraph.checkpoint.sqlite import SqliteSaver

from riptide_watergraph import (
    JsonFileMemory,
    LLMReflector,
    SingleAgentComposer,
    build_graph,
)
from riptide_watergraph.interfaces.gateway import CompletionResult
from riptide_watergraph.tools import default_registry

from .conftest import MockGateway, tool_call


def _learning_responder(system: str, user: str) -> CompletionResult:
    """Worker correctness depends on whether the lesson (mentions 'expression') was
    recalled and injected into its system prompt."""
    if "reflection module" in system:
        return CompletionResult(
            content=json.dumps(
                {
                    "lesson": "For arithmetic tasks, call calculator with an "
                    "'expression' field.",
                    "tags": ["calculator"],
                }
            )
        )
    if "planning orchestrator" in system:
        return CompletionResult(content=json.dumps(["compute 2 + 2"]))
    if "You are a worker" in system:
        if "expression" in system:  # lesson was recalled + injected
            return CompletionResult(
                tool_calls=[tool_call("calculator", {"expression": "2 + 2"})]
            )
        # No lesson yet -> malformed call (wrong key) -> schema violation -> failure.
        return CompletionResult(
            tool_calls=[tool_call("calculator", {"expr": "2 + 2"})]
        )
    return CompletionResult(content="done")


def test_success_rises_across_runs_via_memory(tmp_path):
    memory = JsonFileMemory(tmp_path / "mem.json")
    gateway = MockGateway(_learning_responder)
    reflector = LLMReflector(gateway, model="mock")
    composer = SingleAgentComposer(model="mock")

    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = build_graph(
            gateway=gateway,
            registry=default_registry(),
            composer=composer,
            model="mock",
            checkpointer=cp,
            memory=memory,
            reflector=reflector,
        )

        # --- Run 1: no lessons yet -> fails, then reflects + stores a lesson ---
        r1 = graph.invoke(
            {"task": "compute 2 + 2", "session_id": "run1"},
            {"configurable": {"thread_id": "run1"}},
        )
        assert r1.get("recalled_lessons") == []        # nothing to recall
        assert r1.get("success") is False              # malformed call -> failure
        assert len(memory) >= 1                         # a lesson was learned

        # --- Run 2: lesson recalled + injected -> succeeds ---
        r2 = graph.invoke(
            {"task": "compute 2 + 2", "session_id": "run2"},
            {"configurable": {"thread_id": "run2"}},
        )
        assert r2.get("recalled_lessons")              # lesson recalled
        assert any("expression" in ln for ln in r2["recalled_lessons"])
        assert r2.get("success") is True               # valid call -> success

    # Success rate rose 0/1 -> 1/1 with no fine-tuning: memory + reflection only.


def test_no_memory_flag_preserves_stage1_behavior(tmp_path):
    """With no memory/reflector, the graph is exactly the Stage-1 skeleton."""
    gateway = MockGateway(_learning_responder)
    composer = SingleAgentComposer(model="mock")
    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = build_graph(
            gateway=gateway,
            registry=default_registry(),
            composer=composer,
            model="mock",
            checkpointer=cp,
        )
        result = graph.invoke(
            {"task": "compute 2 + 2"}, {"configurable": {"thread_id": "s1"}}
        )
    assert "recalled_lessons" not in result or result.get("recalled_lessons") is None
    assert "success" not in result            # no reflect node ran
    assert result.get("final_answer") == "done"
