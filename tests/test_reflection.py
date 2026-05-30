"""LLMReflector distills a procedural lesson from a trajectory."""

from __future__ import annotations

import json

from riptide_watergraph.interfaces.gateway import CompletionResult
from riptide_watergraph.interfaces.reflector import Trajectory
from riptide_watergraph.memory.reflection import LLMReflector
from riptide_watergraph.memory.types import MemoryType

from .conftest import MockGateway


async def test_reflector_distills_lesson():
    def responder(system: str, user: str) -> CompletionResult:
        assert "reflection module" in system
        return CompletionResult(
            content=json.dumps(
                {"lesson": "Call calculator with an 'expression' field.",
                 "tags": ["calculator"]}
            )
        )

    reflector = LLMReflector(MockGateway(responder), model="mock")
    traj = Trajectory(
        task="compute 2 + 2",
        results=[{"subtask": "compute", "output": "invalid tool call"}],
        success=False,
        metrics={"failures": {"schema_violation": 1}},
    )
    lessons = await reflector.reflect(traj)
    assert len(lessons) == 1
    rec = lessons[0]
    assert "calculator" in rec.text.lower()
    assert rec.metadata["type"] == MemoryType.PROCEDURAL.value
    assert rec.metadata["success"] is False


async def test_reflector_rejects_non_json_reply():
    # Quality gate (Phase B): a non-JSON / lesson-less reply stores NO lesson,
    # rather than polluting memory with arbitrary prose.
    def responder(system: str, user: str) -> CompletionResult:
        return CompletionResult(content="Always validate tool arguments first.")

    reflector = LLMReflector(MockGateway(responder), model="mock")
    lessons = await reflector.reflect(Trajectory(task="t", success=True))
    assert lessons == []
