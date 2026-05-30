"""Persistent JsonFileMemory: write, retrieve, persist across instances, dedupe, cap."""

from __future__ import annotations

from riptide_watergraph.memory import JsonFileMemory
from riptide_watergraph.memory.types import lesson_record
from riptide_watergraph.interfaces.memory import MemoryRecord


async def test_persists_across_instances(tmp_path):
    path = tmp_path / "mem.json"
    mem = JsonFileMemory(path)
    await mem.write(
        [
            MemoryRecord(id="a", text="rivers carry clear water downstream"),
            MemoryRecord(id="b", text="granite mountains and snow"),
        ]
    )
    # A fresh instance loads what was written.
    reloaded = JsonFileMemory(path)
    assert len(reloaded) == 2
    hits = await reloaded.retrieve("water", k=1)
    assert hits and hits[0].record.id == "a"


async def test_lesson_dedupe_by_content(tmp_path):
    path = tmp_path / "mem.json"
    mem = JsonFileMemory(path)
    # Same lesson text -> same content-hashed id -> stored once.
    await mem.write([lesson_record("use calculator with an expression field")])
    await mem.write([lesson_record("use calculator with an expression field")])
    assert len(mem) == 1


async def test_cap_bounds_growth(tmp_path):
    path = tmp_path / "mem.json"
    mem = JsonFileMemory(path, max_records=5)
    for i in range(10):
        await mem.write([MemoryRecord(id=f"r{i}", text=f"record number {i}")])
    assert len(mem) == 5
