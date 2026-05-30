"""Assemble the orchestrator-worker graph."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from ..guardrails.pipeline import GuardrailPipeline
from ..interfaces.gateway import ModelGateway
from ..interfaces.memory import Memory
from ..interfaces.reflector import Reflector
from ..interfaces.swarm import SwarmComposer
from ..tools.registry import StaticToolRegistry
from .nodes import (
    GraphContext,
    make_finalize,
    make_guard_input,
    make_guard_output,
    make_human_approval,
    make_orchestrator,
    make_recall,
    make_reflect,
    make_swarm_worker,
    make_worker,
    route_after_guard_input,
    route_after_orchestrator,
    route_after_worker,
)
from .state import OrchestratorState


def build_graph(
    *,
    gateway: ModelGateway,
    registry: StaticToolRegistry,
    composer: SwarmComposer,
    model: str,
    checkpointer: Any | None = None,
    memory: Memory | None = None,
    reflector: Reflector | None = None,
    guardrails: GuardrailPipeline | None = None,
    recall_k: int = 3,
    planner_model: str | None = None,
    worker_model: str | None = None,
):
    """Build and compile the orchestrator-worker graph.

    All advanced layers are optional and additive — with none of them, this is the
    Stage-1 skeleton:

    * ``checkpointer`` — durable interrupt/resume (e.g. ``SqliteSaver``).
    * ``memory`` — prepends a ``recall`` node (inject past lessons into prompts).
    * ``reflector`` (with ``memory``) — appends a ``reflect`` node (distill lessons).
    * ``guardrails`` — wraps the graph with ``guard_input`` (block/redact) and
      ``guard_output`` (redact) safety nodes.
    """
    ctx = GraphContext(
        gateway=gateway,
        registry=registry,
        composer=composer,
        model=model,
        planner_model=planner_model or "",
        worker_model=worker_model or "",
        memory=memory,
        reflector=reflector,
        guardrails=guardrails,
        recall_k=recall_k,
    )

    g: StateGraph = StateGraph(OrchestratorState)
    g.add_node("orchestrator", make_orchestrator(ctx))
    g.add_node("worker", make_worker(ctx))
    g.add_node("swarm_worker", make_swarm_worker(ctx))
    g.add_node("human_approval", make_human_approval(ctx))
    g.add_node("finalize", make_finalize(ctx))

    if memory is not None:
        g.add_node("recall", make_recall(ctx))
        g.add_edge("recall", "orchestrator")
        entry_node = "recall"
    else:
        entry_node = "orchestrator"

    # The composer's decision routes to parallel swarm or sequential single-agent.
    g.add_conditional_edges(
        "orchestrator",
        route_after_orchestrator,
        {"swarm_worker": "swarm_worker", "worker": "worker"},
    )
    g.add_conditional_edges(
        "worker",
        route_after_worker,
        {
            "human_approval": "human_approval",
            "worker": "worker",
            "finalize": "finalize",
        },
    )
    g.add_edge("human_approval", "worker")
    g.add_edge("swarm_worker", "finalize")

    # Reflection (if enabled) is the last logical step before output.
    if memory is not None and reflector is not None:
        g.add_node("reflect", make_reflect(ctx))
        g.add_edge("finalize", "reflect")
        exit_node = "reflect"
    else:
        exit_node = "finalize"

    # Guardrails wrap the whole graph: screen input up front, redact output at the end.
    if guardrails is not None:
        g.add_node("guard_input", make_guard_input(ctx))
        g.add_node("guard_output", make_guard_output(ctx))
        g.add_edge(START, "guard_input")
        g.add_conditional_edges(
            "guard_input",
            route_after_guard_input,
            {"blocked": END, "proceed": entry_node},
        )
        g.add_edge(exit_node, "guard_output")
        g.add_edge("guard_output", END)
    else:
        g.add_edge(START, entry_node)
        g.add_edge(exit_node, END)

    return g.compile(checkpointer=checkpointer)
