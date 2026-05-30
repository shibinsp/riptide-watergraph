"""Evaluate the suite against a real LLM (needs an API key).

Setup:
    pip install -e ".[all]"
    export OPENAI_API_KEY=sk-...
    export AGENTIC_WATER_MODEL=gpt-4o-mini      # any LiteLLM model string

Run: python examples/real_model_eval.py     (or: riptide eval)
"""

from __future__ import annotations

from riptide_watergraph.evaluation import EvalRunner


def main() -> None:
    # offline=False routes through LiteLLM (wrapped in ResilientGateway) using the
    # model from settings (AGENTIC_WATER_MODEL).
    report = EvalRunner(offline=False).run()
    print(f"pass rate: {report.n_passed}/{report.n_total} = {report.pass_rate:.0%}")
    print(f"routing: {report.modes}; blocked: {report.blocked}; "
          f"self-learning recall: {report.learning_recall}")
    for r in report.results:
        print(f"  {r.task_id:<12} {'PASS' if r.passed else 'FAIL':<5} {r.mode:<8} {r.notes}")


if __name__ == "__main__":
    main()
