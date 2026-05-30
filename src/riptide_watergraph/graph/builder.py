"""Assemble the orchestrator-worker graph."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from ..interfaces.gateway import ModelGateway
from ..interfaces.memory import Memory
from ..interfaces.reflector import Reflector
from ..interfaces.swarm import SwarmComposer
from ..tools.registry import StaticToolRegistry
from .nodes import (
    GraphContext,
    make_finalize,
    make_human_approval,
    make_orchestrator,
    make_recall,
    make_reflect,
    make_swarm_worker,
    make_worker,
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
    recall_k: int = 3,
):
    """Build and compile the orchestrator-worker graph.

    Pass a checkpointer (e.g. ``SqliteSaver``) to enable durable interrupt/resume.

    Stage 2 (optional, additive): pass ``memory`` to prepend a ``recall`` node that
    retrieves past lessons and injects them into prompts; additionally pass
    ``reflector`` to append a ``reflect`` node that distills lessons back into memory.
    With neither, the graph is exactly the Stage-1 skeleton.
    """
    ctx = GraphContext(
        gateway=gateway,
        registry=registry,
        composer=composer,
        model=model,
        memory=memory,
        reflector=reflector,
        recall_k=recall_k,
    )

    g: StateGraph = StateGraph(OrchestratorState)
    g.add_node("orchestrator", make_orchestrator(ctx))
    g.add_node("worker", make_worker(ctx))
    g.add_node("swarm_worker", make_swarm_worker(ctx))
    g.add_node("human_approval", make_human_approval(ctx))
    g.add_node("finalize", make_finalize(ctx))

    # Entry: recall first if memory is present, else straight to the orchestrator.
    if memory is not None:
        g.add_node("recall", make_recall(ctx))
        g.add_edge(START, "recall")
        g.add_edge("recall", "orchestrator")
    else:
        g.add_edge(START, "orchestrator")

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
    # After approval, return to worker, which resolves the pending action.
    g.add_edge("human_approval", "worker")
    # The swarm handles all subtasks in one parallel pass, then finalizes.
    g.add_edge("swarm_worker", "finalize")

    # Exit: reflect after finalize when both memory and a reflector are present.
    if memory is not None and reflector is not None:
        g.add_node("reflect", make_reflect(ctx))
        g.add_edge("finalize", "reflect")
        g.add_edge("reflect", END)
    else:
        g.add_edge("finalize", END)

    return g.compile(checkpointer=checkpointer)
