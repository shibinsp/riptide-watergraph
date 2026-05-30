"""Cost model + task-shape heuristics for the swarm composer.

These are deliberately simple, transparent estimates — the point is the *decision
gate*, not precise accounting. Multi-agent systems use far more tokens than a single
agent (coordination overhead; Anthropic reports ~15x for full multi-agent), so a swarm
must be justified by genuine, independent parallelism.
"""

from __future__ import annotations

import re

# Rough token/cost constants (cheap-model ballpark; tune per deployment).
TOKENS_PER_SUBTASK = 800
USD_PER_1K_TOKENS = 0.0005
SWARM_COORDINATION_OVERHEAD = 1.4  # a swarm spends ~40% more tokens coordinating

# Gate: only go parallel when at least this many independent subtasks exist.
MIN_SUBTASKS_FOR_SWARM = 3

# Verbs that imply a side effect / human approval — keep these single (HITL is serial).
_SIDE_EFFECT_RE = re.compile(
    r"\b(save|write|delete|remove|send|email|post|deploy|update|create|modify)\b",
    re.IGNORECASE,
)

# Connectives that typically separate independent sub-goals.
_SPLIT_RE = re.compile(r"\s+(?:and then|then|and|also|;|,|plus)\s+", re.IGNORECASE)


def estimate_subtasks(task: str) -> int:
    """Estimate how many independent sub-goals a task contains (>= 1)."""
    parts = [p for p in _SPLIT_RE.split(task) if p.strip()]
    return max(1, len(parts))


def looks_side_effecting(task: str) -> bool:
    """True if the task likely needs a side-effecting tool (=> human approval)."""
    return bool(_SIDE_EFFECT_RE.search(task))


def estimate_cost_usd(n_subtasks: int, *, swarm: bool) -> float:
    """Estimated USD cost for running ``n_subtasks`` single vs as a swarm."""
    base = n_subtasks * TOKENS_PER_SUBTASK
    tokens = base * (SWARM_COORDINATION_OVERHEAD if swarm else 1.0)
    return round(tokens / 1000 * USD_PER_1K_TOKENS, 6)
