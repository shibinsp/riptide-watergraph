"""Deliberate reasoning (System 2) — verified best-of-N + a confidence signal.

Generate diverse candidate answers, score them with a :class:`Verifier`, keep the best, and
report a calibrated confidence. Track 3 of the AGI-direction roadmap; multi-agent debate and
tree-search build on these seams next.
"""

from __future__ import annotations

from ..interfaces.verifier import Verdict, Verifier
from .deliberate import DEFAULT_STYLES, Candidate, DeliberationResult, deliberate
from .verifier import HeuristicVerifier, LLMVerifier

__all__ = [
    "Verdict",
    "Verifier",
    "HeuristicVerifier",
    "LLMVerifier",
    "Candidate",
    "DeliberationResult",
    "deliberate",
    "DEFAULT_STYLES",
]
