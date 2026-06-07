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
from dataclasses import dataclass, field
from typing import Any

import jsonschema
from langgraph.types import interrupt

from ..guardrails.pipeline import GuardrailPipeline
from ..interfaces.gateway import Message, ModelGateway
from ..interfaces.memory import Memory, MemoryRecord
from ..interfaces.reflector import Reflector, Trajectory
from ..interfaces.skill import SkillStore, SkillSynthesizer
from ..interfaces.swarm import SwarmComposer
from ..memory.types import MemoryType
from ..observability.tracing import span
from ..swarm.roles import get_role, role_for
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
    skill_synthesizer: SkillSynthesizer | None = None  # SkillForge: distill reusable skills
    skill_store: SkillStore | None = None  # SkillForge: persist learned skills
    recall_k: int = 3  # how many lessons to retrieve and inject
    tool_k: int = 4  # Stage 3: how many tools to retrieve on demand per subtask
    guardrails: GuardrailPipeline | None = None  # Stage 4: input/output safety
    max_rounds: int = 2  # supervisor re-planning cap (rounds incl. the first)
    max_handoffs: int = 1  # per-subtask agent-to-agent handoff cap
    max_steps: int = 1  # ReAct think->act->observe steps per subtask (1 = single-shot)
    vote_k: int = 1  # self-consistency samples for direct answers (1 = no voting)
    final_schema: dict[str, Any] | None = None  # JSON Schema for structured final output
    sampling: dict[str, Any] = field(default_factory=dict)  # temperature/top_p/max_tokens etc.

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


# A built-in (non-registry) pseudo-tool the worker offers so an agent can delegate its
# subtask to a better-suited specialist. Intercepted in the worker before tool dispatch.
_HANDOFF_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "handoff",
        "description": "Delegate this subtask to a better-suited specialist role "
        "(researcher, analyst, scribe, generalist).",
        "parameters": {
            "type": "object",
            "properties": {
                "role": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["role"],
        },
    },
}


# A built-in pseudo-tool the worker offers so an agent can pause and ask the human a
# clarifying question (HITL). Intercepted in the worker before tool dispatch; the answer
# is injected into the subtask's prompt on re-run (capped at one question per subtask).
_ASK_HUMAN_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "ask_human",
        "description": "Ask the human operator a clarifying question when the subtask is "
        "ambiguous. Use sparingly — only when you cannot proceed without the answer.",
        "parameters": {
            "type": "object",
            "properties": {"question": {"type": "string"}},
            "required": ["question"],
        },
    },
}


def _safe_invoke(ctx: GraphContext, name: str, arguments: dict[str, Any]) -> str:
    """Invoke a tool, returning an error string instead of crashing on failure."""
    try:
        return str(_run(ctx.registry.invoke(name, arguments)))
    except Exception as exc:  # noqa: BLE001 - isolate tool failures from the graph
        return f"tool {name!r} failed: {type(exc).__name__}: {exc}"


def _maybe_handoff(
    state: OrchestratorState, cursor: int, result: Any, max_handoffs: int
) -> dict[str, Any] | None:
    """If the worker emitted a ``handoff`` call, re-assign the role and re-run once.

    Returns a state update (no cursor advance => the worker re-runs this subtask under
    the new role), or ``None`` if there's no handoff. String keys survive checkpointing.
    """
    if not result.tool_calls:
        return None
    fn = result.tool_calls[0].get("function") or {}
    if fn.get("name") != "handoff":
        return None

    plan = state.get("plan") or []
    subtask = plan[cursor] if cursor < len(plan) else ""
    handoffs = dict(state.get("handoffs") or {})
    used = int(handoffs.get(str(cursor), 0))
    if used >= max_handoffs:
        out: WorkerResult = {
            "subtask": subtask,
            "output": "handoff limit reached; handled by the current agent",
            "tool_calls": list(result.tool_calls[:1]),
        }
        return {"results": [out], "cursor": cursor + 1}

    try:
        args = json.loads(fn.get("arguments", "{}"))
    except (json.JSONDecodeError, TypeError):
        args = {}
    roles = list(state.get("roles") or ["generalist"] * len(plan))
    if cursor < len(roles):
        roles[cursor] = str(args.get("role") or "generalist")
    handoffs[str(cursor)] = used + 1
    return {"roles": roles, "handoffs": handoffs}


