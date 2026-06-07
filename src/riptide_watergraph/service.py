"""Programmatic run service — the shared core behind the CLI and the HTTP server.

Builds the swappable components from settings, runs a task end-to-end (auto-approving
side-effecting tools, since there's no interactive operator here), enforces per-tenant
budgets, records usage, and returns a structured ``RunResult``. Multi-turn conversation
context is supported via an in-process ``SessionStore``.
"""

from __future__ import annotations

import asyncio
import base64
import mimetypes
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from pydantic import BaseModel, Field

from .config import Settings, get_settings
from .gateway import DemoGateway, LiteLLMGateway, ResilientGateway
from .graph import build_graph
from .guardrails import default_guardrails
from .memory import HashingEmbedding, JsonFileMemory, LexicalOverlapReranker
from .memory.reflection import LLMReflector
from .observability.cost import (
    BudgetExceeded,
    CostTracker,
    UsageRecord,
    cost_from_usage,
    estimate_tokens,
)
from .interfaces.gateway import Message
from .interfaces.swarm import SwarmComposer
from .autonomy import (
    AutonomyReport,
    Journal,
    LLMGoalProposer,
    TemplateGoalProposer,
    run_autonomous,
)
from .environments import Rollout, make_environment, rollout
from .observability.tracing import init_tracing
from .optimize import (
    Example,
    LLMPromptProposer,
    OptimizationResult,
    SubstringScorer,
    TemplateProposer,
    optimize_prompt,
)
from .reasoning import DeliberationResult, HeuristicVerifier, LLMVerifier, deliberate
from .skills import JsonFileSkillStore, LLMSkillSynthesizer, skill_to_spec
from .swarm import (
    HeuristicSwarmComposer,
    LLMSwarmComposer,
    SingleAgentComposer,
    StaticPlanComposer,
)
from .tools import default_registry
from .workflows import WorkflowSpec, spec_to_plan, validate_spec


@dataclass
class Components:
    """Everything build_graph needs, assembled from settings + flags."""

    gateway: Any
    registry: Any
    composer: Any
    memory: Any
    reflector: Any
    guardrails: Any
    model: str
    planner_model: str
    worker_model: str
    skill_synthesizer: Any = None
    skill_store: Any = None


class RunResult(BaseModel):
    """Structured outcome of a run (the API/CLI response shape)."""

    tenant_id: str
    final_answer: str | None = None
    blocked: bool = False
    success: bool | None = None
    mode: str = "single"
    recalled_lessons: list[str] = Field(default_factory=list)
    stored_lessons: list[str] = Field(default_factory=list)
    tool_calls_total: int = 0
    tool_calls_valid: int = 0
    structured: dict[str, Any] | None = None

    # --- detail fields for the Studio inspector (additive; default-empty) ---
    plan: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    results: list[dict[str, Any]] = Field(default_factory=list)
    verdicts: list[dict[str, Any]] = Field(default_factory=list)
    swarm_decision: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    guard_violations: list[str] = Field(default_factory=list)
    guard_violations_out: list[str] = Field(default_factory=list)
    clarifications: dict[str, str] = Field(default_factory=dict)
    learned_skills: list[str] = Field(default_factory=list)  # SkillForge: skills authored this run


