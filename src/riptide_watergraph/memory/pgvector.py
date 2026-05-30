"""pgvector-backed memory — the production memory seam for scale.

A drop-in for ``JsonFileMemory`` that stores records in Postgres and does dense vector
similarity search with the pgvector extension. Needs the ``[pgvector]`` extra
(``psycopg``) and a Postgres database with ``CREATE EXTENSION vector`` available.

``psycopg`` is imported lazily inside methods, so importing this module (and the package)
never requires it — only constructing/using ``PgVectorMemory`` does.
"""

from __future__ import annotations

import json

from ..interfaces.embedding import EmbeddingProvider
from ..interfaces.memory import Memory, MemoryRecord, RetrievedItem


def vector_literal(vec: list[float]) -> str:
    """Render a float vector as a pgvector literal, e.g. ``[0.1,0.2,0.3]``."""
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


class PgVectorMemory(Memory):
    """Postgres + pgvector memory backend (dense cosine retrieval)."""

    def __init__(
        self,
        dsn: str,
        embedding: EmbeddingProvider,
        *,
        table: str = "riptide_memory",
        dim: int = 256,
    ) -> None:
        self.dsn = dsn
        self.embedding = embedding
        self.table = table
        self.dim = dim
        self._ensure_schema()

    def _connect(self):
        import psycopg  # lazy: only needed when actually using the backend

        return psycopg.connect(self.dsn)

    def _ensure_schema(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS {self.table} ("
                "id text PRIMARY KEY, text text NOT NULL, "
                "metadata jsonb DEFAULT '{}'::jsonb, "
                f"embedding vector({self.dim}))"
            )
            conn.commit()

    async def write(self, records: list[MemoryRecord]) -> list[str]:
        missing = [r for r in records if r.embedding is None]
        if missing:
            for rec, vec in zip(missing, self.embedding.embed([r.text for r in missing])):
                rec.embedding = vec
        with self._connect() as conn, conn.cursor() as cur:
            for r in records:
                cur.execute(
                    f"INSERT INTO {self.table} (id, text, metadata, embedding) "
                    "VALUES (%s, %s, %s::jsonb, %s::vector) "
                    "ON CONFLICT (id) DO UPDATE SET "
                    "text = EXCLUDED.text, metadata = EXCLUDED.metadata, "
                    "embedding = EXCLUDED.embedding",
                    (r.id, r.text, json.dumps(r.metadata), vector_literal(r.embedding or [])),
                )
            conn.commit()
        return [r.id for r in records]

    async def retrieve(
        self,
        query: str,
        *,
        k: int = 10,
        query_embedding: list[float] | None = None,
    ) -> list[RetrievedItem]:
        qe = query_embedding if query_embedding is not None else self.embedding.embed([query])[0]
        lit = vector_literal(qe)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT id, text, metadata, 1 - (embedding <=> %s::vector) AS score "
                f"FROM {self.table} ORDER BY embedding <=> %s::vector LIMIT %s",
                (lit, lit, k),
            )
            rows = cur.fetchall()
        items: list[RetrievedItem] = []
        for id_, text, metadata, score in rows:
            md = metadata if isinstance(metadata, dict) else json.loads(metadata or "{}")
            items.append(
                RetrievedItem(record=MemoryRecord(id=id_, text=text, metadata=md),
                              score=float(score))
            )
        return items

    async def reflect(self, session_id: str) -> list[MemoryRecord]:
        return []
