"""Reward models — a numeric signal over an outcome.

``HeuristicRewardModel`` is deterministic and offline (task/answer overlap), so the bandit
loop is fully testable without a model. ``LLMRewardModel`` asks a model to grade the outcome.
"""

from __future__ import annotations

import json

from ..interfaces.gateway import Message, ModelGateway
from ..interfaces.reward import RewardModel
from ..memory.ranking import tokenize

__all__ = ["HeuristicRewardModel", "LLMRewardModel"]


class HeuristicRewardModel(RewardModel):
    """Offline, deterministic reward from answer presence + task/answer token overlap."""

    async def reward(self, task: str, answer: str) -> float:
        ans = (answer or "").strip()
        if not ans:
            return 0.0
        overlap = len(set(tokenize(ans)) & set(tokenize(task))) / (len(set(tokenize(task))) or 1)
        return round(min(1.0, 0.3 + 0.7 * overlap), 3)


_SYSTEM = (
    "You are a reward model. Rate how good the answer is for the task on a 0..1 scale. "
    'Reply ONLY as JSON: {"reward": <0..1>}.'
)


class LLMRewardModel(RewardModel):
    """Model-graded reward via a ModelGateway."""

    def __init__(self, gateway: ModelGateway, *, model: str) -> None:
        self.gateway = gateway
        self.model = model

    async def reward(self, task: str, answer: str) -> float:
        result = await self.gateway.complete(
            model=self.model,
            messages=[Message(role="system", content=_SYSTEM),
                      Message(role="user", content=f"Task: {task}\nAnswer: {answer}")],
        )
        return _parse_reward(result.content)


def _parse_reward(content: str | None) -> float:
    """Parse a reward reply into a float in [0, 1]; tolerant of fences, defaults to 0.0."""
    if not content:
        return 0.0
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return 0.0
    value = parsed.get("reward") if isinstance(parsed, dict) else parsed
    if value is None:
        return 0.0
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0
