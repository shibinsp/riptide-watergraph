"""Deliberation — verified best-of-N over diverse reasoning candidates (System 2).

Instead of blind self-consistency ("majority wins"), generate several candidates from
*different* reasoning angles, score each with a :class:`Verifier`, and keep the best. The
result carries a **confidence** that blends the winner's verifier score with how much the
candidates agree — a calibrated signal for metacognition ("am I sure, or should I escalate?").
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..interfaces.gateway import Message, ModelGateway
from ..interfaces.verifier import Verifier

__all__ = ["Candidate", "DeliberationResult", "deliberate", "DEFAULT_STYLES"]

# Diverse reasoning lenses — best-of-N is only useful if the candidates differ.
DEFAULT_STYLES: list[tuple[str, str]] = [
    ("direct", "Answer the task directly and concisely."),
    ("stepwise", "Think step by step, then give the final answer."),
    ("critical", "Consider edge cases and likely pitfalls, then give the best answer."),
    ("alternative", "Approach the task from an unconventional angle, then answer."),
    ("rigorous", "Be precise and rigorous; justify briefly, then give the answer."),
]


class Candidate(BaseModel):
    """One scored answer produced under a particular reasoning style."""

    style: str
    answer: str
    score: float
    reason: str = ""


class DeliberationResult(BaseModel):
    """The outcome of a deliberation: the winning answer + ranked candidates + confidence."""

    task: str
    answer: str
    score: float
    confidence: float
    candidates: list[Candidate] = Field(default_factory=list)

    def confident(self, threshold: float = 0.6) -> bool:
        """Whether the result clears a confidence bar (else: escalate / ask a human)."""
        return self.confidence >= threshold


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def _confidence(candidates: list[Candidate]) -> float:
    """Blend the winner's verifier score with candidate agreement (self-consistency)."""
    best = candidates[0]
    agree = sum(1 for c in candidates if _norm(c.answer) == _norm(best.answer)) / len(candidates)
    return round(0.5 * best.score + 0.5 * agree, 3)


async def deliberate(
    task: str,
    *,
    gateway: ModelGateway,
    model: str,
    verifier: Verifier,
    samples: int = 3,
    sampling: dict | None = None,
    styles: list[tuple[str, str]] | None = None,
) -> DeliberationResult:
    """Generate diverse candidates, score them, and return the best with a confidence."""
    chosen = (styles or DEFAULT_STYLES)[: max(1, samples)]
    candidates: list[Candidate] = []
    for name, instruction in chosen:
        result = await gateway.complete(
            model=model,
            messages=[Message(role="system", content=instruction),
                      Message(role="user", content=task)],
            **(sampling or {}),
        )
        answer = (result.content or "").strip()
        verdict = await verifier.score(task, answer)
        candidates.append(Candidate(style=name, answer=answer,
                                    score=verdict.score, reason=verdict.reason))

    candidates.sort(key=lambda c: c.score, reverse=True)
    best = candidates[0]
    return DeliberationResult(
        task=task, answer=best.answer, score=best.score,
        confidence=_confidence(candidates), candidates=candidates,
    )