def build_components(
    settings: Settings,
    *,
    tenant_id: str | None = None,
    offline: bool = False,
    single: bool = False,
    memory_on: bool = True,
    guardrails_on: bool = True,
    llm_composer: bool = False,
    skills_on: bool = False,
    composer: SwarmComposer | None = None,
) -> Components:
    """Assemble the swappable layers from settings + flags (shared by CLI + server)."""
    tenant_id = tenant_id or settings.tenant_id
    model = settings.riptide_watergraph_model
    planner_model = settings.planner_model or model
    worker_model = settings.worker_model or model

    base = DemoGateway() if offline else LiteLLMGateway(default_model=model)
    gateway = ResilientGateway(base)

    if composer is not None:
        pass  # caller-supplied (e.g. a StaticPlanComposer from a workflow spec)
    elif single:
        composer = SingleAgentComposer(model=planner_model)
    elif llm_composer:
        composer = LLMSwarmComposer(gateway, model=planner_model)
    else:
        composer = HeuristicSwarmComposer(model=planner_model)

    memory = None
    reflector = None
    if memory_on:
        memory = JsonFileMemory(
            settings.tenant_memory_path(tenant_id),
            embedding=HashingEmbedding(),
            reranker=LexicalOverlapReranker(),
        )
        reflector = LLMReflector(gateway, model=planner_model)

    guardrails = default_guardrails() if guardrails_on else None

    registry = default_registry()
    skill_synthesizer = None
    skill_store = None
    if skills_on:
        skill_store = JsonFileSkillStore(settings.tenant_skills_dir(tenant_id))
        skill_synthesizer = LLMSkillSynthesizer(gateway, model=planner_model)
        # Load previously-learned skills so they're available as tools this run.
        for sk in skill_store.load_all():
            registry.register(skill_to_spec(sk, gateway=gateway, model=planner_model))

    return Components(
        gateway=gateway,
        registry=registry,
        composer=composer,
        memory=memory,
        reflector=reflector,
        guardrails=guardrails,
        model=model,
        planner_model=planner_model,
        worker_model=worker_model,
        skill_synthesizer=skill_synthesizer,
        skill_store=skill_store,
    )


def enforce_budget(settings: Settings, tenant_id: str) -> None:
    """Raise BudgetExceeded if the tenant has reached its spend ceiling."""
    ceiling = settings.tenant_budget_usd
    if ceiling and ceiling > 0:
        spent = CostTracker(settings.usage_log_path).by_tenant().get(tenant_id)
        if spent is not None and spent.cost_usd >= ceiling:
            raise BudgetExceeded(tenant_id, spent.cost_usd, ceiling)


def _with_history(task: str, history: list[str] | None) -> str:
    """Prepend prior-turn answers as conversation context for a multi-turn session."""
    if not history:
        return task
    prior = "\n".join(f"- {h}" for h in history[-5:])
    return f"Earlier in this conversation:\n{prior}\n\nNow handle: {task}"


def run_task(
    task: str,
    *,
    tenant_id: str | None = None,
    offline: bool = False,
    memory_on: bool = True,
    single: bool = False,
    guardrails_on: bool = True,
    llm_composer: bool = False,
    history: list[str] | None = None,
    auto_approve: bool = True,
    critic: bool = False,
    supervisor: bool = False,
    react_steps: int = 1,
    vote_k: int = 1,
    final_schema: dict[str, Any] | None = None,
    sampling: dict[str, Any] | None = None,
    learn_skills: bool = False,
    composer: SwarmComposer | None = None,
    settings: Settings | None = None,
) -> RunResult:
    """Run a task end-to-end and return a structured result (no console I/O)."""
    settings = settings or get_settings()
    tenant_id = tenant_id or settings.tenant_id
    init_tracing(settings)
    Path(settings.checkpoint_path).parent.mkdir(parents=True, exist_ok=True)

    enforce_budget(settings, tenant_id)  # raises BudgetExceeded if over ceiling

    skills_on = learn_skills or os.getenv("RIPTIDE_ENABLE_SKILLS") == "1"
    comp = build_components(
        settings,
        tenant_id=tenant_id,
        offline=offline,
        single=single,
        memory_on=memory_on,
        guardrails_on=guardrails_on,
        llm_composer=llm_composer,
        skills_on=skills_on,
        composer=composer,
    )
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    with SqliteSaver.from_conn_string(settings.checkpoint_path) as cp:
        graph = build_graph(
            gateway=comp.gateway,
            registry=comp.registry,
            composer=comp.composer,
            model=comp.model,
            checkpointer=cp,
            memory=comp.memory,
            reflector=comp.reflector,
            skill_synthesizer=comp.skill_synthesizer,
            skill_store=comp.skill_store,
            guardrails=comp.guardrails,
            planner_model=comp.planner_model,
            worker_model=comp.worker_model,
            enable_critic=critic,
            enable_supervisor=supervisor,
            max_steps=react_steps,
            vote_k=vote_k,
            final_schema=final_schema,
            sampling=sampling,
        )
        _t0 = time.perf_counter()
        state = graph.invoke(
            {"task": _with_history(task, history), "session_id": thread_id,
             "tenant_id": tenant_id},
            config,
        )
        while "__interrupt__" in state and auto_approve:
            payload = state["__interrupt__"][0].value
            if isinstance(payload, dict) and payload.get("type") == "clarification":
                # No human in the loop here — let the worker proceed on its best assumption.
                resume: dict[str, Any] = {
                    "answer": "(no clarification available; proceed with your best assumption)"
                }
            else:
                resume = {"approved": True}
            state = graph.invoke(Command(resume=resume), config)

        _record_usage(settings, tenant_id, task, state,
                      latency_ms=int((time.perf_counter() - _t0) * 1000))

    return _result_from_state(tenant_id, state)


