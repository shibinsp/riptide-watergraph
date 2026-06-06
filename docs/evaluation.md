# Evaluation

The research consensus is to **run your own evals** rather than trust vendor benchmarks.

## Offline (deterministic)

```bash
riptide eval --offline
```

This runs a deterministic task suite through the **full graph** and scores:

- **pass rate**
- **single-vs-swarm routing**
- **guardrail blocking**
- **tool-call validity**
- a **self-learning recall probe** (does a repeated task recall a prior lesson?)

so behavior is measurable and regressions fail CI (4/4 = 100%).

## Against a real model

Everything above runs offline with the deterministic `DemoGateway`. To run against a live LLM, install a
gateway extra, set a key, and pick a model:

```bash
pip install "riptide-watergraph[litellm]"
export OPENAI_API_KEY=sk-...                    # or ANTHROPIC_API_KEY
export RIPTIDE_WATERGRAPH_MODEL=gpt-4o-mini     # any LiteLLM model string

riptide eval                                    # score the suite against the live model
python examples/real_model_chat.py "What is the capital of France?"
python examples/real_model_eval.py
```

The live path swaps in `LiteLLMGateway` wrapped in `ResilientGateway` (timeouts + retries) — no code
change, just env.

## In tests

- `tests/test_eval_real.py` covers the wiring offline (against a faked LiteLLM boundary) so the **100%
  coverage gate** holds without a key.
- `tests/test_eval_real_smoke.py` is **skip-guarded**: it runs the full suite end-to-end only when an API
  key is present, and is skipped in CI.

## Library use

```python
from riptide_watergraph.evaluation import EvalRunner

report = EvalRunner(offline=True).run()
print(f"{report.n_passed}/{report.n_total} = {report.pass_rate:.0%}")
print(report.modes, report.blocked, report.learning_recall)
```
