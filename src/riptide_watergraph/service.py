"""Programmatic run service — the shared core behind the CLI and the HTTP server.

Builds the swappable components from settings, runs a task end-to-end (auto-approving
side-effecting tools, since there's no interactive operator here), enforces per-tenant
budgets, records usage, and returns a structured ``RunResult``. Multi-turn conversation
context is supported via an in-process ``SessionStore``.
"""

from __future__ import annotations

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
from .observability.tracing import init_tracing
from .swarm import HeuristicSwarmComposer, LLMSwarmComposer, SingleAgentComposer
from .tools import default_registry


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


def build_components(
    settings: Settings,
    *,
    tenant_id: str | None = None,
    offline: bool = False,
    single: bool = False,
    memory_on: bool = True,
    guardrails_on: bool = True,
    llm_composer: bool = False,
) -> Components:
    """Assemble the swappable layers from settings + flags (shared by CLI + server)."""
    tenant_id = tenant_id or settings.tenant_id
    model = settings.riptide_watergraph_model
    planner_model = settings.planner_model or model
    worker_model = settings.worker_model or model

    base = DemoGateway() if offline else LiteLLMGateway(default_model=model)
    gateway = ResilientGateway(base)

    if single:
        composer: Any = SingleAgentComposer(model=planner_model)
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
    return Components(
        gateway=gateway,
        registry=default_registry(),
        composer=composer,
        memory=memory,
        reflector=reflector,
        guardrails=guardrails,
        model=model,
        planner_model=planner_model,
        worker_model=worker_model,
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
    final_schema: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> RunResult:
    """Run a task end-to-end and return a structured result (no console I/O)."""
    settings = settings or get_settings()
    tenant_id = tenant_id or settings.tenant_id
    init_tracing(settings)
    Path(settings.checkpoint_path).parent.mkdir(parents=True, exist_ok=True)

    enforce_budget(settings, tenant_id)  # raises BudgetExceeded if over ceiling

    comp = build_components(
        settings,
        tenant_id=tenant_id,
        offline=offline,
        single=single,
        memory_on=memory_on,
        guardrails_on=guardrails_on,
        llm_composer=llm_composer,
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
            guardrails=comp.guardrails,
            planner_model=comp.planner_model,
            worker_model=comp.worker_model,
            final_schema=final_schema,
        )
        state = graph.invoke(
            {"task": _with_history(task, history), "session_id": thread_id,
             "tenant_id": tenant_id},
            config,
        )
        while "__interrupt__" in state and auto_approve:
            state = graph.invoke(Command(resume={"approved": True}), config)

        _record_usage(settings, tenant_id, task, state)

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
    )


def _record_usage(settings: Settings, tenant_id: str, task: str, state: dict) -> None:
    decision = state.get("swarm_decision") or {}
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
        )
    )


class SessionStore:
    """In-process multi-turn conversation store (per-process; swap for a DB in prod)."""

    def __init__(self) -> None:
        self._sessions: dict[str, list[dict[str, str]]] = {}

    def history(self, session_id: str) -> list[str]:
        return [t["answer"] for t in self._sessions.get(session_id, [])]

    def turns(self, session_id: str) -> list[dict[str, str]]:
        return list(self._sessions.get(session_id, []))

    def append(self, session_id: str, task: str, answer: str) -> None:
        self._sessions.setdefault(session_id, []).append(
            {"task": task, "answer": answer or ""}
        )
