"""LLM-driven swarm composer (Stage 3 → Phase C).

Asks the model to decompose the task into subtasks *with dependencies* and decide
single-vs-swarm, in one call. This replaces the heuristic regex split for real models:
the model judges genuine independence (so "build the API and write tests" can be marked
dependent rather than naively parallel). ``HeuristicSwarmComposer`` remains the offline
default; this one runs against any gateway (and the offline ``DemoGateway`` scripts it).
"""

from __future__ import annotations

import json

from ..interfaces.gateway import Message, ModelGateway
from ..interfaces.swarm import SwarmComposer, SwarmDecision, TeamMember
from .cost import estimate_cost_usd

_SYSTEM = (
    "You are a planning composer. Decompose the user's task into concrete subtasks and "
    "their dependencies, then decide whether to run them as a single agent or a parallel "
    "swarm. Reply ONLY as JSON: "
    '{"mode": "single|swarm", "subtasks": [{"task": "...", "depends_on": [<indices>]}]}. '
    "depends_on lists the indices of subtasks that must finish first (empty if independent)."
)


class LLMSwarmComposer(SwarmComposer):
    """Composer that asks the model for the plan, dependencies, and mode."""

    def __init__(
        self, gateway: ModelGateway, *, model: str, max_parallelism: int = 4
    ) -> None:
        self.gateway = gateway
        self.model = model
        self.max_parallelism = max_parallelism

    async def decide(
        self, task: str, *, budget_usd: float | None = None
    ) -> SwarmDecision:
        result = await self.gateway.complete(
            model=self.model,
            messages=[Message(role="system", content=_SYSTEM),
                      Message(role="user", content=task)],
        )
        plan, deps, mode = _parse(result.content, task)
        n = len(plan)
        single_cost = estimate_cost_usd(n, swarm=False)
        swarm_cost = estimate_cost_usd(n, swarm=True)

        if budget_usd is not None and swarm_cost > budget_usd:
            mode = "single"
        if n < 2:
            mode = "single"

        if mode == "swarm":
            width = _max_level_width(deps)
            parallelism = min(max(2, width), self.max_parallelism)
            members = [
                TeamMember(role=f"worker-{i+1}", model=self.model)
                for i in range(parallelism)
            ]
            cost = swarm_cost
        else:
            members = [TeamMember(role="worker", model=self.model)]
            parallelism = 1
            cost = single_cost

        return SwarmDecision(
            mode=mode,
            members=members,
            estimated_cost_usd=cost,
            single_cost_usd=single_cost,
            parallelism=parallelism,
            rationale=f"LLM composer: {n} subtask(s), mode={mode}.",
            plan=plan,
            dependencies=deps,
        )


def _parse(content: str | None, task: str) -> tuple[list[str], list[list[int]], str]:
    """Parse the composer reply into (plan, dependencies, mode); fall back to single."""
    if content:
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if "\n" in text:
                text = text.split("\n", 1)[1]
        try:
            data = json.loads(text)
            subs = data.get("subtasks") or []
            plan = [str(s.get("task", "")).strip() for s in subs if s.get("task")]
            deps = [
                [int(d) for d in (s.get("depends_on") or []) if isinstance(d, int)]
                for s in subs
                if s.get("task")
            ]
            mode = "swarm" if data.get("mode") == "swarm" else "single"
            if plan:
                return plan, deps, mode
        except (json.JSONDecodeError, AttributeError, ValueError, TypeError):
            pass
    return [task], [[]], "single"


def _max_level_width(deps: list[list[int]]) -> int:
    """Largest number of subtasks that can run in one parallel wave."""
    from ..graph.waves import topological_levels  # local import avoids cycle at load

    levels = topological_levels(deps)
    return max((len(level) for level in levels), default=1)
