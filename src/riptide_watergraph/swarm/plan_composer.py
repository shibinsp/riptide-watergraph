"""A composer that replays a user-authored plan (e.g. a Studio workflow canvas).

``make_orchestrator`` honors ``SwarmDecision.plan``/``.roles``/``.dependencies`` when a composer
supplies them (it skips its own planning), and ``make_swarm_worker`` + ``graph/waves`` execute the
dependency DAG. So a hand-built node/edge graph runs by handing those fields straight through —
no LLM planning, no ``graph/`` import here.
"""

from __future__ import annotations

from ..interfaces.swarm import SwarmComposer, SwarmDecision, TeamMember
from .cost import estimate_cost_usd


class StaticPlanComposer(SwarmComposer):
    """Replays a fixed plan/roles/dependencies as a ``SwarmDecision``."""

    def __init__(
        self,
        *,
        plan: list[str],
        roles: list[str],
        dependencies: list[list[int]],
        model: str,
        mode: str | None = None,
    ) -> None:
        self.plan = plan
        self.roles = roles
        self.dependencies = dependencies
        self.model = model
        # ``auto`` (mode=None) => swarm when there are >= 2 steps, else single.
        self._mode = mode if mode in ("swarm", "single") else (
            "swarm" if len(plan) >= 2 else "single")

    async def decide(self, task: str, *, budget_usd: float | None = None) -> SwarmDecision:
        n = len(self.plan)
        members = [TeamMember(role=r, model=self.model) for r in self.roles] or [
            TeamMember(role="generalist", model=self.model)
        ]
        return SwarmDecision(
            mode="swarm" if self._mode == "swarm" else "single",
            members=members,
            estimated_cost_usd=estimate_cost_usd(n or 1, swarm=(self._mode == "swarm")),
            single_cost_usd=estimate_cost_usd(n or 1, swarm=False),
            parallelism=max(1, n),
            rationale=f"static workflow: {n} node(s) authored in Studio.",
            plan=list(self.plan),
            dependencies=[list(d) for d in self.dependencies],
            roles=list(self.roles),
        )
