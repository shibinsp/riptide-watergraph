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

from ..guardrails.pipeline import GuardrailPipeline
from ..interfaces.gateway import Message, ModelGateway
from ..interfaces.memory import Memory, MemoryRecord
from ..interfaces.reflector import Reflector, Trajectory
from ..interfaces.swarm import SwarmComposer
from ..memory.types import MemoryType
from ..observability.tracing import span
from ..tools.registry import StaticToolRegistry, ToolValidationError
from .state import OrchestratorState, WorkerResult
from .waves import topological_levels


@dataclass
class GraphContext:
    """Dependencies the nodes close over (injected by the builder)."""

    gateway: ModelGateway
    registry: StaticToolRegistry
    composer: SwarmComposer
    model: str
    planner_model: str = ""  # model for orchestrator/finalize (defaults to model)
    worker_model: str = ""  # model for workers (defaults to model; usually cheaper)
    memory: Memory | None = None  # Stage 2: long-term memory (recall + reflect)
    reflector: Reflector | None = None  # Stage 2: distills lessons from trajectories
    recall_k: int = 3  # how many lessons to retrieve and inject
    tool_k: int = 4  # Stage 3: how many tools to retrieve on demand per subtask
    guardrails: GuardrailPipeline | None = None  # Stage 4: input/output safety

    def __post_init__(self) -> None:
        # Per-role models default to the single configured model.
        self.planner_model = self.planner_model or self.model
        self.worker_model = self.worker_model or self.model


def _lessons_block(state: OrchestratorState) -> str:
    """Render recalled lessons as a system-prompt preamble (empty if none)."""
    lessons = state.get("recalled_lessons") or []
    if not lessons:
        return ""
    bullets = "\n".join(f"- {ln}" for ln in lessons)
    return (
        "Relevant lessons from past tasks (apply them):\n"
        f"{bullets}\n\n"
    )


def _run(coro: Any) -> Any:
    """Run an async coroutine to completion from a sync node."""
    return asyncio.run(coro)