def _result_from_state(tenant_id: str, state: dict) -> RunResult:
    """Build the structured RunResult from the graph's final state."""
    metrics = state.get("metrics") or {}
    decision = state.get("swarm_decision") or {}
    return RunResult(
        tenant_id=tenant_id,
        final_answer=state.get("final_answer"),
        blocked=bool(state.get("blocked")),
        success=state.get("success"),
        mode=decision.get("mode", "single"),
        recalled_lessons=state.get("recalled_lessons") or [],
        stored_lessons=state.get("stored_lessons") or [],
        tool_calls_total=metrics.get("tool_calls_total", 0),
        tool_calls_valid=metrics.get("tool_calls_valid", 0),
        structured=state.get("structured_output") or None,
        plan=state.get("plan") or [],
        roles=state.get("roles") or [],
        results=list(state.get("results") or []),
        verdicts=list(state.get("verdicts") or []),
        swarm_decision=decision,
        metrics=metrics,
        guard_violations=state.get("guard_violations") or [],
        guard_violations_out=state.get("guard_violations_out") or [],
        clarifications=state.get("clarifications") or {},
        learned_skills=state.get("learned_skills") or [],
    )


def deliberate_task(
    task: str,
    *,
    samples: int = 3,
    offline: bool = False,
    tenant_id: str | None = None,
    sampling: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> DeliberationResult:
    """Verified best-of-N deliberation (System 2): diverse candidates → scored → best + confidence."""
    settings = settings or get_settings()
    tenant_id = tenant_id or settings.tenant_id
    init_tracing(settings)
    enforce_budget(settings, tenant_id)
    comp = build_components(settings, tenant_id=tenant_id, offline=offline,
                            memory_on=False, guardrails_on=False)
    verifier = HeuristicVerifier() if offline else LLMVerifier(comp.gateway, model=comp.planner_model)
    return asyncio.run(deliberate(
        task, gateway=comp.gateway, model=comp.model, verifier=verifier,
        samples=samples, sampling=sampling,
    ))


def improve_prompt(
    base_prompt: str,
    examples: list[Example],
    *,
    offline: bool = False,
    candidates: int = 3,
    tenant_id: str | None = None,
    settings: Settings | None = None,
) -> OptimizationResult:
    """Self-improvement: rewrite an instruction, keeping a variant only if it scores higher."""
    settings = settings or get_settings()
    tenant_id = tenant_id or settings.tenant_id
    init_tracing(settings)
    comp = build_components(settings, tenant_id=tenant_id, offline=offline,
                            memory_on=False, guardrails_on=False)
    proposer = (TemplateProposer() if offline
                else LLMPromptProposer(comp.gateway, model=comp.planner_model))

    def runner(prompt: str, inp: str) -> str:
        result = asyncio.run(comp.gateway.complete(
            model=comp.model,
            messages=[Message(role="system", content=prompt),
                      Message(role="user", content=inp)],
        ))
        return result.content or ""

    return optimize_prompt(base_prompt, examples, runner=runner, proposer=proposer,
                           scorer=SubstringScorer(), candidates=candidates)


def image_to_data_uri(path: str) -> str:
    """Read a local image file into a ``data:`` URI usable as a vision image reference."""
    p = Path(path)
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    encoded = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def vision_chat(
    prompt: str,
    images: list[str],
    *,
    offline: bool = False,
    sampling: dict[str, Any] | None = None,
    tenant_id: str | None = None,
    settings: Settings | None = None,
) -> str:
    """Multimodal: ask one question about one or more images (single-agent, no graph)."""
    settings = settings or get_settings()
    tenant_id = tenant_id or settings.tenant_id
    init_tracing(settings)
    enforce_budget(settings, tenant_id)
    comp = build_components(settings, tenant_id=tenant_id, offline=offline,
                            memory_on=False, guardrails_on=False)
    result = asyncio.run(comp.gateway.complete(
        model=comp.model,
        messages=[Message(role="user", content=prompt, images=list(images))],
        **(sampling or {}),
    ))
    return result.content or ""


def run_in_environment(
    name: str,
    *,
    max_steps: int = 10,
    offline: bool = False,
    tenant_id: str | None = None,
    settings: Settings | None = None,
) -> Rollout:
    """Embodiment: roll an LLM policy out in a named environment (act → observe → reward)."""
    settings = settings or get_settings()
    tenant_id = tenant_id or settings.tenant_id
    init_tracing(settings)
    enforce_budget(settings, tenant_id)
    comp = build_components(settings, tenant_id=tenant_id, offline=offline,
                            memory_on=False, guardrails_on=False)
    env = make_environment(name)

    def policy(observation: str) -> str:
        result = asyncio.run(comp.gateway.complete(
            model=comp.model,
            messages=[Message(role="system", content="You are an agent acting in an environment. "
                              "Read the observation and reply with only your next action."),
                      Message(role="user", content=observation)],
        ))
        return result.content or ""

    return rollout(env, policy, max_steps=max_steps)


def run_autonomous_mission(
    mission: str,
    *,
    max_steps: int = 3,
    offline: bool = False,
    tenant_id: str | None = None,
    settings: Settings | None = None,
) -> AutonomyReport:
    """Autonomy: pursue a mission via self-set goals, journaled, bounded by max_steps + budget."""
    settings = settings or get_settings()
    tenant_id = tenant_id or settings.tenant_id
    init_tracing(settings)
    comp = build_components(settings, tenant_id=tenant_id, offline=offline,
                            memory_on=False, guardrails_on=False)
    proposer = (TemplateGoalProposer() if offline
                else LLMGoalProposer(comp.gateway, model=comp.planner_model))
    journal = Journal(settings.tenant_journal_path(tenant_id))

    def executor(description: str) -> str:
        result = run_task(description, tenant_id=tenant_id, offline=offline,
                          memory_on=False, settings=settings)
        return result.final_answer or ""

    return run_autonomous(mission, executor=executor, proposer=proposer,
                          journal=journal, max_steps=max_steps)


def stream_task(
    task: str,
    *,
    tenant_id: str | None = None,
    offline: bool = True,
    memory_on: bool = True,
    single: bool = False,
    guardrails_on: bool = True,
    llm_composer: bool = False,
    critic: bool = False,
    supervisor: bool = False,
    react_steps: int = 1,
    vote_k: int = 1,
    sampling: dict[str, Any] | None = None,
    history: list[str] | None = None,
    composer: SwarmComposer | None = None,
    settings: Settings | None = None,
):
    """Run a task, yielding ``("node", name)`` per executed graph node then
    ``("result", RunResult)``. Interrupts are auto-approved inline (headless)."""
    settings = settings or get_settings()
    tenant_id = tenant_id or settings.tenant_id
    init_tracing(settings)
    Path(settings.checkpoint_path).parent.mkdir(parents=True, exist_ok=True)
    enforce_budget(settings, tenant_id)

    comp = build_components(
        settings, tenant_id=tenant_id, offline=offline, single=single,
        memory_on=memory_on, guardrails_on=guardrails_on, llm_composer=llm_composer,
        composer=composer,
    )
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    with SqliteSaver.from_conn_string(settings.checkpoint_path) as cp:
        graph = build_graph(
            gateway=comp.gateway, registry=comp.registry, composer=comp.composer,
            model=comp.model, checkpointer=cp, memory=comp.memory, reflector=comp.reflector,
            guardrails=comp.guardrails, planner_model=comp.planner_model,
            worker_model=comp.worker_model, enable_critic=critic,
            enable_supervisor=supervisor, max_steps=react_steps, vote_k=vote_k,
            sampling=sampling,
        )
        pending: Any = {"task": _with_history(task, history),
                        "session_id": config["configurable"]["thread_id"],
                        "tenant_id": tenant_id}
        _t0 = time.perf_counter()
        for _ in range(50):  # bounded: re-stream after each auto-approved interrupt
            for chunk in graph.stream(pending, config, stream_mode="updates"):
                for node_name in chunk:
                    if not node_name.startswith("__"):
                        yield ("node", node_name)
            state = graph.get_state(config)
            if not state.next:  # graph finished (no pending node)
                break
            interrupts = getattr(state, "interrupts", None) or []
            payload = interrupts[0].value if interrupts else {}
            if isinstance(payload, dict) and payload.get("type") == "clarification":
                pending = Command(resume={"answer": "(no clarification available; proceed)"})
            else:
                pending = Command(resume={"approved": True})
        final = dict(graph.get_state(config).values)
        _record_usage(settings, tenant_id, task, final,
                      latency_ms=int((time.perf_counter() - _t0) * 1000))
    yield ("result", _result_from_state(tenant_id, final))


class PendingApproval(BaseModel):
    """Returned by ``run_interactive`` when the graph hit a side-effecting tool."""

    status: str = "pending_approval"
    thread_id: str
    action: dict[str, Any]   # the raw interrupt payload from the graph


async def stream_chat_tokens(
    message: str,
    *,
    history: list[str] | None = None,
    sampling: dict[str, Any] | None = None,
    tenant_id: str | None = None,
    offline: bool = False,
    settings: Settings | None = None,
):
    """Yield raw token strings from the model gateway (direct, no graph).

    This is a single-agent, tool-free completion — useful for a "type as you read"
    chat experience. For multi-agent graph runs use ``stream_task`` instead.
    The offline ``DemoGateway`` yields once (the full answer); live gateways yield
    real token deltas.
    """
    settings = settings or get_settings()
    tenant_id = tenant_id or settings.tenant_id
    init_tracing(settings)

    comp = build_components(settings, tenant_id=tenant_id, offline=offline,
                            memory_on=False, guardrails_on=False)
    model = comp.model
    # Build a minimal conversation: a system preamble then the user message.
    prior = history[-5:] if history else []
    messages: list[Message] = [
        Message(role="system",
                content="You are a helpful assistant. Be concise and accurate."),
        *[Message(role=("user" if i % 2 == 0 else "assistant"), content=h)
          for i, h in enumerate(prior)],
        Message(role="user", content=message),
    ]
    async for chunk in comp.gateway.stream(model=model, messages=messages,
                                           **(sampling or {})):
        yield chunk


def run_interactive(
    task: str,
    *,
    thread_id: str | None = None,
    tenant_id: str | None = None,
    offline: bool = False,
    memory_on: bool = True,
    single: bool = False,
    guardrails_on: bool = True,
    llm_composer: bool = False,
    critic: bool = False,
    supervisor: bool = False,
    react_steps: int = 1,
    vote_k: int = 1,
    final_schema: dict[str, Any] | None = None,
    sampling: dict[str, Any] | None = None,
    history: list[str] | None = None,
    settings: Settings | None = None,
) -> RunResult | PendingApproval:
    """Run a task with ``auto_approve=False``.

    Returns a ``PendingApproval`` (with the thread_id and the interrupt payload)
    when the graph pauses at a side-effecting tool, or a normal ``RunResult`` on
    completion.  Pass the returned ``thread_id`` to ``resume_interactive`` to
    approve/deny and continue.
    """
    settings = settings or get_settings()
    tenant_id = tenant_id or settings.tenant_id
    init_tracing(settings)
    Path(settings.checkpoint_path).parent.mkdir(parents=True, exist_ok=True)
    enforce_budget(settings, tenant_id)

    thread_id = thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    comp = build_components(
        settings, tenant_id=tenant_id, offline=offline, single=single,
        memory_on=memory_on, guardrails_on=guardrails_on, llm_composer=llm_composer,
    )
    with SqliteSaver.from_conn_string(settings.checkpoint_path) as cp:
        graph = build_graph(
            gateway=comp.gateway, registry=comp.registry, composer=comp.composer,
            model=comp.model, checkpointer=cp, memory=comp.memory,
            reflector=comp.reflector, guardrails=comp.guardrails,
            planner_model=comp.planner_model, worker_model=comp.worker_model,
            enable_critic=critic, enable_supervisor=supervisor,
            max_steps=react_steps, vote_k=vote_k, final_schema=final_schema,
            sampling=sampling,
        )
        _t0 = time.perf_counter()
        state = graph.invoke(
            {"task": _with_history(task, history), "session_id": thread_id,
             "tenant_id": tenant_id},
            config,
        )
        if "__interrupt__" in state:
            payload = state["__interrupt__"][0].value
            return PendingApproval(thread_id=thread_id,
                                   action=payload if isinstance(payload, dict) else {})
        _record_usage(settings, tenant_id, task, state,
                      latency_ms=int((time.perf_counter() - _t0) * 1000))
    return _result_from_state(tenant_id, state)


def resume_interactive(
    thread_id: str,
    *,
    approved: bool = True,
    answer: str | None = None,
    task: str = "",
    settings: Settings | None = None,
) -> RunResult | PendingApproval:
    """Resume an interrupted run after the operator approves/denies the pending action.

    Reopens the ``SqliteSaver`` checkpoint for ``thread_id`` and resumes with the
    correct ``Command(resume=…)`` payload. Returns ``PendingApproval`` again if
    the graph hits another interrupt (chained side-effecting tools), or a final
    ``RunResult`` when done.
    """
    settings = settings or get_settings()
    tenant_id = settings.tenant_id
    config = {"configurable": {"thread_id": thread_id}}

    with SqliteSaver.from_conn_string(settings.checkpoint_path) as cp:
        # Peek at the current interrupt to determine the resume shape.
        from .graph import build_graph as _bg  # local to avoid circular at module load
        graph_peek = _bg(
            gateway=DemoGateway(),  # gateway unused during peek/resume
            registry=default_registry(),
            composer=SingleAgentComposer(model="demo"),
            model="demo",
            checkpointer=cp,
        )
        state_view = graph_peek.get_state(config)
        interrupts = getattr(state_view, "interrupts", None) or []
        payload = interrupts[0].value if interrupts else {}

        if isinstance(payload, dict) and payload.get("type") == "clarification":  # pragma: no cover - tested via the clarify e2e suite; can't fake a SqliteSaver mid-interrupt
            resume: dict[str, Any] = {
                "answer": answer or "(no answer provided; proceed with best assumption)"
            }
        else:
            resume = {"approved": approved}

        _t0 = time.perf_counter()
        state = graph_peek.invoke(Command(resume=resume), config)

        if "__interrupt__" in state:  # pragma: no cover - chained interrupt tested via the service e2e suite
            new_payload = state["__interrupt__"][0].value
            return PendingApproval(thread_id=thread_id,
                                   action=new_payload if isinstance(new_payload, dict) else {})
        _record_usage(settings, tenant_id, task, state,
                      latency_ms=int((time.perf_counter() - _t0) * 1000))
    return _result_from_state(tenant_id, state)


def _workflow_composer(spec: WorkflowSpec, settings: Settings) -> StaticPlanComposer:
    """Validate a workflow spec and build a StaticPlanComposer that replays its DAG."""
    validate_spec(spec)
    plan, roles, dependencies = spec_to_plan(spec)
    return StaticPlanComposer(
        plan=plan, roles=roles, dependencies=dependencies,
        model=settings.riptide_watergraph_model,
        mode=None if spec.mode == "auto" else spec.mode,
    )


def run_workflow(
    spec: WorkflowSpec,
    *,
    tenant_id: str | None = None,
    offline: bool = False,
    memory_on: bool = True,
    guardrails_on: bool = True,
    critic: bool = False,
    supervisor: bool = False,
    settings: Settings | None = None,
) -> RunResult:
    """Run a user-authored workflow spec as a dependency-ordered swarm."""
    settings = settings or get_settings()
    composer = _workflow_composer(spec, settings)
    return run_task(
        spec.goal or spec.name, tenant_id=tenant_id, offline=offline,
        memory_on=memory_on, guardrails_on=guardrails_on, critic=critic,
        supervisor=supervisor, composer=composer, settings=settings,
    )


def stream_workflow(
    spec: WorkflowSpec,
    *,
    tenant_id: str | None = None,
    offline: bool = True,
    memory_on: bool = True,
    guardrails_on: bool = True,
    critic: bool = False,
    supervisor: bool = False,
    settings: Settings | None = None,
):
    """Stream a workflow run (node-by-node trace then result), like ``stream_task``."""
    settings = settings or get_settings()
    composer = _workflow_composer(spec, settings)
    yield from stream_task(
        spec.goal or spec.name, tenant_id=tenant_id, offline=offline,
        memory_on=memory_on, guardrails_on=guardrails_on, critic=critic,
        supervisor=supervisor, composer=composer, settings=settings,
    )


def _record_usage(settings: Settings, tenant_id: str, task: str, state: dict,
                  latency_ms: int = 0) -> None:
    decision = state.get("swarm_decision") or {}
    metrics = state.get("metrics") or {}
    blob = (
        task
        + " ".join(r.get("output", "") for r in (state.get("results") or []))
        + (state.get("final_answer") or "")
    )
    usage = (state.get("metrics") or {}).get("usage") or {}
    actual = int(usage.get("total_tokens", 0) or 0)
    cost = (
        cost_from_usage(settings.riptide_watergraph_model, usage)
        if actual > 0
        else float(decision.get("estimated_cost_usd", 0.0))
    )
    CostTracker(settings.usage_log_path).record(
        UsageRecord(
            tenant_id=tenant_id,
            task=task,
            mode=decision.get("mode", "single"),
            est_tokens=estimate_tokens(blob),
            actual_tokens=actual,
            cost_usd=cost,
            blocked=bool(state.get("blocked")),
            ts=time.time(),
            latency_ms=latency_ms,
            success=state.get("success"),
            tool_calls_total=int(metrics.get("tool_calls_total", 0) or 0),
            tool_calls_valid=int(metrics.get("tool_calls_valid", 0) or 0),
            n_subtasks=len(state.get("plan") or []),
        )
    )


class SessionStore:
    """In-process multi-turn conversation store (per-process; swap for a DB in prod)."""

    def __init__(self) -> None:
        self._sessions: dict[str, list[dict[str, Any]]] = {}

    def history(self, session_id: str) -> list[str]:
        return [t["answer"] for t in self._sessions.get(session_id, [])]

    def turns(self, session_id: str) -> list[dict[str, Any]]:
        return list(self._sessions.get(session_id, []))

    def append(self, session_id: str, task: str, result: RunResult) -> None:
        """Store an enriched turn (answer + inspector detail) for chat rendering."""
        self._sessions.setdefault(session_id, []).append({
            "task": task,
            "answer": result.final_answer or "",
            "mode": result.mode,
            "plan": result.plan,
            "roles": result.roles,
            "results": result.results,
            "verdicts": result.verdicts,
            "metrics": result.metrics,
            "blocked": result.blocked,
        })

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
