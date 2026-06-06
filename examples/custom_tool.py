"""Register a custom tool and a custom gateway, then run a task through the graph.

Shows two swappable seams at once: a ``ToolSpec`` (the tool) and a ``ModelGateway`` (a
tiny scripted model that decides to call it). Offline, no API key.

Run: python examples/custom_tool.py
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from riptide_watergraph import (
    HeuristicSwarmComposer,
    build_graph,
    default_registry,
)
from riptide_watergraph.interfaces.gateway import CompletionResult, Message, ModelGateway
from riptide_watergraph.interfaces.tools import ToolSpec


def shout(text: str) -> str:
    """A custom read-only tool: upper-case with emphasis."""
    return text.upper() + "!"


SHOUT_SPEC = ToolSpec(
    name="shout",
    description="Shout the given text (upper-case, emphatic).",
    json_schema={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    },
    side_effecting=False,
    handler=shout,
)


class ScriptedGateway(ModelGateway):
    """Minimal gateway: plan one subtask, call ``shout``, then finalize."""

    async def complete(self, *, model: str, messages: list[Message],
                       tools: list[dict[str, Any]] | None = None, **kwargs: Any
                       ) -> CompletionResult:
        system = next((m.content or "" for m in messages if m.role == "system"), "")
        if "planning orchestrator" in system:
            return CompletionResult(content=json.dumps(["shout the greeting"]))
        if "You are a worker" in system:
            return CompletionResult(tool_calls=[{
                "id": "c1", "type": "function",
                "function": {"name": "shout", "arguments": json.dumps({"text": "hello"})},
            }])
        return CompletionResult(content="done")

    async def stream(self, *, model: str, messages: list[Message], **kwargs: Any
                    ) -> AsyncIterator[str]:
        yield "done"


def main() -> None:
    registry = default_registry()
    registry.register(SHOUT_SPEC)

    graph = build_graph(
        gateway=ScriptedGateway(),
        registry=registry,
        composer=HeuristicSwarmComposer(model="demo"),
        model="demo",
    )
    state = graph.invoke({"task": "greet loudly"}, {"configurable": {"thread_id": "ct"}})
    print("final answer:", state.get("final_answer"))
    for result in state.get("results", []):
        print(f"  - {result['subtask']} -> {result['output']}")


if __name__ == "__main__":
    main()
