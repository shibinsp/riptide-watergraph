"""Guardrail interface — the safety/compliance seam.

A guardrail inspects text at a stage ("input" or "output") and may **block** it
(refuse to proceed) or **redact** it (return transformed text). Guardrails compose
into a pipeline; defense-in-depth means layering several cheap checks rather than
trusting one. There is no single fix for prompt injection — combine detection with
least-privilege tool access (the registry) and monitoring (tracing).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class GuardrailResult(BaseModel):
    """Outcome of a guardrail check."""

    allowed: bool = True  # False => block the request
    transformed_text: str | None = None  # set when the guard redacts/rewrites
    violations: list[str] = Field(default_factory=list)  # human-readable reasons


class Guardrail(ABC):
    """A single safety check applied at the input or output boundary."""

    name: str = "guardrail"

    @abstractmethod
    async def check(self, text: str, *, stage: str) -> GuardrailResult:
        """Inspect ``text`` for ``stage`` in {"input", "output"}."""
