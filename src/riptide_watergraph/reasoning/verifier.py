"""Verifiers — score a candidate answer's quality (the deliberation judge).

``HeuristicVerifier`` is deterministic and offline (task/answer token overlap), so the
deliberation path is testable without a model. ``LLMVerifier`` asks a model to grade the
answer on a 0..1 scale and is used when a real gateway is available.
"""

from __future__ import annotations

import json

from ..interfaces.gateway import Message, ModelGateway
from ..interfaces.verifier import Verdict, Verifier
from ..memory.ranking import tokenize

__all__ = ["HeuristicVerifier", "LLMVerifier"]


class HeuristicVerifier(Verifier):
    """Offline, deterministic scoring by answer presence + task/answer token overlap."""

    async def score(self, task: str, answer: str) -> Verdict:
        ans = (answer or "").strip()
        if not ans:
            return Verdict(score=0.0, reason="empty answer")
        a_tokens, t_tokens = set(tokenize(ans)), set(tokenize(task))
        overlap = len(a_tokens & t_tokens) / (len(t_tokens) or 1)
        length_bonus = 0.2 if len(ans) >= 4 else 0.0
        score = min(1.0, 0.4 + 0.4 * overlap + length_bonus)
        return Verdict(score=round(score, 3), reason=f"overlap={overlap:.2f}")


_SYSTEM = (
    "You are a strict answer verifier. Rate how well the answer solves the task on a scale "
    'from 0 to 1. Reply ONLY as JSON: {"score": <0..1>, "reason": "<short>"}.'
)


class LLMVerifier(Verifier):
    """Model-graded scoring via a ModelGateway."""

    def __init__(self, gateway: ModelGateway, *, model: str) -> None:
        self.gateway = gateway
        self.model = model

    async def score(self, task: str, answer: str) -> Verdict:
        result = await self.gateway.complete(
            model=self.model,
            messages=[Message(role="system", content=_SYSTEM),
                      Message(role="user", content=f"Task: {task}\nAnswer: {answer}")],
        )
        return _parse_verdict(result.content)


def _parse_verdict(content: str | None) -> Verdict:
    """Parse a grading reply into a Verdict; tolerant of code fences, clamps to [0, 1]."""
    if not content:
        return Verdict(score=0.0, reason="no verdict")
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return Verdict(score=0.0, reason="unparseable verdict")
    if isinstance(parsed, dict) and "score" in parsed:
        score = max(0.0, min(1.0, float(parsed["score"])))
        return Verdict(score=score, reason=str(parsed.get("reason", "")))
    return Verdict(score=0.0, reason="no score in verdict")
