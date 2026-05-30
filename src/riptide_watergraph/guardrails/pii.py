"""PII detection + redaction guardrail.

Redacts (never blocks) common PII so it doesn't reach the model on input or the user
on output. Pattern-based and offline — for production, layer a dedicated PII scanner
(e.g. LLM Guard) on top; this is the always-on baseline.
"""

from __future__ import annotations

import re

from ..interfaces.guardrail import Guardrail, GuardrailResult

# (label, compiled pattern). Order matters: redact more specific patterns first.
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("PHONE", re.compile(r"\b(?:\+?\d{1,2}[\s-]?)?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4}\b")),
]


class PiiGuardrail(Guardrail):
    """Redacts emails, SSNs, credit-card numbers, and phone numbers."""

    name = "pii"

    async def check(self, text: str, *, stage: str) -> GuardrailResult:
        redacted = text
        found: list[str] = []
        for label, pattern in _PATTERNS:
            if pattern.search(redacted):
                found.append(label)
                redacted = pattern.sub(f"[REDACTED_{label}]", redacted)
        if not found:
            return GuardrailResult(allowed=True)
        return GuardrailResult(
            allowed=True,
            transformed_text=redacted,
            violations=[f"pii:{label.lower()}" for label in found],
        )
