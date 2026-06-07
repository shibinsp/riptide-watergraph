# Self-improvement (measured prompt optimization)

Added in **v0.18.0** — track 4 of the AGI-direction roadmap.

The agent can rewrite its own instructions — but only adopts a change it can **measure**. Given a base
prompt and a handful of labelled examples, the optimizer proposes variants, scores each on the examples,
and keeps a variant **only if it strictly beats the base**. Bounded, verified recursive self-improvement
(DSPy / TextGrad / STOP-style) — no unmeasured change ever ships.

```
base prompt ──▶ propose variants ──▶ score each on examples ──▶ keep the best (only if it beats base)
                (TemplateProposer /    (SubstringScorer /
                 LLMPromptProposer)      ExactMatchScorer)
```

## CLI

```bash
echo '[{"input": "2 + 2", "expected": "4"}, {"input": "3 + 5", "expected": "8"}]' > ex.json
riptide improve "Answer the arithmetic question." --examples ex.json --candidates 4 --out best.txt
#  base score: 0.50
#  best score: 1.00 (improved)
#  wrote improved prompt to best.txt
#
#  BEST PROMPT
#  Answer the arithmetic question.
#
#  Think step by step before giving the final answer.
```

## In code

```python
from riptide_watergraph.service import improve_prompt
from riptide_watergraph.optimize import Example

result = improve_prompt(
    "Answer the question.",
    [Example(input="capital of France?", expected="Paris")],
    candidates=4,
)
print(result.base_score, "->", result.best_score, "improved" if result.improved else "kept base")
print(result.best_prompt)
```

Or drive the primitive directly with your own runner/proposer/scorer:

```python
from riptide_watergraph.optimize import optimize_prompt, TemplateProposer, SubstringScorer

result = optimize_prompt(
    base_prompt, examples,
    runner=lambda prompt, inp: my_model(prompt, inp),  # how a prompt is executed on an input
    proposer=TemplateProposer(), scorer=SubstringScorer(), candidates=5,
)
```

## The seam (swappable)

| Interface | Default | Purpose |
|-----------|---------|---------|
| `Proposer` | `TemplateProposer` (offline) / `LLMPromptProposer` | propose rewrites of a prompt |
| `Scorer` | `SubstringScorer` / `ExactMatchScorer` | measure a prediction vs the expected answer |
| `optimize_prompt(...)` | — | base vs candidates → adopt only a strictly-better variant |

`OptimizationResult` reports `base_score`, `best_score`, the `improved` flag, and every candidate's score
— so the gain (or lack of one) is always auditable. Offline, the deterministic `TemplateProposer` +
`SubstringScorer` make the whole loop run without a key.

## Roadmap context

Track 4 of the AGI-direction roadmap (after [SkillForge](skills.md),
[cognitive memory](cognitive-memory.md), and [deliberate reasoning](deliberation.md)). The same
`Scorer`/eval seam feeds what's next: optimizing **role prompts** and the **composer policy** against the
eval suite, and an **autonomy** loop with a self-generated curriculum.
