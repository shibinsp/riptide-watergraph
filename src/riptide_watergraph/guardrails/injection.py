"""Prompt-injection / jailbreak detection guardrail.

Heuristic detector for the most common injection phrasings. On the **input** stage a
match blocks the request; on output it only flags (the model echoing such text isn't
itself an attack). Heuristics catch the obvious cases cheaply — pair with least-
privilege tools and monitoring for defense-in-depth.
"""

from __future__ import annotations

import re

from ..interfaces.guardrail import Guardrail, GuardrailResult

_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(?:all\s+)?(?:the\s+)?previous\s+instructions", re.I),
    re.compile(r"disregard\s+(?:all\s+)?(?:the\s+)?(?:above|previous)", re.I),
    re.compile(r"reveal\s+(?:your\s+)?(?:system\s+)?prompt", re.I),
    re.compile(r"(?:show|print|repeat)\s+(?:your\s+)?(?:system\s+)?(?:prompt|instructions)", re.I),
    re.compile(r"you\s+are\s+now\s+(?:a|an|in)\b", re.I),
    re.compile(r"developer\s+mode", re.I),
    re.compile(r"\bDAN\b", re.I),
    re.compile(r"ignore\s+(?:your\s+)?(?:guidelines|guardrails|rules)", re.I),
]


class PromptInjectionGuardrail(Guardrail):
    """Blocks inputs that look like prompt-injection / jailbreak attempts."""

    name = "prompt_injection"

    async def check(self, text: str, *, stage: str) -> GuardrailResult:
        matched = any(p.search(text) for p in _INJECTION_PATTERNS)
        if not matched:
            return GuardrailResult(allowed=True)
        # Block on input; only flag on output (the model echoing such text isn't an attack).
        return GuardrailResult(
            allowed=(stage != "input"), violations=["prompt_injection"]
        )
