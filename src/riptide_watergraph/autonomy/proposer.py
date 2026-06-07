"""Goal proposers — decompose a mission into self-set subgoals (the auto-curriculum)."""

from __future__ import annotations

import json

from ..interfaces.autonomy import Goal, GoalProposer, JournalEntry
from ..interfaces.gateway import Message, ModelGateway

__all__ = ["TemplateGoalProposer", "LLMGoalProposer"]


class TemplateGoalProposer(GoalProposer):
    """Deterministic, offline decomposition: a fixed opening curriculum then refinement."""

    async def propose(self, mission: str, history: list[JournalEntry]) -> list[Goal]:
        if not history:
            return [
                Goal(description=f"Break down and start: {mission}", parent=mission),
                Goal(description=f"Make concrete progress on: {mission}", parent=mission),
            ]
        return [Goal(description=f"Refine and extend the work on: {mission}", parent=mission)]


_SYSTEM = (
    "You are an autonomous planner. Given a mission and the work done so far, propose the next "
    "1-3 concrete subgoals (or none if the mission is complete). Reply ONLY as a JSON array of "
    'strings: ["subgoal", ...].'
)


class LLMGoalProposer(GoalProposer):
    """Model-driven goal proposal."""

    def __init__(self, gateway: ModelGateway, *, model: str) -> None:
        self.gateway = gateway
        self.model = model

    async def propose(self, mission: str, history: list[JournalEntry]) -> list[Goal]:
        done = "\n".join(f"- {e.goal} -> {e.result}" for e in history[-5:]) or "(nothing yet)"
        result = await self.gateway.complete(
            model=self.model,
            messages=[Message(role="system", content=_SYSTEM),
                      Message(role="user", content=f"Mission: {mission}\nDone so far:\n{done}")],
        )
        return [Goal(description=d, parent=mission) for d in _parse_goals(result.content)]


def _parse_goals(content: str | None) -> list[str]:
    """Parse a goal-list reply into strings; tolerant of code fences, skips non-strings."""
    if not content:
        return []
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item).strip() for item in parsed if isinstance(item, str) and item.strip()]
