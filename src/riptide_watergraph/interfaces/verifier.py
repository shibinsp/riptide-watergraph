"""Verifier interface — the deliberate-reasoning (System 2) seam.

A :class:`Verifier` scores how good a candidate answer is for a task. It turns blind
self-consistency ("majority wins") into **verified best-of-N**: generate several diverse
candidates, score each, and keep the best — the core of test-time-compute scaling.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel


class Verdict(BaseModel):
    """A verifier's judgement of one candidate answer."""

    score: float  # 0.0 (poor) .. 1.0 (excellent)
    reason: str = ""


class Verifier(ABC):
    """Scores a candidate answer for a task (higher is better)."""

    @abstractmethod
    async def score(self, task: str, answer: str) -> Verdict:
        """Return a :class:`Verdict` rating ``answer`` as a response to ``task``."""
