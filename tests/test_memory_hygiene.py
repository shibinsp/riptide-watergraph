"""Phase B: consolidation/decay, episodic storage, and the lesson quality gate."""

from __future__ import annotations

import asyncio
import json

from langgraph.checkpoint.sqlite import SqliteSaver

from riptide_watergraph import InMemoryMemory, SingleAgentComposer, build_graph
from riptide_watergraph.interfaces.gateway import CompletionResult
from riptide_watergraph.interfaces.memory import MemoryRecord
from riptide_watergraph.interfaces.reflector import Trajectory
from riptide_watergraph.memory import JsonFileMemory, MemoryType
from riptide_watergraph.memory.reflection import LLMReflector
from riptide_watergraph.tools import default_registry

from .conftest import MockGateway


async def test_consolidate_merges_near_duplicate_embeddings(tmp_path):
    mem = JsonFileMemory(tmp_path / "m.json")
    await mem.write(
        [
            MemoryRecord(id="a", text="lesson one", embedding=[1.0, 0.0]),
            MemoryRecord(id="b", text="lesson two", embedding=[0.9999, 0.01]),
            MemoryRecord(id="c", text="unrelated", embedding=[0.0, 1.0]),
        ]
    )
    removed = mem.consolidate(sim_threshold=0.99)
    assert removed == 1
    assert len(mem) == 2


def test_consolidate_decays_old_failed_lessons(tmp_path):
    mem = JsonFileMemory(tmp_path / "m.json")
    recs = [
        MemoryRecord(id=f"f{i}", text=f"failed lesson {i}", metadata={"success": False, "ts": float(i)})
        for i in range(8)
    ]
    asyncio.run(mem.write(recs))
    removed = mem.consolidate(max_failed=3)
    assert len(mem) == 3  # only the 3 most-recent failed lessons survive
    assert removed == 5


async def test_reflector_non_json_stores_nothing():
    gw = MockGateway(lambda s, u: CompletionResult(content="just prose, not json"))
    reflector = LLMReflector(gw, model="mock")
    assert await reflector.reflect(Trajectory(task="t", success=True)) == []


def _responder(system: str, user: str) -> CompletionResult:
    if "reflection module" in system:
        return CompletionResult(
            content=json.dumps({"lesson": "call calculator with an expression", "tags": []})
        )
    if "planning orchestrator" in system:
        return CompletionResult(content=json.dumps(["compute 2 + 2"]))
    if "You are a worker" in system:
        return CompletionResult(content="ok")
    return CompletionResult(content="final")


def test_reflect_writes_episodic_and_recall_excludes_it():
    mem = InMemoryMemory()
    gw = MockGateway(_responder)
    with SqliteSaver.from_conn_string(":memory:") as cp:
        graph = build_graph(
            gateway=gw,
            registry=default_registry(),
            composer=SingleAgentComposer(model="mock"),
            model="mock",
            checkpointer=cp,
            memory=mem,
            reflector=LLMReflector(gw, model="mock"),
        )
        graph.invoke(
            {"task": "compute 2 + 2", "session_id": "r1"},
            {"configurable": {"thread_id": "r1"}},
        )
        # An episodic trajectory record was stored alongside the distilled lesson.
        items = asyncio.run(mem.retrieve("compute 2 + 2", k=10))
        assert any(
            it.record.metadata.get("type") == MemoryType.EPISODIC.value for it in items
        )

        # A second run recalls lessons but never the episodic trajectory.
        s2 = graph.invoke(
            {"task": "compute 2 + 2", "session_id": "r2"},
            {"configurable": {"thread_id": "r2"}},
        )
        assert s2.get("recalled_lessons")
        assert all("outcome:" not in ln for ln in s2["recalled_lessons"])
