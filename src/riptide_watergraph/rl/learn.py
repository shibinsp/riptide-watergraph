"""Learn the best strategy for a task from a reward signal (bandit + reward model)."""

from __future__ import annotations

import asyncio
from typing import Callable

from pydantic import BaseModel, Field

from ..interfaces.reward import RewardModel
from .bandit import Bandit

__all__ = ["ArmStats", "StrategyReport", "optimize_strategy"]

# A runner executes a named strategy (arm) on a task and returns the answer.
StrategyRunner = Callable[[str, str], str]


class ArmStats(BaseModel):
    arm: str
    pulls: int
    mean_reward: float


class StrategyReport(BaseModel):
    """Which strategy won, and each arm's learned value."""

    task: str
    best: str
    rounds: int
    arms: list[ArmStats] = Field(default_factory=list)


def optimize_strategy(
    task: str,
    arms: list[str],
    *,
    runner: StrategyRunner,
    reward_model: RewardModel,
    rounds: int = 6,
) -> StrategyReport:
    """Run a UCB bandit over ``arms`` for ``rounds``, learning the highest-reward strategy."""
    bandit = Bandit(arms)
    for _ in range(rounds):
        arm = bandit.select()
        answer = runner(arm, task)
        reward = asyncio.run(reward_model.reward(task, answer))
        bandit.update(arm, reward)

    stats = [ArmStats(arm=a, pulls=bandit.counts[a], mean_reward=round(bandit.values[a], 3))
             for a in bandit.arms]
    return StrategyReport(task=task, best=bandit.best(), rounds=rounds, arms=stats)
