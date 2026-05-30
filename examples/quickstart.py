"""Quickstart: drive riptide-watergraph as a library (offline, no API key).

Run: python examples/quickstart.py
"""

from __future__ import annotations

from riptide_watergraph import (
    DemoGateway,
    HeuristicSwarmComposer,
    InMemoryMemory,
    build_graph,
    default_guardrails,
    default_registry,
)
from riptide_watergraph.memory.reflection import LLMReflector


def main() -> None:
    gateway = DemoGateway()  # deterministic, offline; swap for LiteLLMGateway for real
    graph = build_graph(
        gateway=gateway,
        registry=default_registry(),
        composer=HeuristicSwarmComposer(model="demo"),
        model="demo",
        memory=InMemoryMemory(),
        reflector=LLMReflector(gateway, model="demo"),
        guardrails=default_guardrails(),
    )

    state = graph.invoke(
        {"task": "compute 21 * 2", "session_id": "demo", "tenant_id": "default"},
        {"configurable": {"thread_id": "demo"}},
    )

    print("final answer:", state.get("final_answer"))
    for result in state.get("results", []):
        print(f"  - {result['subtask']} -> {result['output']}")


if __name__ == "__main__":
    main()
