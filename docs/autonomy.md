# Autonomy

Added in **v0.19.0** — the final track of the AGI-direction roadmap.

Everything else answers a task you give it. **Autonomy** lets the agent pursue a high-level *mission*:
it proposes its own subgoals, executes them, journals the results, and proposes follow-ups (an
auto-curriculum) — **always bounded** by a hard step cap and the tenant budget. Autonomy never runs away.

```
mission ──▶ propose subgoals ──▶ execute each (full graph) ──▶ journal result ──▶ refill queue (curriculum)
            (TemplateGoalProposer /                            (persistent,         when it drains, until
             LLMGoalProposer)                                   per-tenant)          max_steps / budget
```

## Safety bounds

- **Hard step cap** — `--max-steps` (default 3); the loop never executes more goals than this.
- **Budget** — each goal runs through `run_task`, so the per-tenant spend ceiling (`TENANT_BUDGET_USD`)
  stops the run at the boundary, and every step is cost-tracked.
- **Guardrails + HITL** — goals execute through the normal graph, so input/output guardrails apply and
  side-effecting tools still route through approval.
- **Per-tenant journal** — the record of autonomous work never leaks across tenants.

## CLI

```bash
riptide auto "research the water cycle and summarize the key facts" --max-steps 3 --offline
#  autonomous run: 3 step(s) for mission: research the water cycle and summarize the key facts
#    1. Break down and start: research the water cycle ...
#       -> ...
#    2. Make concrete progress on: ...
#    3. Refine and extend the work on: ...
```

## In code

```python
from riptide_watergraph.service import run_autonomous_mission

report = run_autonomous_mission("draft a v1 plan for feature X", max_steps=4)
for entry in report.entries:
    print(entry.goal, "->", entry.result)
```

Or drive the loop directly with your own executor + proposer:

```python
from riptide_watergraph.autonomy import run_autonomous, TemplateGoalProposer, Journal

report = run_autonomous(
    "mission text",
    executor=lambda goal: my_agent(goal),      # how one goal is carried out
    proposer=TemplateGoalProposer(),
    journal=Journal("data/journal.json"),
    max_steps=3,
)
```

## The seam (swappable)

| Interface | Default | Purpose |
|-----------|---------|---------|
| `GoalProposer` | `TemplateGoalProposer` (offline) / `LLMGoalProposer` | propose the next subgoals (the curriculum) |
| `Journal` | JSON, per-tenant | append-only record of completed goals + results |
| `run_autonomous(...)` | — | the bounded loop: propose → execute → journal → refill |

Offline, the deterministic `TemplateGoalProposer` makes the whole loop run without a key.

## Roadmap context

This completes the AGI-direction roadmap's cognitive-scaffolding tracks:
[SkillForge](skills.md) → [cognitive memory](cognitive-memory.md) →
[deliberate reasoning](deliberation.md) → [self-improvement](self-improvement.md) → **autonomy**. The
remaining roadmap items are the experimental research seams (multimodal perception, a Gym-like
environment, reward/RL) — larger, optional, and flagged as research.
