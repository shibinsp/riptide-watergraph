"""Environment interface — the embodiment seam (Gym-like, text actions).

An :class:`Environment` turns "answer a question" into "act, observe, and get rewarded": the
agent ``reset()``s, then ``step(action)``s, receiving an :class:`Observation` (text + reward +
done) each time. This is the substrate for interactive, feedback-driven agents (and, later, RL).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class Observation(BaseModel):
    """What an environment returns from ``reset``/``step``."""

    text: str  # what the agent perceives (the next prompt)
    reward: float = 0.0  # scalar feedback for the action that produced this observation
    done: bool = False  # whether the episode has ended
    info: dict = Field(default_factory=dict)  # optional diagnostics


class Environment(ABC):
    """A text-action environment an agent can act in (Gym-like)."""

    @abstractmethod
    def reset(self) -> Observation:
        """Start a new episode and return the first observation."""

    @abstractmethod
    def step(self, action: str) -> Observation:
        """Apply ``action`` and return the resulting observation (with reward + done)."""
