"""Reward interface — the numeric-feedback seam for reinforcement-style learning.

A :class:`RewardModel` turns an outcome into a scalar in ``[0, 1]``. Combined with a bandit
over candidate strategies, the agent can *learn* which strategy maximizes reward for a task —
online policy improvement from a reward signal (the substrate for RL).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class RewardModel(ABC):
    """Scores an outcome as a scalar reward in ``[0, 1]`` (higher is better)."""

    @abstractmethod
    async def reward(self, task: str, answer: str) -> float:
        """Return the reward for ``answer`` as a response to ``task``."""
