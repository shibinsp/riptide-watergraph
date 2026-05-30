"""Topological wave scheduling for dependency-aware subtask execution.

Given ``dependencies`` (a list where ``dependencies[i]`` holds the indices that subtask
``i`` depends on), produce ordered *waves*: each wave is a set of subtask indices whose
prerequisites are all satisfied, so they can run in parallel. Subtasks in later waves run
after earlier ones. Cycles (or out-of-range deps) are handled defensively by emitting any
remaining nodes as a final wave rather than looping forever.
"""

from __future__ import annotations


def topological_levels(dependencies: list[list[int]]) -> list[list[int]]:
    """Return execution waves (lists of subtask indices) honoring dependencies."""
    n = len(dependencies)
    if n == 0:
        return []

    # Sanitize: ignore self-deps and out-of-range indices.
    deps = [
        {d for d in dependencies[i] if 0 <= d < n and d != i} if i < len(dependencies)
        else set()
        for i in range(n)
    ]

    done: set[int] = set()
    levels: list[list[int]] = []
    while len(done) < n:
        wave = [i for i in range(n) if i not in done and deps[i] <= done]
        if not wave:
            # Cycle or unsatisfiable deps — emit the remainder so we never hang.
            wave = [i for i in range(n) if i not in done]
        levels.append(wave)
        done.update(wave)
    return levels
