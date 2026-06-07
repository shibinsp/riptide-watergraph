"""A small, deterministic environment: guess the target number from higher/lower hints.

Offline-friendly and fully testable — it parses an integer from the agent's (free-text) action,
returns a hint + reward, and ends on a correct guess or after ``max_turns``.
"""

from __future__ import annotations

import re

from ..interfaces.environment import Environment, Observation

__all__ = ["GuessingGameEnv"]

_INT = re.compile(r"-?\d+")


def _first_int(text: str) -> int | None:
    m = _INT.search(text or "")
    return int(m.group()) if m else None


class GuessingGameEnv(Environment):
    """Guess ``target`` in ``[low, high]``; each step gives a higher/lower hint + reward."""

    def __init__(self, target: int = 42, low: int = 1, high: int = 100,
                 max_turns: int = 10) -> None:
        self.target = target
        self.low = low
        self.high = high
        self.max_turns = max_turns
        self.turns = 0

    def reset(self) -> Observation:
        self.turns = 0
        return Observation(text=f"Guess a whole number between {self.low} and {self.high}.")

    def step(self, action: str) -> Observation:
        self.turns += 1
        out_of_turns = self.turns >= self.max_turns
        guess = _first_int(action)
        if guess is None:
            return Observation(text="Please reply with a number.", done=out_of_turns)
        if guess == self.target:
            return Observation(text="Correct!", reward=1.0, done=True)
        hint = "higher" if guess < self.target else "lower"
        return Observation(text=f"Try {hint} than {guess}.", done=out_of_turns,
                           info={"hint": hint})
