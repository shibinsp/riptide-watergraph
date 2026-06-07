"""Roll a policy out in an environment — the act/observe/reward loop."""

from __future__ import annotations

from typing import Callable

from pydantic import BaseModel, Field

from ..interfaces.environment import Environment

__all__ = ["Transition", "Rollout", "rollout"]

# A policy maps an observation (text) to an action (text).
Policy = Callable[[str], str]


class Transition(BaseModel):
    """One step: the observation the policy saw, its action, and the reward it earned."""

    observation: str
    action: str
    reward: float
    done: bool


class Rollout(BaseModel):
    """The result of an episode."""

    steps: int
    total_reward: float
    transitions: list[Transition] = Field(default_factory=list)


def rollout(env: Environment, policy: Policy, *, max_steps: int = 10) -> Rollout:
    """Run ``policy`` in ``env`` until done or ``max_steps``; record the transitions."""
    obs = env.reset()
    transitions: list[Transition] = []
    total = 0.0
    steps = 0
    while not obs.done and steps < max_steps:
        seen = obs.text
        action = policy(seen)
        obs = env.step(action)
        transitions.append(Transition(observation=seen, action=action,
                                      reward=obs.reward, done=obs.done))
        total += obs.reward
        steps += 1
    return Rollout(steps=steps, total_reward=total, transitions=transitions)
