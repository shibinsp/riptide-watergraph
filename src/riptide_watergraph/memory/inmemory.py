"""In-process memory backend (Stage-1 default).

Keeps records in a list and ranks them with the pure-Python hybrid ranker. No external
vector DB is required to run the skeleton; pgvector is the named production seam
(``pip install riptide-watergraph[pgvector]``) for Stage 2.
"""

from __future__ import annotations

from ..interfaces.memory import Memory, MemoryRecord, RetrievedItem
from .ranking import hybrid_rank


class InMemoryMemory(Memory):
    """A list-backed Memory using BM25+RRF hybrid ranking."""

    def __init__(self) -> None:
        self._records: dict[str, MemoryRecord] = {}

    async def write(self, records: list[MemoryRecord]) -> list[str]:
        for r in records:
            self._records[r.id] = r
        return [r.id for r in records]

    async def retrieve(
        self,
        query: str,
        *,
        k: int = 10,
        query_embedding: list[float] | None = None,
    ) -> list[RetrievedItem]:
        return hybrid_rank(
            query,
            list(self._records.values()),
            query_embedding=query_embedding,
            k=k,
        )

    async def reflect(self, session_id: str) -> list[MemoryRecord]:
        # Stage-1 stub. Stage 2 distills trajectories into lessons here.
        return []
