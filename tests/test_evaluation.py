"""The offline evaluation suite doubles as a behavioral regression gate."""

from __future__ import annotations

from riptide_watergraph.evaluation import EvalRunner, default_suite


def test_offline_suite_all_pass():
    report = EvalRunner(offline=True).run()
    assert report.n_total == len(default_suite())
    failures = [(r.task_id, r.notes) for r in report.results if not r.passed]
    assert report.pass_rate == 1.0, failures


def test_suite_exercises_routing_and_guardrails():
    report = EvalRunner(offline=True).run()
    # at least one single-agent task, one swarm task, and one blocked attempt
    assert report.modes.get("single", 0) >= 1
    assert report.modes.get("swarm", 0) >= 1
    assert report.blocked >= 1


def test_self_learning_recall_probe():
    report = EvalRunner(offline=True).run()
    assert report.learning_recall is True
