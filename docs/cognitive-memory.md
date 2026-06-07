# Cognitive memory (knowledge graph + consolidation)

Added in **v0.16.0** — track 2 of the AGI-direction roadmap.

The framework already has **procedural** memory (distilled lessons) and **episodic** memory (raw run
trajectories). This adds the third [CoALA](https://arxiv.org/abs/2309.02427)-style store — **semantic**
memory: facts as `(subject, predicate, object)` triples in a **knowledge graph** — plus a **consolidation
"sleep" cycle** that distils accumulated experience into durable, queryable knowledge.

## The sleep cycle

In-run *reflection* distils one lesson per run. *Consolidation* is its offline counterpart: run it
periodically to compress many episodes into semantic knowledge.

```
episodic records ──▶ extract triples ──▶ knowledge graph ──▶ write SEMANTIC facts ──▶ recalled at runtime
(many past runs)     (subject,pred,obj)   (merge + weight)     (back into memory)      (existing recall node)
```

Because the existing **`recall` node already injects semantic records** (it only drops episodic ones),
the facts produced by consolidation are surfaced into prompts on future runs **with no graph change** —
the agent gets smarter as it sleeps.

```bash
riptide consolidate --tenant default
#  consolidated tenant=default
#    scanned 42 records (37 episodic)
#    knowledge graph: 58 facts; wrote 58 semantic record(s); pruned 3
```

## In code

```python
from riptide_watergraph.memory import JsonFileMemory, RuleTripleExtractor, consolidate_memory

report = consolidate_memory(
    memory,                         # a JsonFileMemory (the tenant's store)
    extractor=RuleTripleExtractor(),  # deterministic/offline, or LLMTripleExtractor(gateway, model=...)
    kg_path="data/tenants/default/knowledge.json",
)
print(report.triples, report.facts_written)
```

Query the graph directly:

```python
from riptide_watergraph.memory import KnowledgeGraph

kg = KnowledgeGraph.load("data/tenants/default/knowledge.json")
kg.facts_about("water")     # ["water is liquid", "water has hydrogen", ...] (ranked by recurrence)
kg.entities()               # every subject/object in the graph
```

## The seam (swappable)

| Interface | Default | Purpose |
|-----------|---------|---------|
| `TripleExtractor` | `RuleTripleExtractor` (offline) / `LLMTripleExtractor` | text → `(subject, predicate, object)` facts |
| `KnowledgeGraph` | pure-Python | merge-on-add (accumulates a `weight` per recurrence), query, persist |
| `consolidate_memory` | — | the sleep cycle: episodic → graph → semantic facts → recall |

Facts merge by case-insensitive identity, so a fact seen across many runs gains weight and ranks higher
in `facts_about`. The knowledge graph and the semantic records are **per-tenant**
(`DATA_DIR/tenants/<id>/knowledge.json`) — knowledge never leaks across tenants.

## Roadmap context

This is track 2 of the AGI-direction roadmap (after [SkillForge](skills.md)). Next: deliberate reasoning
(tree-search + debate + verifier), metacognition, self-improvement, and autonomy.
