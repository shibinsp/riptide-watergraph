"""Track 4: pgvector backend.

The vector-literal helper is unit-tested offline. The full backend needs Postgres +
pgvector, so its integration test is skipped unless ``RIPTIDE_TEST_PG_DSN`` is set (and
psycopg installed) — CI skips it.
"""

from __future__ import annotations

import os
import sys
import types

import pytest

from riptide_watergraph.memory.pgvector import PgVectorMemory, vector_literal


def test_vector_literal_format():
    assert vector_literal([1.0, 2.5, -3.0]) == "[1.0,2.5,-3.0]"
    assert vector_literal([]) == "[]"


def test_package_imports_without_psycopg():
    # Importing the module/class must not require psycopg (lazy import in methods).
    assert PgVectorMemory is not None


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self):
        return _FakeCursor(self._rows)

    def commit(self):
        self.commits += 1


@pytest.fixture
def fake_psycopg(monkeypatch):
    # retrieve() rows: one dict metadata + one JSON-string metadata (both code paths).
    rows = [("l1", "lesson one", {"k": "v"}, 0.91),
            ("l2", "lesson two", '{"k2": "v2"}', 0.83)]
    mod = types.ModuleType("psycopg")
    mod.connect = lambda dsn: _FakeConn(rows)
    monkeypatch.setitem(sys.modules, "psycopg", mod)
    return rows


async def test_pgvector_write_and_retrieve_mocked(fake_psycopg):
    from riptide_watergraph.interfaces.memory import MemoryRecord
    from riptide_watergraph.memory import HashingEmbedding

    mem = PgVectorMemory("postgresql://fake", HashingEmbedding(dim=8), dim=8)  # _ensure_schema
    ids = await mem.write([MemoryRecord(id="l1", text="lesson one", metadata={"k": "v"})])
    assert ids == ["l1"]
    items = await mem.retrieve("query", k=2)
    assert [it.record.id for it in items] == ["l1", "l2"]
    assert items[0].record.metadata == {"k": "v"}     # dict metadata kept
    assert items[1].record.metadata == {"k2": "v2"}   # JSON-string metadata parsed
    assert items[0].score == pytest.approx(0.91)
    assert await mem.reflect("s") == []


@pytest.mark.skipif(
    not os.getenv("RIPTIDE_TEST_PG_DSN"),
    reason="set RIPTIDE_TEST_PG_DSN (and install psycopg + pgvector) to run",
)
def test_pgvector_roundtrip():
    import asyncio

    from riptide_watergraph.interfaces.memory import MemoryRecord
    from riptide_watergraph.memory import HashingEmbedding

    mem = PgVectorMemory(os.environ["RIPTIDE_TEST_PG_DSN"], HashingEmbedding(dim=256), dim=256)
    asyncio.run(mem.write([
        MemoryRecord(id="a", text="rivers carry clear water"),
        MemoryRecord(id="b", text="granite mountains and snow"),
    ]))
    hits = asyncio.run(mem.retrieve("water", k=1))
    assert hits and hits[0].record.id in {"a", "b"}
