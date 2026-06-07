"""Autonomy interface — the self-directed-goal seam.

Given a high-level mission, a :class:`GoalProposer` proposes subgoals; the loop executes them,
records what happened to a journal, and proposes follow-ups (an auto-curriculum) — bounded by a
hard step cap and the tenant budget. The substrate for open-ended, self-directed behaviour.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel


class Goal(BaseModel):
    """A subgoal the agent sets for itself in pursuit of a mission."""

    description: str
    parent: str = ""  # the mission or goal this was spun off from


class JournalEntry(BaseModel):
    """One completed goal and its result — the persistent record of autonomous work."""

    goal: str
    result: str


class GoalProposer(ABC):
    """Proposes the next subgoals given the mission and what's been done so far."""

    @abstractmethod
    async def propose(self, mission: str, history: list[JournalEntry]) -> list[Goal]:
        """Return the next subgoals to pursue (empty to stop)."""
