"""Track 3: EvalRunner real-model wiring (no network — only checks construction)."""

from __future__ import annotations

from riptide_watergraph.evaluation import EvalRunner
from riptide_watergraph.gateway import DemoGateway, LiteLLMGateway, ResilientGateway


def test_offline_runner_uses_demo_gateway():
    runner = EvalRunner(offline=True)
    assert runner.model == "demo"
    assert isinstance(runner._gateway(), DemoGateway)


def test_real_runner_uses_resilient_litellm(monkeypatch):
    monkeypatch.setenv("RIPTIDE_WATERGRAPH_MODEL", "gpt-4o-mini")
    runner = EvalRunner(offline=False)
    assert runner.model == "gpt-4o-mini"  # configured model, not a placeholder
    gw = runner._gateway()
    assert isinstance(gw, ResilientGateway)
    assert isinstance(gw.inner, LiteLLMGateway)
