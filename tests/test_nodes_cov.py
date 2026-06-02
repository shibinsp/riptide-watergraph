"""graph/nodes.py coverage: pure parse-helpers + worker/_resolve_completion branches +
the non-dict resume normalization in human_approval / human_clarify.

Worker/_resolve_completion call asyncio.run internally, so these are SYNC tests.
"""

from __future__ import annotations

import json

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from riptide_watergraph import SingleAgentComposer, build_graph
from riptide_watergraph.graph.nodes import (
    GraphContext,
    _coerce_plan,
    _empty_metrics,
    _maybe_clarify,
    _maybe_handoff,
    _parse_json_object,
    _parse_subtasks,
    _parse_verdict,
    _resolve_completion,
    make_guard_input,
    make_supervisor,
    make_worker,
)
from riptide_watergraph.guardrails import default_guardrails
from riptide_watergraph.interfaces.gateway import CompletionResult
from riptide_watergraph.interfaces.tools import ToolSpec
from riptide_watergraph.tools import default_registry
from riptide_watergraph.tools.registry import StaticToolRegistry

from .conftest import MockGateway, tool_call
from .test_clarify import ClarifyGateway


def _ctx(responder=None, **kw):
    gw = MockGateway(responder or (lambda s, u: CompletionResult(content="x")))
    return GraphContext(gateway=gw, registry=default_registry(),
                        composer=SingleAgentComposer(model="m"), model="m", **kw)


# ---------- pure parse-helpers ----------

def test_parse_json_object():
    assert _parse_json_object(None) is None
    assert _parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert _parse_json_object("not json") is None
    assert _parse_json_object("[1, 2]") is None  # not a dict


def test_parse_verdict():
    r = {"subtask": "s", "output": "good output"}
    assert _parse_verdict('```json\n{"verdict": "fail", "reason": "x"}\n```', r)["verdict"] == "fail"
    assert _parse_verdict(None, {"subtask": "s", "output": "invalid"})["verdict"] == "fail"  # heuristic
    assert _parse_verdict("not json", r)["verdict"] == "pass"  # except -> heuristic (good output)


def test_parse_subtasks():
    assert _parse_subtasks(None) == []
    assert _parse_subtasks('```\n["a", "b"]\n```') == ["a", "b"]
    assert _parse_subtasks("not json") == []
    assert _parse_subtasks('{"x": 1}') == []  # parsed but not a list


def test_coerce_plan():
    assert _coerce_plan(None, "t") == ["t"]
    assert _coerce_plan('```\n["a"]\n```', "t") == ["a"]
    assert _coerce_plan("not json", "t") == ["t"]


# ---------- handoff / clarify bad-JSON arg branches ----------

def test_maybe_handoff_bad_json_args():
    state = {"plan": ["t"], "roles": ["generalist"], "handoffs": {}}
    result = CompletionResult(tool_calls=[{"function": {"name": "handoff", "arguments": "not json"}}])
    update = _maybe_handoff(state, 0, result, max_handoffs=1)
    assert update["roles"][0] == "generalist"  # bad JSON -> args {} -> default role


def test_maybe_clarify_bad_json_args():
    state = {"clarifications": {}}
    result = CompletionResult(tool_calls=[{"function": {"name": "ask_human", "arguments": "not json"}}])
    update = _maybe_clarify(state, 0, "sub", result)
    assert update["pending_action"]["type"] == "clarification"  # bad JSON -> default question


# ---------- _resolve_completion (swarm single-step) branches ----------

def test_resolve_completion_branches():
    ctx = _ctx()
    metrics = _empty_metrics()
    invalid = CompletionResult(tool_calls=[tool_call("nonexistent_tool", {})])
    out, _ = _resolve_completion(ctx, "sub", invalid, metrics)
    assert "invalid tool call" in out
    assert metrics["failures"]["unknown_tool"] == 1  # reason-in-failures branch

    side = CompletionResult(tool_calls=[tool_call("write_note", {"path": "p", "text": "t"})])
    out2, _ = _resolve_completion(ctx, "sub", side, _empty_metrics())
    assert "needs approval" in out2

    ro = CompletionResult(tool_calls=[tool_call("calculator", {"expression": "1 + 1"})])
    out3, _ = _resolve_completion(ctx, "sub", ro, _empty_metrics())
    assert "2" in out3


# ---------- worker branches (cursor past plan; invalid mid-step) ----------

def test_worker_cursor_past_plan():
    worker = make_worker(_ctx())
    assert worker({"plan": [], "cursor": 0}) == {}  # nothing to do


def test_worker_invalid_tool_call_mid_step():
    # max_steps=2 + a persistently-invalid tool call -> observe+continue on step 0.
    ctx = _ctx(lambda s, u: CompletionResult(tool_calls=[tool_call("nonexistent_tool", {})]),
               max_steps=2)
    worker = make_worker(ctx)
    update = worker({"plan": ["do x"], "cursor": 0, "roles": ["generalist"], "task": "t"})
    assert update["results"][0]["output"].startswith("invalid tool call")


# ---------- non-dict resume normalization (human_approval / human_clarify) ----------

def test_human_approval_non_dict_resume(tmp_path):
    note = tmp_path / "n.txt"
    reg = StaticToolRegistry()
    reg.register(ToolSpec(
        name="write_note", description="w",
        json_schema={"type": "object", "properties": {"path": {"type": "string"},
                                                       "text": {"type": "string"}},
                     "required": ["path", "text"], "additionalProperties": False},
        side_effecting=True, handler=lambda path, text: "ok"))

    def responder(system, user):
        if "planning orchestrator" in system:
            return CompletionResult(content=json.dumps(["save a note"]))
        if "You are a worker" in system:
            return CompletionResult(tool_calls=[tool_call("write_note",
                                                          {"path": str(note), "text": "x"})])
        return CompletionResult(content="done")

    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = build_graph(gateway=MockGateway(responder), registry=reg,
                            composer=SingleAgentComposer(model="m"), model="m", checkpointer=cp)
        config = {"configurable": {"thread_id": "approve-bool"}}
        assert "__interrupt__" in graph.invoke({"task": "t"}, config)
        result = graph.invoke(Command(resume=True), config)  # bool, not a dict
        assert "__interrupt__" not in result


def test_supervisor_no_corrective_subtasks():
    # A failed verdict triggers the supervisor's gateway call, which returns no subtasks.
    ctx = _ctx(lambda s, u: CompletionResult(content="[]"))
    supervisor = make_supervisor(ctx)
    state = {
        "verdicts": [{"subtask": "s", "verdict": "fail", "reason": "r"}],
        "round": 0, "plan": ["s"], "roles": ["generalist"], "dependencies": [[]],
        "results": [{"subtask": "s", "output": "bad"}],
    }
    update = supervisor(state)
    assert "plan" not in update  # nothing to add -> straight to finalize


def test_guard_input_transforms_without_blocking():
    ctx = _ctx(guardrails=default_guardrails())
    guard_input = make_guard_input(ctx)
    update = guard_input({"task": "please contact me at john.doe@example.com"})
    assert update.get("task") and not update.get("blocked")  # PII redacted, not blocked


def test_human_clarify_non_dict_resume():
    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = build_graph(gateway=ClarifyGateway(), registry=default_registry(),
                            composer=SingleAgentComposer(model="m"), model="m", checkpointer=cp)
        config = {"configurable": {"thread_id": "clarify-str"}}
        assert "__interrupt__" in graph.invoke({"task": "ambiguous"}, config)
        result = graph.invoke(Command(resume="just a string"), config)  # str, not a dict
        assert result["clarifications"]["0"] == "just a string"
