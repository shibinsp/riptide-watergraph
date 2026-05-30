"""Assemble the orchestrator-worker graph."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from ..interfaces.gateway import ModelGateway
from ..interfaces.swarm import SwarmComposer
from ..tools.registry import StaticToolRegistry
from .nodes import (
    GraphContext,
    make_finalize,
    make_human_approval,
    make_orchestrator,
    make_worker,
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
):
    """Build and compile the orchestrator-worker graph.

    Pass a checkpointer (e.g. ``SqliteSaver``) to enable durable interrupt/resume.
    """
    ctx = GraphContext(
        gateway=gateway, registry=registry, composer=composer, model=model
    )

    g: StateGraph = StateGraph(OrchestratorState)
    g.add_node("orchestrator", make_orchestrator(ctx))
    g.add_node("worker", make_worker(ctx))
    g.add_node("human_approval", make_human_approval(ctx))
    g.add_node("finalize", make_finalize(ctx))

    g.add_edge(START, "orchestrator")
    g.add_edge("orchestrator", "worker")
    g.add_conditional_edges(
        "worker",
        route_after_worker,
        {
            "human_approval": "human_approval",
            "worker": "worker",
            "finalize": "finalize",
        },
    )
    # After approval, return to worker, which resolves the pending action.
    g.add_edge("human_approval", "worker")
    g.add_edge("finalize", END)

    return g.compile(checkpointer=checkpointer)
