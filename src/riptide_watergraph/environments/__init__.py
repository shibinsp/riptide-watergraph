"""Environments — the embodiment seam (act / observe / reward).

An experimental research track: a Gym-like ``Environment`` (reset/step) + a ``rollout`` loop, the
substrate that turns "answer a question" into "act, observe, and improve". Ships a deterministic
toy environment so the path is fully offline-testable.
"""

from __future__ import annotations

from ..interfaces.environment import Environment, Observation
from .guessing import GuessingGameEnv
from .runner import Rollout, Transition, rollout

__all__ = [
    "Environment",
    "Observation",
    "GuessingGameEnv",
    "Rollout",
    "Transition",
    "rollout",
    "make_environment",
    "ENVIRONMENTS",
]

# Registry of named, ready-to-run environments.
ENVIRONMENTS: dict[str, type[Environment]] = {"guessing": GuessingGameEnv}


def make_environment(name: str) -> Environment:
    """Build a registered environment by name (raises ``ValueError`` if unknown)."""
    try:
        return ENVIRONMENTS[name]()
    except KeyError:
        raise ValueError(
            f"unknown environment '{name}'; available: {', '.join(sorted(ENVIRONMENTS))}"
        ) from None