def _clarified(state: OrchestratorState, cursor: int, subtask: str) -> str:
    """Append any human clarification answer for this subtask to its prompt."""
    answer = (state.get("clarifications") or {}).get(str(cursor))
    return f"{subtask}\n\n(Human clarification: {answer})" if answer else subtask


def _maybe_clarify(
    state: OrchestratorState, cursor: int, subtask: str, result: Any
) -> dict[str, Any] | None:
    """If the worker emitted ``ask_human``, route to the clarification interrupt (once)."""
    if not result.tool_calls:
        return None
    fn = result.tool_calls[0].get("function") or {}
    if fn.get("name") != "ask_human":
        return None
    if str(cursor) in (state.get("clarifications") or {}):
        return None  # already answered — don't ask again
    try:
        args = json.loads(fn.get("arguments", "{}"))
    except (json.JSONDecodeError, TypeError):
        args = {}
    question = str(args.get("question") or "Could you clarify this subtask?")
    return {
        "pending_action": {
            "type": "clarification",
            "question": question,
            "subtask": subtask,
            "cursor": cursor,
        }
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
        if reason not in ("unknown_tool", "schema_violation"):  # pragma: no cover - validate_call only raises these two
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
                    ctx.gateway.complete(model=ctx.planner_model, messages=[sys, usr], **ctx.sampling)
                )
                _add_usage(metrics, result)
                plan = _coerce_plan(result.content, task)
                dependencies = [[] for _ in plan]

            # Assign a specialist role per subtask (composer-provided or by keyword).
            if decision.roles and len(decision.roles) == len(plan):
                roles = decision.roles
            else:
                roles = [role_for(s) for s in plan]

            return {
                "plan": plan,
                "dependencies": dependencies,
                "roles": roles,
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
        role = get_role((state.get("roles") or ["generalist"] * len(plan))[cursor])
        with span("worker", subtask=subtask, cursor=cursor, role=role.name):
            allowed = set(role.tools) if role.tools is not None else None
            specs = _run(ctx.registry.retrieve(subtask, k=ctx.tool_k, allowed=allowed))
            tools = [s.to_openai_schema() for s in specs] + [_HANDOFF_SCHEMA]
            # Offer the clarify pseudo-tool only until this subtask has been answered once.
            if str(cursor) not in (state.get("clarifications") or {}):
                tools.append(_ASK_HUMAN_SCHEMA)
            # ReAct loop: think -> act -> observe, up to max_steps (1 == single-shot).
            messages = [
                Message(role="system", content=_lessons_block(state) + role.system_prompt),
                Message(role="user", content=_clarified(state, cursor, subtask)),
            ]

            # Self-consistency: sample k times; if all are direct answers, majority-vote.
            # If any sample wants a tool, abandon voting (so tools/side-effects run once).
            if ctx.vote_k > 1:
                samples = []
                for _ in range(ctx.vote_k):
                    s = _run(ctx.gateway.complete(
                        model=ctx.worker_model, messages=messages, tools=tools,
                        **{**ctx.sampling, "temperature": ctx.sampling.get("temperature", 0.7)}))
                    _add_usage(metrics, s)
                    samples.append(s)
                if all(not s.tool_calls for s in samples):
                    voted: WorkerResult = {
                        "subtask": subtask,
                        "output": _majority([s.content or "" for s in samples]),
                        "tool_calls": [],
                    }
                    return {"results": [voted], "cursor": cursor + 1, "metrics": metrics}
                # else fall through to a single normal ReAct pass below.

            last_step = ctx.max_steps - 1
            for step in range(ctx.max_steps):
                result = _run(
                    ctx.gateway.complete(
                        model=ctx.worker_model, messages=messages, tools=tools,
                        **ctx.sampling,
                    )
                )
                _add_usage(metrics, result)

                # Agent-to-agent handoff / clarification re-route the subtask.
                handoff = _maybe_handoff(state, cursor, result, ctx.max_handoffs)
                if handoff is not None:
                    handoff["metrics"] = metrics
                    return handoff
                clarify = _maybe_clarify(state, cursor, subtask, result)
                if clarify is not None:
                    clarify["metrics"] = metrics
                    return clarify

                if not result.tool_calls:
                    out: WorkerResult = {
                        "subtask": subtask,
                        "output": result.content or "",
                        "tool_calls": [],
                    }
                    return {"results": [out], "cursor": cursor + 1, "metrics": metrics}

                call = result.tool_calls[0]
                call_id, name, arguments, valid, reason = _parse_tool_call(ctx, call)
                metrics["tool_calls_total"] += 1
                if valid:
                    metrics["tool_calls_valid"] += 1
                elif reason in metrics["failures"]:
                    metrics["failures"][reason] += 1

                if not valid:
                    if step < last_step:  # let the model self-correct next step
                        _observe(messages, call, call_id, f"invalid tool call ({reason})")
                        continue
                    out = {
                        "subtask": subtask,
                        "output": f"invalid tool call ({reason}) for {name!r}",
                        "tool_calls": [call],
                    }
                    return {"results": [out], "cursor": cursor + 1, "metrics": metrics}

                if ctx.registry.get(name).side_effecting:
                    # Defer execution to AFTER approval (idempotency). Ends the loop.
                    return {
                        "pending_action": {
                            "tool": name, "arguments": arguments,
                            "subtask": subtask, "cursor": cursor, "call_id": call_id,
                        },
                        "metrics": metrics,
                    }

                # Read-only tool: execute (errors isolated). Observe and continue.
                observation = _safe_invoke(ctx, name, arguments)
                if step < last_step:
                    _observe(messages, call, call_id, observation)
                    continue
                out = {"subtask": subtask, "output": observation, "tool_calls": [call]}
                return {"results": [out], "cursor": cursor + 1, "metrics": metrics}

            return {}  # pragma: no cover - unreachable; loop always returns above

    return worker


def _majority(texts: list[str]) -> str:
    """Most-common answer by normalized text (ties -> earliest sample)."""
    from collections import Counter

    counts = Counter(t.strip() for t in texts)
    winner = counts.most_common(1)[0][0]
    return next((t for t in texts if t.strip() == winner), texts[0] if texts else "")


def _observe(messages: list[Message], call: dict[str, Any], call_id: str | None,
             observation: str) -> None:
    """Append the assistant tool-call + tool observation so the next step sees it."""
    messages.append(Message(role="assistant", content=None, tool_calls=[call]))
    messages.append(
        Message(role="tool", tool_call_id=call_id,
                name=(call.get("function") or {}).get("name"), content=observation)
    )


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
        roles = state.get("roles") or ["generalist"] * len(plan)
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
            role = get_role(roles[idx])
            sys = Message(
                role="system",
                content=preamble + _context_for(idx) + role.system_prompt,
            )
            usr = Message(role="user", content=plan[idx])
            allowed = set(role.tools) if role.tools is not None else None
            specs = await ctx.registry.retrieve(plan[idx], k=ctx.tool_k, allowed=allowed)
            tools = [s.to_openai_schema() for s in specs]
            result = await ctx.gateway.complete(
                model=ctx.worker_model, messages=[sys, usr], tools=tools, **ctx.sampling
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


def make_human_clarify(ctx: GraphContext):
    """Pause to ask the human a clarifying question, then re-run the subtask with the answer.

    Mirrors ``human_approval`` but for the ``ask_human`` pseudo-tool: ``interrupt()`` surfaces
    the question, the resume payload supplies the answer, which is stored in
    ``state['clarifications']`` and injected into the subtask's prompt on re-run. The cap
    (one answer per subtask) is enforced by the worker, which stops offering ``ask_human``
    once an answer exists.
    """

    def human_clarify(state: OrchestratorState) -> dict[str, Any]:
        pending = state.get("pending_action") or {}
        cursor = pending.get("cursor", state.get("cursor", 0))
        reply = interrupt(
            {
                "type": "clarification",
                "question": pending.get("question"),
                "subtask": pending.get("subtask"),
            }
        )
        # Normalize the resume payload into an answer string.
        if isinstance(reply, dict):
            answer = str(reply.get("answer", ""))
        else:
            answer = str(reply)
        clarifications = dict(state.get("clarifications") or {})
        clarifications[str(cursor)] = answer
        return {"clarifications": clarifications, "pending_action": None}

    return human_clarify


def make_finalize(ctx: GraphContext):
    """Compose the final answer from accumulated results."""

    def finalize(state: OrchestratorState) -> dict[str, Any]:
        results = state.get("results") or []
        verdicts = state.get("verdicts") or []
        metrics = state.get("metrics") or _empty_metrics()

        def passed(i: int) -> bool:
            return i >= len(verdicts) or verdicts[i].get("verdict") != "fail"

        verified = [r for i, r in enumerate(results) if passed(i)]
        failed = [r for i, r in enumerate(results) if not passed(i)]

        with span("finalize", n_results=len(results), n_failed=len(failed)):
            transcript = "\n".join(f"- {r['subtask']}: {r['output']}" for r in verified)
            note = (
                f"\n\n{len(failed)} subtask(s) failed verification and were excluded."
                if failed
                else ""
            )
            sys = Message(
                role="system",
                content="Compose a concise final answer from the verified worker results.",
            )
            usr = Message(
                role="user",
                content=f"Task: {state['task']}\n\nResults:\n{transcript}{note}",
            )
            result = _run(
                ctx.gateway.complete(model=ctx.planner_model, messages=[sys, usr], **ctx.sampling)
            )
            _add_usage(metrics, result)
            answer = (result.content or transcript) + note

            update: dict[str, Any] = {"final_answer": answer, "metrics": metrics}
            if ctx.final_schema is not None:
                structured = _structured_output(ctx, state, transcript, metrics)
                if structured is not None:
                    update["structured_output"] = structured
            return update

    return finalize


def _structured_output(
    ctx: GraphContext, state: OrchestratorState, transcript: str, metrics: dict[str, Any]
) -> dict[str, Any] | None:
    """Ask the model for a JSON object matching ``ctx.final_schema``; validate (retry once)."""
    schema = ctx.final_schema or {}
    sys = Message(
        role="system",
        content="Return ONLY a JSON object matching this JSON Schema, no prose: "
        + json.dumps(schema),
    )
    usr = Message(role="user", content=f"Task: {state['task']}\n\nResults:\n{transcript}")
    for _ in range(2):
        res = _run(ctx.gateway.complete(model=ctx.planner_model, messages=[sys, usr], **ctx.sampling))
        _add_usage(metrics, res)
        data = _parse_json_object(res.content)
        if data is not None:
            try:
                jsonschema.validate(instance=data, schema=schema)
                return data
            except jsonschema.ValidationError:
                continue
    return None


def _parse_json_object(content: str | None) -> dict[str, Any] | None:
    """Parse a JSON object from a model reply (tolerant of code fences)."""
    if not content:
        return None
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def make_critic(ctx: GraphContext):
    """Adversarially verify each worker result (pass/fail) before finalize."""

    def critic(state: OrchestratorState) -> dict[str, Any]:
        results = state.get("results") or []
        verdicts = list(state.get("verdicts") or [])
        metrics = state.get("metrics") or _empty_metrics()
        with span("critic", n_results=len(results)):
            for i in range(len(verdicts), len(results)):
                r = results[i]
                sys = Message(
                    role="system",
                    content=(
                        "You are a critic. Decide whether the subtask result is correct "
                        "and complete. Be skeptical. Reply ONLY as JSON: "
                        '{"verdict": "pass"|"fail", "reason": "<short>"}.'
                    ),
                )
                usr = Message(
                    role="user",
                    content=f"Subtask: {r['subtask']}\nResult: {r['output']}",
                )
                res = _run(ctx.gateway.complete(model=ctx.planner_model, messages=[sys, usr], **ctx.sampling))
                _add_usage(metrics, res)
                verdicts.append(_parse_verdict(res.content, r))
        return {"verdicts": verdicts, "metrics": metrics}

    return critic


def _parse_verdict(content: str | None, result: WorkerResult) -> dict[str, Any]:
    """Parse a critic reply; fall back to a heuristic on bad/empty output."""
    subtask = result.get("subtask", "")
    if content:
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if "\n" in text:
                text = text.split("\n", 1)[1]
        try:
            data = json.loads(text)
            verdict = "fail" if data.get("verdict") == "fail" else "pass"
            return {"subtask": subtask, "verdict": verdict, "reason": str(data.get("reason", ""))}
        except (json.JSONDecodeError, AttributeError):
            pass
    # Heuristic fallback: empty/error-looking output fails.
    out = (result.get("output") or "").lower()
    bad = (not out) or any(w in out for w in ("invalid", "failed", "error", "needs approval"))
    return {"subtask": subtask, "verdict": "fail" if bad else "pass", "reason": "heuristic"}


def make_supervisor(ctx: GraphContext):
    """Review verdicts and, if anything failed, append corrective subtasks (capped)."""

    def supervisor(state: OrchestratorState) -> dict[str, Any]:
        rnd = state.get("round", 0) + 1
        verdicts = state.get("verdicts") or []
        failed = [v for v in verdicts if v.get("verdict") == "fail"]
        metrics = state.get("metrics") or _empty_metrics()

        with span("supervisor", round=rnd, n_failed=len(failed)):
            if rnd >= ctx.max_rounds or not failed:
                return {"round": rnd, "metrics": metrics}  # routing -> finalize

            sys = Message(
                role="system",
                content=(
                    "You are a supervisor. Some subtasks failed verification. Propose a "
                    "short JSON array of corrective subtasks to fix them, or [] if none."
                ),
            )
            usr = Message(
                role="user",
                content="Failed: "
                + "; ".join(f"{v['subtask']} ({v.get('reason', '')})" for v in failed),
            )
            res = _run(ctx.gateway.complete(model=ctx.planner_model, messages=[sys, usr], **ctx.sampling))
            _add_usage(metrics, res)
            corrective = _parse_subtasks(res.content)
            if not corrective:
                return {"round": rnd, "metrics": metrics}  # nothing to add -> finalize

            plan = list(state.get("plan") or [])
            roles = list(state.get("roles") or [])
            deps = list(state.get("dependencies") or [])
            for sub in corrective:
                plan.append(sub)
                roles.append(role_for(sub))
                deps.append([])
            # cursor stays at the old length, so the worker picks up the new subtasks.
            return {
                "round": rnd,
                "plan": plan,
                "roles": roles,
                "dependencies": deps,
                "metrics": metrics,
            }

    return supervisor


def _parse_subtasks(content: str | None) -> list[str]:
    """Parse a JSON array of subtask strings; return [] on anything else."""
    if not content:
        return []
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(x) for x in parsed if str(x).strip()]
    except json.JSONDecodeError:
        pass
    return []


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


def make_skill_forge(ctx: GraphContext):
    """SkillForge: distill a reusable skill from a successful run and register it.

    On success, ask the synthesizer for a parameterized skill, verify it, persist it to the
    skill store, and register it (as a ``skill.<name>`` tool) so future runs can invoke it —
    the agent's toolset grows over time. A failed run, no distillable skill, or a skill that
    fails verification is a no-op (the default graph never includes this node).
    """
    from ..skills.forge import skill_to_spec
    from ..skills.verify import verify_skill

    def skill_forge(state: OrchestratorState) -> dict[str, Any]:
        assert ctx.skill_synthesizer is not None and ctx.skill_store is not None  # invariant
        if not _compute_success(state):
            return {}
        with span("skill_forge"):
            trajectory = Trajectory(
                task=state["task"],
                plan=state.get("plan") or [],
                results=[dict(r) for r in (state.get("results") or [])],
                success=True,
                metrics=state.get("metrics") or {},
                session_id=state.get("session_id", ""),
            )
            skill = _run(ctx.skill_synthesizer.synthesize(trajectory))
            if skill is None:
                return {}
            ok, _reason = verify_skill(skill, gateway=ctx.gateway, model=ctx.model)
            if not ok:
                return {}
            ctx.skill_store.save(skill)
            spec = skill_to_spec(skill, gateway=ctx.gateway, model=ctx.model)
            ctx.registry.register(spec)
            return {"learned_skills": [spec.name]}

    return skill_forge


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


def route_after_supervisor(state: OrchestratorState) -> str:
    """supervisor -> worker (corrective subtasks were appended) | finalize."""
    plan = state.get("plan") or []
    return "worker" if state.get("cursor", 0) < len(plan) else "finalize"


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
    """worker -> human_clarify | human_approval | worker (more) | finalize."""
    pending = state.get("pending_action")
    if pending is not None and state.get("approval") is None:
        if pending.get("type") == "clarification":
            return "human_clarify"
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