def _empty_metrics() -> dict[str, Any]:
    return {
        "tool_calls_total": 0,
        "tool_calls_valid": 0,
        "failures": {"unknown_tool": 0, "bad_json": 0, "schema_violation": 0},
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def _add_usage(metrics: dict[str, Any], result: Any) -> None:
    """Fold a completion's real token usage into the metrics accumulator."""
    usage = getattr(result, "usage", None) or {}
    agg = metrics.setdefault(
        "usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    )
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        agg[key] += int(usage.get(key, 0) or 0)


def _safe_invoke(ctx: GraphContext, name: str, arguments: dict[str, Any]) -> str:
    """Invoke a tool, returning an error string instead of crashing on failure."""
    try:
        return str(_run(ctx.registry.invoke(name, arguments)))
    except Exception as exc:  # noqa: BLE001 - isolate tool failures from the graph
        return f"tool {name!r} failed: {type(exc).__name__}: {exc}"


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
        metrics = _empty_metrics()
        with span("orchestrator", task=task):
            # Cost-aware composition decision (single vs swarm) for this task.
            decision = _run(ctx.composer.decide(task))

            if decision.plan:
                # An LLM composer already produced the plan + dependencies.
                plan = decision.plan
                dependencies = decision.dependencies or [[] for _ in plan]
            else:
                # Heuristic composer: orchestrator plans the subtasks itself.
                sys = Message(
                    role="system",
                    content=(
                        _lessons_block(state)
                        + "You are a planning orchestrator. Break the user's task into "
                        "a short ordered list of concrete subtasks. Reply ONLY with a "
                        'JSON array of strings, e.g. ["step one", "step two"].'
                    ),
                )
                usr = Message(role="user", content=task)
                result = _run(
                    ctx.gateway.complete(model=ctx.planner_model, messages=[sys, usr])
                )
                _add_usage(metrics, result)
                plan = _coerce_plan(result.content, task)
                dependencies = [[] for _ in plan]

            return {
                "plan": plan,
                "dependencies": dependencies,
                "cursor": 0,
                "metrics": metrics,
                "swarm_decision": decision.model_dump(),
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
                    _lessons_block(state)
                    + "You are a worker. Accomplish the subtask. Use a tool if helpful; "
                    "otherwise answer directly and concisely."
                ),
            )
            usr = Message(role="user", content=subtask)
            # On-demand tool retrieval: only the most relevant tools enter context.
            specs = _run(ctx.registry.retrieve(subtask, k=ctx.tool_k))
            tools = [s.to_openai_schema() for s in specs]
            result = _run(
                ctx.gateway.complete(
                    model=ctx.worker_model, messages=[sys, usr], tools=tools
                )
            )
            _add_usage(metrics, result)

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

            # Read-only tool: execute inline (errors isolated, not crashing the run).
            out = {
                "subtask": subtask,
                "output": _safe_invoke(ctx, name, arguments),
                "tool_calls": [call],
            }
            return {"results": [out], "cursor": cursor + 1, "metrics": metrics}

    return worker


def make_swarm_worker(ctx: GraphContext):
    """Execute subtasks as dependency-ordered waves (Stage 3 / Phase C swarm mode).

    Subtasks with no unmet dependencies run concurrently within a wave (``asyncio.gather``
    over latency-dominant model calls); later waves run after the ones they depend on.
    A shared **blackboard** carries each subtask's output to its dependents (injected into
    their prompt), so a dependent subtask can build on upstream results. Side-effecting
    tools are NOT executed here — the composer routes approval-needing tasks to the serial
    single-agent path.
    """

    def swarm_worker(state: OrchestratorState) -> dict[str, Any]:
        plan = state.get("plan") or []
        deps = state.get("dependencies") or [[] for _ in plan]
        metrics = state.get("metrics") or _empty_metrics()
        preamble = _lessons_block(state)
        blackboard: dict[int, str] = {}
        results_by_idx: dict[int, WorkerResult] = {}

        def _context_for(idx: int) -> str:
            prereqs = [d for d in deps[idx] if d in blackboard]
            if not prereqs:
                return ""
            lines = "\n".join(f"- {plan[d]}: {blackboard[d]}" for d in prereqs)
            return f"Context from prior steps:\n{lines}\n\n"

        async def call(idx: int):
            sys = Message(
                role="system",
                content=(
                    preamble
                    + _context_for(idx)
                    + "You are a worker on one subtask. Use a tool if helpful; "
                    "otherwise answer directly and concisely."
                ),
            )
            usr = Message(role="user", content=plan[idx])
            specs = await ctx.registry.retrieve(plan[idx], k=ctx.tool_k)
            tools = [s.to_openai_schema() for s in specs]
            result = await ctx.gateway.complete(
                model=ctx.worker_model, messages=[sys, usr], tools=tools
            )
            return idx, result

        async def run_wave(indices: list[int]):
            return await asyncio.gather(*(call(i) for i in indices))

        levels = topological_levels(deps)
        with span("swarm_worker", n_subtasks=len(plan), n_waves=len(levels)):
            for wave in levels:
                pairs = _run(run_wave(wave))
                for idx, result in pairs:
                    _add_usage(metrics, result)
                    output, call_obj = _resolve_completion(ctx, plan[idx], result, metrics)
                    results_by_idx[idx] = {
                        "subtask": plan[idx],
                        "output": output,
                        "tool_calls": [call_obj] if call_obj else [],
                    }
                    blackboard[idx] = output  # available to dependents in later waves

        results = [results_by_idx[i] for i in range(len(plan)) if i in results_by_idx]
        return {
            "results": results,
            "cursor": len(plan),
            "metrics": metrics,
            "blackboard": blackboard,
        }

    return swarm_worker


def _resolve_completion(
    ctx: GraphContext, subtask: str, result: Any, metrics: dict[str, Any]
) -> tuple[str, dict[str, Any] | None]:
    """Turn a worker completion into (output, tool_call) for the swarm path."""
    if not result.tool_calls:
        return (result.content or "", None)
    call_obj = result.tool_calls[0]
    _id, name, arguments, valid, reason = _parse_tool_call(ctx, call_obj)
    metrics["tool_calls_total"] += 1
    if valid:
        metrics["tool_calls_valid"] += 1
    elif reason in metrics["failures"]:
        metrics["failures"][reason] += 1

    if not valid:
        return (f"invalid tool call ({reason}) for {name!r}", call_obj)
    if ctx.registry.get(name).side_effecting:
        return (f"{name!r} needs approval; rerun this subtask in single mode", call_obj)
    return (_safe_invoke(ctx, name, arguments), call_obj)


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
        metrics = state.get("metrics") or _empty_metrics()
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
            result = _run(
                ctx.gateway.complete(model=ctx.planner_model, messages=[sys, usr])
            )
            _add_usage(metrics, result)
            answer = result.content or transcript
            return {"final_answer": answer, "metrics": metrics}

    return finalize


# --------------------------------------------------------------------------- #
# Stage 2: memory recall + reflection
# --------------------------------------------------------------------------- #


def make_recall(ctx: GraphContext):
    """Retrieve relevant past lessons and stage them for prompt injection."""

    def recall(state: OrchestratorState) -> dict[str, Any]:
        assert ctx.memory is not None  # builder only adds this node when memory is set
        task = state["task"]
        with span("recall", task=task):
            # Over-fetch then drop episodic trajectories — only distilled lessons
            # (procedural/semantic) are injected into prompts.
            items = _run(ctx.memory.retrieve(task, k=ctx.recall_k * 2))
            lessons = [
                it.record.text
                for it in items
                if it.record.metadata.get("type") != MemoryType.EPISODIC.value
            ][: ctx.recall_k]
            return {"recalled_lessons": lessons}

    return recall


def make_reflect(ctx: GraphContext):
    """Judge the outcome and distill lessons into long-term memory."""

    def reflect(state: OrchestratorState) -> dict[str, Any]:
        assert ctx.reflector is not None and ctx.memory is not None  # builder invariant
        success = _compute_success(state)
        with span("reflect", success=success):
            trajectory = Trajectory(
                task=state["task"],
                plan=state.get("plan") or [],
                results=[dict(r) for r in (state.get("results") or [])],
                success=success,
                metrics=state.get("metrics") or {},
                session_id=state.get("session_id", ""),
            )
            lessons = _run(ctx.reflector.reflect(trajectory))
            # Store the full trajectory as episodic memory (not just the distilled
            # lesson) so the raw experience is preserved, per the research.
            episodic = _episodic_record(state, success)
            _run(ctx.memory.write([*lessons, episodic]))
            return {
                "success": success,
                "stored_lessons": [ln.text for ln in lessons],
            }

    return reflect


def _episodic_record(state: OrchestratorState, success: bool) -> MemoryRecord:
    """Summarize a completed run as an episodic memory record."""
    session = state.get("session_id", "") or state["task"][:24]
    results = state.get("results") or []
    steps = "; ".join(f"{r['subtask']} -> {r['output']}" for r in results)[:600]
    outcome = "success" if success else "failure"
    return MemoryRecord(
        id=f"episodic-{session}",
        text=f"Task: {state['task']} | outcome: {outcome} | {steps}",
        metadata={
            "type": MemoryType.EPISODIC.value,
            "task": state["task"],
            "success": success,
        },
    )


def _compute_success(state: OrchestratorState) -> bool:
    """Heuristic outcome signal: produced an answer, did work, no invalid tool calls."""
    metrics = state.get("metrics") or {}
    failures = sum((metrics.get("failures") or {}).values())
    has_answer = bool(state.get("final_answer"))
    did_work = len(state.get("results") or []) > 0
    return has_answer and did_work and failures == 0


# --------------------------------------------------------------------------- #
# Stage 4: guardrails
# --------------------------------------------------------------------------- #


def make_guard_input(ctx: GraphContext):
    """Screen the incoming task: block injections, redact PII before it spreads."""

    def guard_input(state: OrchestratorState) -> dict[str, Any]:
        assert ctx.guardrails is not None  # builder only adds this node with guardrails
        task = state["task"]
        with span("guard_input"):
            result = _run(ctx.guardrails.run(task, stage="input"))
            if not result.allowed:
                reasons = ", ".join(result.violations) or "policy violation"
                return {
                    "blocked": True,
                    "final_answer": f"[blocked by guardrails] {reasons}",
                    "guard_violations": result.violations,
                }
            update: dict[str, Any] = {"guard_violations": result.violations}
            if result.transformed_text is not None:
                update["task"] = result.transformed_text  # e.g. PII redacted
            return update

    return guard_input


def make_guard_output(ctx: GraphContext):
    """Screen the final answer: redact any PII before it reaches the user."""

    def guard_output(state: OrchestratorState) -> dict[str, Any]:
        assert ctx.guardrails is not None  # builder only adds this node with guardrails
        answer = state.get("final_answer") or ""
        with span("guard_output"):
            result = _run(ctx.guardrails.run(answer, stage="output"))
            update: dict[str, Any] = {}
            if result.transformed_text is not None:
                update["final_answer"] = result.transformed_text
            if result.violations:
                update["guard_violations_out"] = result.violations
            return update

    return guard_output


# --------------------------------------------------------------------------- #
# Routing
# --------------------------------------------------------------------------- #


def route_after_guard_input(state: OrchestratorState) -> str:
    """guard_input -> blocked (straight to END) | proceed."""
    return "blocked" if state.get("blocked") else "proceed"


def route_after_orchestrator(state: OrchestratorState) -> str:
    """orchestrator -> swarm_worker (parallel) | worker (sequential).

    Swarm only when the composer chose it AND the plan actually has >= 2 subtasks.
    """
    decision = state.get("swarm_decision") or {}
    plan = state.get("plan") or []
    if decision.get("mode") == "swarm" and len(plan) >= 2:
        return "swarm_worker"
    return "worker"


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
            output = _safe_invoke(ctx, name, arguments)
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
