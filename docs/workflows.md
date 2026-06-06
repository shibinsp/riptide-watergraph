# Workflows

The Studio's **Workflows** view is a drag-and-drop canvas (AutoGen-Studio "Team Builder" style) for
composing a multi-agent workflow, then running it — with **zero graph-engine changes**.

## The mapping

- A **node** is a step assigned to a **role** (an instruction + a role from the catalog).
- An **edge** is a **dependency**.
- The canvas is a **DAG run as a swarm**: independent nodes run in parallel waves, dependent nodes run
  after their upstreams, and results are shared through the blackboard.

A tiny `StaticPlanComposer` replays the hand-drawn graph: node → subtask, role-per-node, edge →
dependency. The existing orchestrator honors a composer-supplied plan, so the user's graph runs for real.

## Run-level controls

Model and temperature are **run-level** controls on the canvas toolbar (the swarm worker uses one global
`worker_model`/`sampling`). Per-node tool scope comes from the chosen role. True per-node model/tool
overrides are a future engine change.

## Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/workflows` · `POST /api/workflows` | list / save (upsert) named workflows |
| `GET /api/workflows/{name}` · `DELETE /api/workflows/{name}` | load / delete |
| `POST /api/workflows/run` | run a spec → `RunResult` |
| `GET /api/workflows/run/stream` | run with a live SSE node trace |

A cycle, duplicate id, dangling edge, or empty graph is rejected with HTTP 422.

## Library use

```python
from riptide_watergraph.workflows import WorkflowSpec, WorkflowNode, WorkflowEdge
from riptide_watergraph.service import run_workflow

spec = WorkflowSpec(
    name="research-then-summarize",
    nodes=[WorkflowNode(id="a", role="researcher", subtask="research water"),
           WorkflowNode(id="b", role="scribe", subtask="summarize the findings")],
    edges=[WorkflowEdge(source="a", target="b")],
)
result = run_workflow(spec, offline=True)
print(result.mode, result.results)
```
