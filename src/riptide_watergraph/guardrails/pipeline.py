"""Guardrail pipeline — runs a layered set of checks for a stage.

Policy: redactions chain (each guard sees the prior guard's transformed text); if any
guard blocks, the whole pipeline blocks. Returns one combined result.
"""

from __future__ import annotations

from ..interfaces.guardrail import Guardrail, GuardrailResult
from .injection import PromptInjectionGuardrail
from .pii import PiiGuardrail


class GuardrailPipeline:
    """Runs guardrails in order, chaining redactions and aggregating violations."""

    def __init__(self, guards: list[Guardrail]) -> None:
        self.guards = guards

    async def run(self, text: str, *, stage: str) -> GuardrailResult:
        current = text
        violations: list[str] = []
        allowed = True
        changed = False
        for guard in self.guards:
            result = await guard.check(current, stage=stage)
            if result.violations:
                violations.extend(result.violations)
            if result.transformed_text is not None:
                current = result.transformed_text
                changed = True
            if not result.allowed:
                allowed = False
        return GuardrailResult(
            allowed=allowed,
            transformed_text=current if changed else None,
            violations=violations,
        )


def default_guardrails() -> GuardrailPipeline:
    """A sensible default: block injections, redact PII."""
    return GuardrailPipeline([PromptInjectionGuardrail(), PiiGuardrail()])
