"""The bounded autonomy loop — self-set goals, execute, journal, propose follow-ups.

Pursue a mission by executing proposed subgoals and topping up the queue with new ones when it
drains (an auto-curriculum). **Always bounded** by a hard ``max_steps`` cap (and, via the
executor, the tenant budget) — autonomy never runs away.
"""

from __future__ import annotations

import asyncio
from collections import deque
from typing import Callable

from pydantic import BaseModel, Field

from ..interfaces.autonomy import GoalProposer, JournalEntry
from .journal import Journal

__all__ = ["AutonomyReport", "run_autonomous"]

# An executor runs one goal (a task) and returns its result text.
Executor = Callable[[str], str]


class AutonomyReport(BaseModel):
    """What an autonomous run accomplished."""

    mission: str
    steps: int
    entries: list[JournalEntry] = Field(default_factory=list)


def run_autonomous(
    mission: str,
    *,
    executor: Executor,
    proposer: GoalProposer,
    journal: Journal,
    max_steps: int = 3,
) -> AutonomyReport:
    """Pursue ``mission`` for up to ``max_steps`` self-set goals, journaling each result."""
    queue = deque(asyncio.run(proposer.propose(mission, journal.entries())))
    steps = 0
    while queue and steps < max_steps:
        goal = queue.popleft()
        result = executor(goal.description)
        journal.append(JournalEntry(goal=goal.description, result=result))
        steps += 1
        # Auto-curriculum: when the queue drains, propose frontier goals from what we learned.
        if not queue and steps < max_steps:
            queue.extend(asyncio.run(proposer.propose(mission, journal.entries())))

    return AutonomyReport(mission=mission, steps=steps, entries=journal.entries())
