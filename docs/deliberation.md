# Deliberate reasoning

Added in **v0.17.0** — track 3 of the AGI-direction roadmap.

Self-consistency voting picks the **majority** answer with no check on quality. **Deliberation** does
better: generate several candidates from *different reasoning angles*, **score each with a verifier**, and
keep the best — verified **best-of-N**, the core of test-time-compute scaling (System 2). The result
carries a **confidence** that blends the winner's verifier score with how much the candidates agree — a
calibrated signal for **metacognition** ("am I sure, or should I escalate?").

```
task ──▶ diverse candidates ──▶ verifier scores each ──▶ best answer + confidence
         (direct, stepwise,       (HeuristicVerifier /     (escalate when low)
          critical, …)             LLMVerifier)
```

## CLI

```bash
riptide deliberate "What is the boiling point of water at sea level?" --samples 4 --offline
#  deliberation (4 candidates)
#    [0.78] stepwise     ...
#    [0.61] direct       ...
#    ...
#  BEST (score 0.78, confidence 0.71)
#  <answer>
```

If confidence is low, the CLI suggests escalating (more samples, debate, or a human).

## In code

```python
from riptide_watergraph.service import deliberate_task

result = deliberate_task("explain reciprocal rank fusion", samples=4)
print(result.answer, result.score, result.confidence)
if not result.confident(threshold=0.6):
    ...  # escalate: more samples / ask a human

# or drive the primitive directly with your own gateway + verifier
from riptide_watergraph.reasoning import deliberate, HeuristicVerifier
res = await deliberate(task, gateway=gw, model="gpt-4o-mini",
                       verifier=HeuristicVerifier(), samples=5)
```

## The seam (swappable)

| Interface | Default | Purpose |
|-----------|---------|---------|
| `Verifier` | `HeuristicVerifier` (offline) / `LLMVerifier` | score a candidate answer 0..1 |
| `deliberate(...)` | — | generate diverse candidates → score → best + confidence |
| `DeliberationResult` | — | the winner, ranked `candidates`, and a `confidence` (+ `confident()`) |

Candidates are generated under distinct **reasoning styles** (`DEFAULT_STYLES`: direct, stepwise,
critical, alternative, rigorous) — best-of-N only helps if the candidates actually differ. Offline, the
deterministic `HeuristicVerifier` scores by task/answer token overlap so the whole path runs without a key.

## Roadmap context

Track 3 of the AGI-direction roadmap (after [SkillForge](skills.md) and
[cognitive memory](cognitive-memory.md)). The same `Verifier` seam powers what's next: **multi-agent
debate** (agents critique and revise, the verifier judges), **tree-search** over reasoning steps, and
**metacognition** wired into the graph (escalate compute only when confidence is low).
