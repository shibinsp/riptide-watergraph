"""Optimizer interface — the self-improvement seam.

Bounded recursive self-improvement: propose instruction variants, **measure** each against
labelled examples, and adopt a variant only when it scores strictly better (DSPy/STOP-style).
The agent rewrites its own prompts, but never adopts an unverified change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel


class Example(BaseModel):
    """One labelled example used to score a prompt: an input and its expected answer."""

    input: str
    expected: str


class Scorer(ABC):
    """Scores a prediction against the expected answer (1.0 = perfect, 0.0 = wrong)."""

    @abstractmethod
    def score(self, prediction: str, expected: str) -> float:
        """Return a score in ``[0, 1]`` for ``prediction`` vs ``expected``."""


class Proposer(ABC):
    """Proposes improved variants of a prompt given the examples it must satisfy."""

    @abstractmethod
    async def propose(self, prompt: str, examples: list[Example], *, n: int) -> list[str]:
        """Return up to ``n`` candidate rewrites of ``prompt``."""
