"""Single-agent composer (Stage-1 stub).

Always returns a single-agent decision. Stage 3 replaces ``decide`` with the
cost-aware gate that analyzes task decomposability and forms a team only when a swarm
beats a single agent net of the token-cost multiplier.
"""

from __future__ import annotations

from ..interfaces.swarm import SwarmComposer, SwarmDecision, TeamMember


class SingleAgentComposer(SwarmComposer):
    """Composer that always chooses a single worker."""

    def __init__(self, *, model: str) -> None:
        self.model = model

    async def decide(
        self, task: str, *, budget_usd: float | None = None
    ) -> SwarmDecision:
        return SwarmDecision(
            mode="single",
            members=[TeamMember(role="worker", model=self.model, tools=[])],
            estimated_cost_usd=0.0,
            rationale="Stage-1 stub: single agent. Cost-aware gate arrives in Stage 3.",
        )
