"""Autonomy — a gated, budget-bounded self-directed goal loop.

Track 5 (final) of the AGI-direction roadmap. Given a mission, the agent proposes its own
subgoals, executes them, journals the results, and proposes follow-ups (an auto-curriculum) —
always bounded by a hard step cap and the tenant budget.
"""

from __future__ import annotations

from ..interfaces.autonomy import Goal, GoalProposer, JournalEntry
from .journal import Journal
from .loop import AutonomyReport, run_autonomous
from .proposer import LLMGoalProposer, TemplateGoalProposer

__all__ = [
    "Goal",
    "GoalProposer",
    "JournalEntry",
    "Journal",
    "AutonomyReport",
    "run_autonomous",
    "TemplateGoalProposer",
    "LLMGoalProposer",
]
