# Quickstart

Everything here runs **offline** with the deterministic `DemoGateway` — no API key required.

## CLI

```bash
riptide run "What is 21 * 2?" --offline
riptide run "save a note about water" --offline --auto-approve
riptide eval --offline                  # the behavioral regression gate (4/4 = 100%)
riptide costs                           # per-tenant usage dashboard
```

## Library

Drive the full graph as a library — build the swappable layers, then `invoke`:

```python
from riptide_watergraph import (
    build_graph, default_registry, InMemoryMemory,
    HeuristicSwarmComposer, default_guardrails,
)
from riptide_watergraph.gateway import DemoGateway

graph = build_graph(
    gateway=DemoGateway(),
    registry=default_registry(),
    composer=HeuristicSwarmComposer(model="demo"),
    memory=InMemoryMemory(),
    guardrails=default_guardrails(),
    model="demo",
)
state = graph.invoke({"task": "research water then summarize"},
                     {"configurable": {"thread_id": "t1"}})
print(state["final_answer"])
```

See [`examples/quickstart.py`](https://github.com/shibinsp/riptide-watergraph/blob/main/examples/quickstart.py)
and [`examples/custom_tool.py`](https://github.com/shibinsp/riptide-watergraph/blob/main/examples/custom_tool.py)
for runnable scripts.

## The service layer

`service.run_task` is the console-free entry point used by both the CLI and the HTTP server:

```python
from riptide_watergraph.service import run_task

result = run_task("compute 21 * 2 then write a one-line summary",
                  offline=True, critic=True)
print(result.final_answer, result.mode, result.verdicts)
```

## Launch the Studio

```bash
pip install "riptide-watergraph[server]"
riptide serve        # open http://127.0.0.1:8000/
```

Continue to [Like Water Studio](studio.md).

## Against a real model

```bash
pip install "riptide-watergraph[litellm]"
export OPENAI_API_KEY=sk-...                    # or ANTHROPIC_API_KEY
export RIPTIDE_WATERGRAPH_MODEL=gpt-4o-mini
riptide eval                                    # live
python examples/real_model_chat.py "What is the capital of France?"
```

More in [Evaluation](evaluation.md).
