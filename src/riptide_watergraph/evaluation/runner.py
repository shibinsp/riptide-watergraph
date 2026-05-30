"""Eval runner: build a graph, run the suite, score and aggregate.

Offline + deterministic by default (DemoGateway), so the suite doubles as a behavioral
regression gate in CI. Pass ``offline=False`` to evaluate against a real model.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..gateway import DemoGateway, LiteLLMGateway
from ..graph import build_graph
from ..guardrails import default_guardrails
from ..memory import HashingEmbedding, InMemoryMemory, LexicalOverlapReranker
from ..memory.reflection import LLMReflector
from ..swarm import HeuristicSwarmComposer
from ..tools import default_registry
from .suite import EvalTask, default_suite


class EvalResult(BaseModel):
    task_id: str
    passed: bool
    mode: str  # single | swarm | blocked
    blocked: bool = False
    tool_valid_rate: float | None = None
    notes: str = ""


class EvalReport(BaseModel):
    results: list[EvalResult] = Field(default_factory=list)
    pass_rate: float = 0.0
    n_passed: int = 0
    n_total: int = 0
    modes: dict[str, int] = Field(default_factory=dict)
    blocked: int = 0
    learning_recall: bool = False  # did a repeated task recall a prior lesson?


class EvalRunner:
    """Runs the task suite through a freshly built graph."""

    def __init__(self, *, offline: bool = True, model: str = "eval-model") -> None:
        self.offline = offline
        self.model = model

    def _gateway(self):
        return DemoGateway() if self.offline else LiteLLMGateway(default_model=self.model)

    def _build(self, memory):
        gateway = self._gateway()
        return build_graph(
            gateway=gateway,
            registry=default_registry(),
            composer=HeuristicSwarmComposer(model=self.model),
            model=self.model,
            memory=memory,
            reflector=LLMReflector(gateway, model=self.model),
            guardrails=default_guardrails(),
        )

    def run(self, suite: list[EvalTask] | None = None) -> EvalReport:
        suite = suite or default_suite()
        memory = InMemoryMemory(
            embedding=HashingEmbedding(), reranker=LexicalOverlapReranker()
        )
        graph = self._build(memory)

        results = [self._run_task(graph, t) for t in suite]
        report = EvalReport(
            results=results,
            n_total=len(results),
            n_passed=sum(1 for r in results if r.passed),
            blocked=sum(1 for r in results if r.blocked),
            learning_recall=self._probe_learning(),
        )
        report.pass_rate = (report.n_passed / report.n_total) if report.n_total else 0.0
        for r in results:
            report.modes[r.mode] = report.modes.get(r.mode, 0) + 1
        return report

    def _run_task(self, graph, task: EvalTask) -> EvalResult:
        state = graph.invoke(
            {"task": task.prompt, "session_id": task.id, "tenant_id": "eval"},
            {"configurable": {"thread_id": task.id}},
        )
        blocked = bool(state.get("blocked"))
        decision = state.get("swarm_decision") or {}
        mode = "blocked" if blocked else decision.get("mode", "single")

        metrics = state.get("metrics") or {}
        total = metrics.get("tool_calls_total", 0)
        valid = metrics.get("tool_calls_valid", 0)
        rate = (valid / total) if total else None

        passed, notes = self._score(task, state, blocked, mode)
        return EvalResult(
            task_id=task.id, passed=passed, mode=mode, blocked=blocked,
            tool_valid_rate=rate, notes=notes,
        )

    @staticmethod
    def _score(task: EvalTask, state: dict, blocked: bool, mode: str) -> tuple[bool, str]:
        if task.expect_blocked:
            return (blocked, "" if blocked else "expected block, was allowed")
        if blocked:
            return (False, "unexpectedly blocked")
        if task.expect_mode and mode != task.expect_mode:
            return (False, f"expected {task.expect_mode}, got {mode}")
        if task.expect_substring:
            blob = (
                task.prompt
                + " ".join(r.get("output", "") for r in (state.get("results") or []))
                + (state.get("final_answer") or "")
            ).lower()
            if task.expect_substring.lower() not in blob:
                return (False, f"missing expected {task.expect_substring!r}")
        return (True, "")

    def _probe_learning(self) -> bool:
        """Run one task twice; the second run should recall the first run's lesson."""
        memory = InMemoryMemory(
            embedding=HashingEmbedding(), reranker=LexicalOverlapReranker()
        )
        graph = self._build(memory)
        cfg1 = {"configurable": {"thread_id": "probe-1"}}
        cfg2 = {"configurable": {"thread_id": "probe-2"}}
        graph.invoke({"task": "compute 7 * 7", "session_id": "p1", "tenant_id": "eval"}, cfg1)
        s2 = graph.invoke({"task": "compute 7 * 7", "session_id": "p2", "tenant_id": "eval"}, cfg2)
        return bool(s2.get("recalled_lessons"))
