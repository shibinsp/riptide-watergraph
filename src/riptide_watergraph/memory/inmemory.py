"""In-process memory backend.

Keeps records in a dict and ranks them with the pure-Python hybrid ranker. Optionally
embeds records (dense retrieval) and reranks the fused candidates. No external vector DB
required; pgvector is the named production seam for scale.
"""

from __future__ import annotations

from ..interfaces.embedding import EmbeddingProvider
from ..interfaces.memory import Memory, MemoryRecord, RetrievedItem
from ..interfaces.reranker import Reranker
from .ranking import hybrid_rank


class InMemoryMemory(Memory):
    """A dict-backed Memory using BM25 (+ optional dense) hybrid ranking and rerank."""

    def __init__(
        self,
        *,
        embedding: EmbeddingProvider | None = None,
        reranker: Reranker | None = None,
    ) -> None:
        self._records: dict[str, MemoryRecord] = {}
        self.embedding = embedding
        self.reranker = reranker

    async def write(self, records: list[MemoryRecord]) -> list[str]:
        if self.embedding is not None:
            missing = [r for r in records if r.embedding is None]
            if missing:
                vecs = self.embedding.embed([r.text for r in missing])
                for rec, vec in zip(missing, vecs):
                    rec.embedding = vec
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
        qe = query_embedding
        if qe is None and self.embedding is not None:
            qe = self.embedding.embed([query])[0]
        top_m = k * 3 if self.reranker is not None else k
        items = hybrid_rank(
            query, list(self._records.values()), query_embedding=qe, k=top_m
        )
        if self.reranker is not None:
            items = self.reranker.rerank(query, items, k=k)
        return items

    async def reflect(self, session_id: str) -> list[MemoryRecord]:
        return []  # reflection is driven by a Reflector in the graph's reflect node
