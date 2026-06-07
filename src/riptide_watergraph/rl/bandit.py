"""A deterministic UCB1 multi-armed bandit — prefer higher-reward arms, explore the rest.

No randomness (so runs are reproducible): each arm is tried once, then selection maximizes the
upper-confidence bound ``mean + c*sqrt(ln(total)/n)``. ``best()`` returns the highest-mean arm.
"""

from __future__ import annotations

import math

__all__ = ["Bandit"]


class Bandit:
    """UCB1 bandit over a fixed set of named arms (strategies)."""

    def __init__(self, arms: list[str], *, c: float = 1.4) -> None:
        if not arms:
            raise ValueError("a bandit needs at least one arm")
        self.c = c
        self.counts: dict[str, int] = {a: 0 for a in arms}
        self.values: dict[str, float] = {a: 0.0 for a in arms}  # running mean reward
        self.total = 0

    @property
    def arms(self) -> list[str]:
        return list(self.counts)

    def select(self) -> str:
        for arm in self.arms:
            if self.counts[arm] == 0:  # play each arm once before exploiting
                return arm
        return max(self.arms, key=lambda a: self.values[a]
                   + self.c * math.sqrt(math.log(self.total) / self.counts[a]))

    def update(self, arm: str, reward: float) -> None:
        self.counts[arm] += 1
        self.total += 1
        n = self.counts[arm]
        self.values[arm] += (reward - self.values[arm]) / n  # incremental mean

    def best(self) -> str:
        return max(self.arms, key=lambda a: self.values[a])
