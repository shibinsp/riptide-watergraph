"""Self-improvement — measured prompt optimization (keep only verified gains).

Track 4 of the AGI-direction roadmap. Propose instruction variants, score them against labelled
examples, and adopt a variant only when it strictly beats the base. The agent rewrites its own
prompts but never ships an unmeasured change.
"""

from __future__ import annotations

from ..interfaces.optimizer import Example, Proposer, Scorer
from .optimizer import CandidatePrompt, OptimizationResult, optimize_prompt
from .proposer import LLMPromptProposer, TemplateProposer
from .scorer import ExactMatchScorer, SubstringScorer

__all__ = [
    "Example",
    "Scorer",
    "Proposer",
    "SubstringScorer",
    "ExactMatchScorer",
    "TemplateProposer",
    "LLMPromptProposer",
    "optimize_prompt",
    "OptimizationResult",
    "CandidatePrompt",
]
