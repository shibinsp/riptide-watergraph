"""Offline evaluation harness — measure the framework on a task suite.

The research consensus is to run your own evals on your task distribution rather than
trust vendor benchmarks. This harness makes the framework's behavior measurable:
pass rate, single-vs-swarm routing, guardrail blocking, tool-call validity, and
self-learning gain — deterministically, offline.
"""

from .runner import EvalReport, EvalResult, EvalRunner
from .suite import EvalTask, default_suite

__all__ = [
    "EvalTask",
    "default_suite",
    "EvalRunner",
    "EvalResult",
    "EvalReport",
]
