"""Proposers — generate candidate rewrites of a prompt.

``TemplateProposer`` is deterministic and offline (it appends proven strategy hints), so the
optimizer is fully testable without a model. ``LLMPromptProposer`` asks a model to rewrite the
prompt given the examples it must satisfy.
"""

from __future__ import annotations

from ..interfaces.gateway import Message, ModelGateway
from ..interfaces.optimizer import Example, Proposer

__all__ = ["TemplateProposer", "LLMPromptProposer", "STRATEGY_HINTS"]

STRATEGY_HINTS = [
    "Be concise and precise.",
    "Think step by step before giving the final answer.",
    "Double-check your answer against the question.",
    "Avoid assumptions; answer only what is asked.",
    "Prefer the most specific correct answer.",
]


class TemplateProposer(Proposer):
    """Deterministic variants: append distinct strategy hints to the base prompt."""

    async def propose(self, prompt: str, examples: list[Example], *, n: int) -> list[str]:
        return [f"{prompt}\n\n{STRATEGY_HINTS[i % len(STRATEGY_HINTS)]}" for i in range(n)]


_SYSTEM = (
    "You are a prompt optimizer. Rewrite the instruction so an assistant answers the given "
    "examples correctly. Reply with ONLY the rewritten instruction (no preamble)."
)


class LLMPromptProposer(Proposer):
    """Model-driven rewrites, one gateway call per requested candidate."""

    def __init__(self, gateway: ModelGateway, *, model: str) -> None:
        self.gateway = gateway
        self.model = model

    async def propose(self, prompt: str, examples: list[Example], *, n: int) -> list[str]:
        sample = "\n".join(f"- input: {e.input} | expected: {e.expected}" for e in examples[:5])
        user = f"Current instruction:\n{prompt}\n\nExamples:\n{sample}"
        variants: list[str] = []
        for _ in range(n):
            result = await self.gateway.complete(
                model=self.model,
                messages=[Message(role="system", content=_SYSTEM),
                          Message(role="user", content=user)],
            )
            text = (result.content or "").strip()
            if text:
                variants.append(text)
        return variants
