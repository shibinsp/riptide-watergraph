# Self-authored skills (SkillForge)

Added in **v0.15.0** — the first step of the AGI-direction roadmap.

Where [reflection](evaluation.md) distills a *lesson* (advice injected into prompts), **SkillForge**
distills a **skill**: a reusable, parameterized procedure the agent extracts from a successful run and
registers as a runnable `skill.<name>` tool. Future runs retrieve and invoke it directly — the agent's
own toolset **grows over time** (capability acquisition, à la Voyager).

A v0.15.0 skill is a **prompt-program**: a parameterized prompt template executed through the gateway —
**no code execution, safe by construction**. It is **off by default**, **verified before registration**,
and per-tenant.

## The loop

```
successful run ──▶ synthesize (LLM)  ──▶ verify  ──▶ persist + register  ──▶ available next run
                   distill a Skill       smoke-test    JsonFileSkillStore     skill.<name> tool
```

1. **Synthesize** — after a *successful* run, `LLMSkillSynthesizer` asks the model for a reusable,
   parameterized skill as JSON `{name, description, parameters, template, tags}`. A non-JSON / nameless /
   template-less reply yields nothing (quality gate).
2. **Verify** — `verify_skill` checks structure (name, template, JSON-Schema-object parameters) and runs
   one **smoke invocation** that must not raise. Unverified skills are never registered.
3. **Persist + register** — the skill is saved to a per-tenant `JsonFileSkillStore` and registered into
   the tool registry as `skill.<name>`, so the worker can retrieve and invoke it on later runs.

## Enable it

Off by default. Turn it on per-run or globally:

```bash
# CLI: learn a skill from this run (also loads previously-learned skills)
riptide run "summarize this text: ..." --offline --learn-skills

# list the skills the agent has authored
riptide skills

# globally (server / service): RIPTIDE_ENABLE_SKILLS=1 loads + forges skills
RIPTIDE_ENABLE_SKILLS=1 riptide serve
```

In code:

```python
from riptide_watergraph.service import run_task

result = run_task("draft a release note for v1.2", learn_skills=True)
print(result.learned_skills)   # e.g. ["skill.draft_release_note"]
```

## The seam (swappable, "like water")

| Interface | Default | Purpose |
|-----------|---------|---------|
| `SkillSynthesizer` | `LLMSkillSynthesizer` | distill a `Skill` from a `Trajectory` |
| `SkillStore` | `JsonFileSkillStore` | persist learned skills (per-tenant, under `DATA_DIR`) |
| `skill_to_spec` | — | bind a `Skill` into an invokable `ToolSpec` |
| `verify_skill` | — | structural + smoke-test guard before registration |

All live in `riptide_watergraph.skills` and are exported from the top-level package.

## Safety

- **No code execution** — a skill is a prompt template, not a program. (Code-backed skills behind
  `RIPTIDE_ENABLE_EXEC` are a planned follow-up.)
- **Verified before registration** — malformed or raising skills are dropped.
- **Per-tenant** — learned skills never leak across tenants (`DATA_DIR/tenants/<id>/skills`).
- **Side-effecting skills** still route through the HITL approval gate like any side-effecting tool.

## Roadmap context

SkillForge is track 1 of the AGI-direction roadmap. Next: a knowledge-graph semantic memory + a
consolidation "sleep" cycle, then deliberate reasoning (search + debate + verifier), metacognition,
self-improvement, and autonomy.
