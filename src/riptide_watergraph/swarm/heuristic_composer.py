"""Cost-aware dynamic swarm composer (Stage 3).

Decides, per task and at runtime, whether to run a single agent or a parallel swarm —
and forms the team. A swarm is chosen only when the task genuinely decomposes into
several independent sub-goals AND it doesn't need human-approved side effects (those
serialize through the HITL gate). Otherwise it stays single, avoiding the multi-agent
token multiplier for work that wouldn't benefit.

This is the concrete "cost-aware gate": the decision carries both the chosen-mode cost
and the single-agent cost so callers can see the trade-off.
"""

from __future__ import annotations

from ..interfaces.swarm import SwarmComposer, SwarmDecision, TeamMember
from .cost import (
    MIN_SUBTASKS_FOR_SWARM,
    estimate_cost_usd,
    estimate_subtasks,
    looks_side_effecting,
)


class HeuristicSwarmComposer(SwarmComposer):
    """Rule-based composer with a transparent cost gate."""

    def __init__(self, *, model: str, max_parallelism: int = 4) -> None:
        self.model = model
        self.max_parallelism = max_parallelism

    async def decide(
        self, task: str, *, budget_usd: float | None = None
    ) -> SwarmDecision:
        n = estimate_subtasks(task)
        side_effecting = looks_side_effecting(task)
        single_cost = estimate_cost_usd(n, swarm=False)
        swarm_cost = estimate_cost_usd(n, swarm=True)

        go_swarm = n >= MIN_SUBTASKS_FOR_SWARM and not side_effecting
        if budget_usd is not None and swarm_cost > budget_usd:
            go_swarm = False  # respect a hard budget ceiling

        if go_swarm:
            parallelism = min(n, self.max_parallelism)
            members = [
                TeamMember(role=f"worker-{i+1}", model=self.model)
                for i in range(parallelism)
            ]
            rationale = (
                f"~{n} independent subtasks detected -> swarm of {parallelism} "
                f"(swarm ${swarm_cost} vs single ${single_cost}); parallelism justifies "
                "the coordination overhead."
            )
            return SwarmDecision(
                mode="swarm",
                members=members,
                estimated_cost_usd=swarm_cost,
                single_cost_usd=single_cost,
                parallelism=parallelism,
                rationale=rationale,
            )

        reason = (
            "task needs human-approved side effects (serial)"
            if side_effecting
            else f"~{n} subtask(s), below the swarm threshold ({MIN_SUBTASKS_FOR_SWARM})"
        )
        return SwarmDecision(
            mode="single",
            members=[TeamMember(role="worker", model=self.model)],
            estimated_cost_usd=single_cost,
            single_cost_usd=single_cost,
            parallelism=1,
            rationale=f"single agent: {reason}.",
        )
