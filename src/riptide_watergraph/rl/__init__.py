"""Reward / RL — learn the highest-reward strategy from a numeric signal.

The final research seam: a :class:`RewardModel` scores outcomes, and a deterministic UCB
:class:`Bandit` over candidate strategies learns which one maximizes reward for a task —
online policy improvement (the substrate for reinforcement learning).
"""

from __future__ import annotations

from ..interfaces.reward import RewardModel
from .bandit import Bandit
from .learn import ArmStats, StrategyReport, optimize_strategy
from .reward import HeuristicRewardModel, LLMRewardModel

__all__ = [
    "RewardModel",
    "HeuristicRewardModel",
    "LLMRewardModel",
    "Bandit",
    "optimize_strategy",
    "StrategyReport",
    "ArmStats",
]
