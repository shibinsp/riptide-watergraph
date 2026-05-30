"""Track 4: pgvector backend.

The vector-literal helper is unit-tested offline. The full backend needs Postgres +
pgvector, so its integration test is skipped unless ``RIPTIDE_TEST_PG_DSN`` is set (and
psycopg installed) — CI skips it.
"""

from __future__ import annotations

import os

import pytest

from riptide_watergraph.memory.pgvector import PgVectorMemory, vector_literal


def test_vector_literal_format():
    assert vector_literal([1.0, 2.5, -3.0]) == "[1.0,2.5,-3.0]"
    assert vector_literal([]) == "[]"


def test_package_imports_without_psycopg():
    # Importing the module/class must not require psycopg (lazy import in methods).
    assert PgVectorMemory is not None


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
