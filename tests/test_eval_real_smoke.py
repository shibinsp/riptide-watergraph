"""Live real-model eval smoke test — runs only with a real API key (skipped in CI).

    pip install -e ".[litellm]"
    export OPENAI_API_KEY=sk-...        # or ANTHROPIC_API_KEY
    export RIPTIDE_WATERGRAPH_MODEL=gpt-4o-mini
    pytest tests/test_eval_real_smoke.py

CI has no key, so this is skipped there; the real-model wiring (EvalRunner builds a
ResilientGateway(LiteLLMGateway)) is covered offline by tests/test_eval_real.py.
"""

from __future__ import annotations

import os

import pytest

from riptide_watergraph.evaluation import EvalRunner

pytestmark = pytest.mark.skipif(
    not (os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")),
    reason="set OPENAI_API_KEY / ANTHROPIC_API_KEY (and install [litellm]) to run the live eval",
)


def test_real_model_eval_runs():
    """The full eval suite runs end-to-end against a live model and scores a valid report."""
    report = EvalRunner(offline=False).run()
    assert report.n_total > 0
    assert 0.0 <= report.pass_rate <= 1.0
    assert report.n_passed <= report.n_total
