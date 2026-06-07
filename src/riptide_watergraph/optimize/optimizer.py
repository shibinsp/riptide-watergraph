"""The prompt optimizer — propose variants, measure them, keep only what improves.

Scores the base prompt on labelled examples, scores each proposed variant the same way, and
returns the best. A variant is adopted **only if it strictly beats the base** — bounded,
verified self-improvement (no unmeasured change ever ships).
"""

from __future__ import annotations

import asyncio
from typing import Callable

from pydantic import BaseModel, Field

from ..interfaces.optimizer import Example, Proposer, Scorer

__all__ = ["CandidatePrompt", "OptimizationResult", "optimize_prompt"]

# A runner executes a prompt on an input and returns the prediction (e.g. a gateway call).
Runner = Callable[[str, str], str]


class CandidatePrompt(BaseModel):
    prompt: str
    score: float


class OptimizationResult(BaseModel):
    """The outcome of one optimization pass."""

    base_prompt: str
    base_score: float
    best_prompt: str
    best_score: float
    improved: bool
    candidates: list[CandidatePrompt] = Field(default_factory=list)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _evaluate(prompt: str, examples: list[Example], runner: Runner, scorer: Scorer) -> float:
    return _mean([scorer.score(runner(prompt, ex.input), ex.expected) for ex in examples])


def optimize_prompt(
    base_prompt: str,
    examples: list[Example],
    *,
    runner: Runner,
    proposer: Proposer,
    scorer: Scorer,
    candidates: int = 3,
) -> OptimizationResult:
    """Return the best prompt found; the base is kept unless a variant scores strictly higher."""
    base_score = _evaluate(base_prompt, examples, runner, scorer)
    best_prompt, best_score = base_prompt, base_score

    variants = asyncio.run(proposer.propose(base_prompt, examples, n=candidates))
    scored: list[CandidatePrompt] = []
    for variant in variants:
        score = _evaluate(variant, examples, runner, scorer)
        scored.append(CandidatePrompt(prompt=variant, score=score))
        if score > best_score:
            best_prompt, best_score = variant, score

    return OptimizationResult(
        base_prompt=base_prompt, base_score=base_score,
        best_prompt=best_prompt, best_score=best_score,
        improved=best_prompt != base_prompt, candidates=scored,
    )
