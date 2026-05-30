"""Swarm composer interface — the runtime team-formation seam.

Stage 1 ships ``SingleAgentComposer`` (always single-agent). Stage 3 implements the
cost-aware gate: analyze the task, decide single-vs-swarm, and form a team — only
choosing a swarm when the task genuinely decomposes net of the token-cost multiplier.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, Field


class TeamMember(BaseModel):
    """One worker in a composed team."""

    role: str
    model: str
    tools: list[str] = Field(default_factory=list)


class SwarmDecision(BaseModel):
    """The composer's decision for a task."""

    mode: Literal["single", "swarm"]
    members: list[TeamMember]
    estimated_cost_usd: float = 0.0  # cost of the chosen mode
    single_cost_usd: float = 0.0  # cost if run as a single agent (for comparison)
    parallelism: int = 1  # number of workers that can run concurrently
    rationale: str = ""
    # Optional decomposition produced by an LLM composer. ``plan`` is the subtask list;
    # ``dependencies[i]`` lists the indices subtask i depends on (empty => independent).
    # A heuristic composer leaves these empty and the orchestrator plans separately.
    plan: list[str] = Field(default_factory=list)
    dependencies: list[list[int]] = Field(default_factory=list)


class SwarmComposer(ABC):
    """Decides composition (single agent vs swarm) per task, cost-aware."""

    @abstractmethod
    async def decide(
        self, task: str, *, budget_usd: float | None = None
    ) -> SwarmDecision:
        """Return a composition decision. Stage-1 stub always returns single-agent."""
