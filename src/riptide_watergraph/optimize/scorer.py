"""Scorers — deterministic, offline metrics for measuring a prompt's outputs."""

from __future__ import annotations

from ..interfaces.optimizer import Scorer

__all__ = ["SubstringScorer", "ExactMatchScorer"]


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


class SubstringScorer(Scorer):
    """1.0 if the expected answer appears anywhere in the prediction, else 0.0."""

    def score(self, prediction: str, expected: str) -> float:
        return 1.0 if _norm(expected) in _norm(prediction) else 0.0


class ExactMatchScorer(Scorer):
    """1.0 only if the (normalized) prediction equals the expected answer."""

    def score(self, prediction: str, expected: str) -> float:
        return 1.0 if _norm(prediction) == _norm(expected) else 0.0
