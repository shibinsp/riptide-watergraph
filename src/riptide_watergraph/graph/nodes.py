"""Graph nodes for the orchestrator-worker skeleton.

Nodes are **synchronous** (paired with the sync ``SqliteSaver``); async gateway calls
are wrapped via ``_run``. The flow:

    orchestrator -> worker -> [human_approval] -> worker ... -> finalize

IDEMPOTENCY (critical): on resume after an ``interrupt()``, LangGraph re-executes the
*entire* node that interrupted, from the top. Therefore ``human_approval`` performs NO
side effects before ``interrupt()``, and the actual side-effecting tool runs ONLY in
``worker`` after approval — so a resume can never double-execute it.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from langgraph.types import interrupt

from ..interfaces.gateway import Message, ModelGateway
from ..interfaces.swarm import SwarmComposer
from ..observability.tracing import span
from ..tools.registry import StaticToolRegistry, ToolValidationError
from .state import OrchestratorState, WorkerResult


@dataclass
class GraphContext:
    """Dependencies the nodes close over (injected by the builder)."""

    gateway: ModelGateway
    registry: StaticToolRegistry
    composer: SwarmComposer
    model: str


def _run(coro: Any) -> Any:
    """Run an async coroutine to completion from a sync node."""
    return asyncio.run(coro)


def _empty_metrics() -> dict[str, Any]:
    return {
        "tool_calls_total": 0,
        "tool_calls_valid": 0,
        "failures": {"unknown_tool": 0, "bad_json": 0, "schema_violation": 0},
    }


def _parse_tool_call(
    ctx: GraphContext, call: dict[str, Any]
) -> tuple[str | None, str, dict[str, Any], bool, str | None]:
    """Parse + validate one tool call.

    Returns (call_id, name, arguments, is_valid, failure_reason).
    """
    call_id = call.get("id")
    fn = call.get("function", {}) or {}
    name = fn.get("name", "")
    raw_args = fn.get("arguments", "{}")

    try:
        arguments = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
    except (json.JSONDecodeError, TypeError):
        return call_id, name, {}, False, "bad_json"

    try:
        ctx.registry.validate_call(name, arguments)
    except ToolValidationError as exc:
        reason = str(exc).split(":", 1)[0]
        if reason not in ("unknown_tool", "schema_violation"):
            reason = "schema_violation"
        return call_id, name, arguments, False, reason

    return call_id, name, arguments, True, None


# --------------------------------------------------------------------------- #
# Nodes
# --------------------------------------------------------------------------- #


def make_orchestrator(ctx: GraphContext):
    """Decompose the task into a plan (list of subtasks)."""

    def orchestrator(state: OrchestratorState) -> dict[str, Any]:
        task = state["task"]
        with span("orchestrator", task=task):
            # Consult the (stubbed) cost-aware composer for completeness.
            _run(ctx.composer.decide(task))

            sys = Message(
                role="system",
                content=(
                    "You are a planning orchestrator. Break the user's task into a "
                    "short ordered list of concrete subtasks. Reply ONLY with a JSON "
                    'array of strings, e.g. ["step one", "step two"].'
                ),
            )
            usr = Message(role="user", content=task)
            result = _run(ctx.gateway.complete(model=ctx.model, messages=[sys, usr]))

            plan = _coerce_plan(result.content, task)
            return {
                "plan": plan,
                "cursor": 0,
                "metrics": _empty_metrics(),
                "messages": [{"role": "system", "content": f"plan={plan}"}],
            }

    return orchestrator


def make_worker(ctx: GraphContext):
    """Process one subtask per invocation; resolve an approved action if pending."""

    def worker(state: OrchestratorState) -> dict[str, Any]:
        metrics = state.get("metrics") or _empty_metrics()

        # --- Case A: resolve a pending action after human approval ---
        pending = state.get("pending_action")
        approval = state.get("approval")
        if pending is not None and approval is not None:
            return _resolve_pending(ctx, state, pending, approval)

        plan = state.get("plan") or []
        cursor = state.get("cursor", 0)
        if cursor >= len(plan):
            return {}  # nothing to do; routing sends us to finalize

        subtask = plan[cursor]
        with span("worker", subtask=subtask, cursor=cursor):
            sys = Message(
                role="system",
                content=(
                    "You are a worker. Accomplish the subtask. Use a tool if helpful; "
                    "otherwise answer directly and concisely."
                ),
            )
            usr = Message(role="user", content=subtask)
            tools = ctx.registry.openai_schemas()
            result = _run(
                ctx.gateway.complete(
                    model=ctx.model, messages=[sys, usr], tools=tools
                )
            )

            if not result.tool_calls:
                # Direct answer — record and advance.
                out: WorkerResult = {
                    "subtask": subtask,
                    "output": result.content or "",
                    "tool_calls": [],
                }
                return {"results": [out], "cursor": cursor + 1, "metrics": metrics}

            # Take the first tool call (skeleton handles one per subtask).
            call = result.tool_calls[0]
            call_id, name, arguments, valid, reason = _parse_tool_call(ctx, call)

            metrics["tool_calls_total"] += 1
            if valid:
                metrics["tool_calls_valid"] += 1
            elif reason in metrics["failures"]:
                metrics["failures"][reason] += 1

            if not valid:
                out = {
                    "subtask": subtask,
                    "output": f"invalid tool call ({reason}) for {name!r}",
                    "tool_calls": [call],
                }
                return {"results": [out], "cursor": cursor + 1, "metrics": metrics}

            spec = ctx.registry.get(name)
            if spec.side_effecting:
                # Defer execution to AFTER approval (idempotency). Route to HITL.
                return {
                    "pending_action": {
                        "tool": name,
                        "arguments": arguments,
                        "subtask": subtask,
                        "cursor": cursor,
                        "call_id": call_id,
                    },
                    "metrics": metrics,
                }

            # Read-only tool: execute inline.
            tool_result = _run(ctx.registry.invoke(name, arguments))
            out = {
                "subtask": subtask,
                "output": str(tool_result),
                "tool_calls": [call],
            }
            return {"results": [out], "cursor": cursor + 1, "metrics": metrics}

    return worker


def make_human_approval(ctx: GraphContext):
    """Pause for human approval of a side-effecting action.

    NO side effects before ``interrupt()`` — see module docstring.
    """

    def human_approval(state: OrchestratorState) -> dict[str, Any]:
        pending = state.get("pending_action") or {}
        decision = interrupt(
            {
                "type": "tool_approval",
                "tool": pending.get("tool"),
                "arguments": pending.get("arguments"),
                "subtask": pending.get("subtask"),
            }
        )
        # Normalize the resume payload into an approval dict.
        if isinstance(decision, dict):
            approval = decision
        else:
            approval = {"approved": bool(decision)}
        return {"approval": approval}

    return human_approval


def make_finalize(ctx: GraphContext):
    """Compose the final answer from accumulated results."""

    def finalize(state: OrchestratorState) -> dict[str, Any]:
        results = state.get("results") or []
        with span("finalize", n_results=len(results)):
            transcript = "\n".join(
                f"- {r['subtask']}: {r['output']}" for r in results
            )
            sys = Message(
                role="system",
                content="Compose a concise final answer from the worker results.",
            )
            usr = Message(
                role="user",
                content=f"Task: {state['task']}\n\nResults:\n{transcript}",
            )
            result = _run(ctx.gateway.complete(model=ctx.model, messages=[sys, usr]))
            answer = result.content or transcript
            return {"final_answer": answer}

    return finalize


# --------------------------------------------------------------------------- #
# Routing
# --------------------------------------------------------------------------- #


def route_after_worker(state: OrchestratorState) -> str:
    """worker -> human_approval (needs approval) | worker (more) | finalize."""
    if state.get("pending_action") is not None and state.get("approval") is None:
        return "human_approval"
    plan = state.get("plan") or []
    if state.get("cursor", 0) < len(plan):
        return "worker"
    return "finalize"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _resolve_pending(
    ctx: GraphContext,
    state: OrchestratorState,
    pending: dict[str, Any],
    approval: dict[str, Any],
) -> dict[str, Any]:
    """Execute (or skip) the approved action; advance cursor; clear pending/approval."""
    cursor = pending.get("cursor", state.get("cursor", 0))
    subtask = pending.get("subtask", "")
    name = pending["tool"]
    arguments = pending["arguments"]

    if approval.get("approved"):
        with span("worker.execute_approved", tool=name):
            tool_result = _run(ctx.registry.invoke(name, arguments))
            output = str(tool_result)
    else:
        output = f"action {name!r} rejected by human"

    out: WorkerResult = {
        "subtask": subtask,
        "output": output,
        "tool_calls": [{"id": pending.get("call_id"), "function": {"name": name}}],
    }
    return {
        "results": [out],
        "cursor": cursor + 1,
        "pending_action": None,
        "approval": None,
    }


def _coerce_plan(content: str | None, task: str) -> list[str]:
    """Parse the orchestrator's reply into a list of subtasks; fall back to [task]."""
    if not content:
        return [task]
    text = content.strip()
    # Strip common markdown code fences.
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list) and parsed:
            return [str(x) for x in parsed]
    except json.JSONDecodeError:
        pass
    return [task]
