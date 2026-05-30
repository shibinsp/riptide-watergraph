"""Persistent JSON-file memory backend (default for the CLI).

Unlike ``InMemoryMemory`` (per-process), this persists records to disk so lessons
accumulate across runs — which is what makes the self-learning loop observable.
Retrieval reuses the BM25 (+ optional dense) hybrid ranker and an optional reranker.

Memory hygiene: ``write`` dedupes by record id (content-hashed lesson ids collapse
duplicates) and caps to the most recent ``max_records``; ``consolidate()`` additionally
merges near-duplicate records by embedding similarity and decays old failed lessons so
the store stays clean rather than degrading over time.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from ..interfaces.embedding import EmbeddingProvider
from ..interfaces.memory import Memory, MemoryRecord, RetrievedItem
from ..interfaces.reranker import Reranker
from .ranking import _cosine, hybrid_rank


class JsonFileMemory(Memory):
    """A disk-backed Memory with hybrid ranking, optional dense + rerank, and hygiene."""

    def __init__(
        self,
        path: str | Path,
        *,
        max_records: int = 1000,
        embedding: EmbeddingProvider | None = None,
        reranker: Reranker | None = None,
    ) -> None:
        self.path = Path(path)
        self.max_records = max_records
        self.embedding = embedding
        self.reranker = reranker
        self._records: dict[str, MemoryRecord] = {}
        self._load()

    # --- persistence ---

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        for item in raw:
            rec = MemoryRecord(**item)
            self._records[rec.id] = rec

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = [r.model_dump() for r in self._records.values()]
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # --- Memory interface ---

    async def write(self, records: list[MemoryRecord]) -> list[str]:
        if self.embedding is not None:
            missing = [r for r in records if r.embedding is None]
            if missing:
                vecs = self.embedding.embed([r.text for r in missing])
                for rec, vec in zip(missing, vecs):
                    rec.embedding = vec
        for r in records:
            r.metadata.setdefault("ts", time.time())  # age for decay
            self._records[r.id] = r  # dedupe by id
        if len(self._records) > self.max_records:
            overflow = len(self._records) - self.max_records
            for key in list(self._records.keys())[:overflow]:
                del self._records[key]
        self._save()
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

    # --- hygiene ---

    def consolidate(self, *, sim_threshold: float = 0.97, max_failed: int = 5) -> int:
        """Merge near-duplicate records and decay old failed lessons. Returns #removed.

        Two records are near-duplicates if their embeddings' cosine >= ``sim_threshold``
        (or, lacking embeddings, their text matches); the first-seen is kept. Failed
        lessons beyond the ``max_failed`` most-recent are dropped.
        """
        records = list(self._records.values())
        kept: list[MemoryRecord] = []
        removed = 0
        for r in records:
            is_dup = False
            for kr in kept:
                if r.embedding and kr.embedding:
                    if _cosine(r.embedding, kr.embedding) >= sim_threshold:
                        is_dup = True
                        break
                elif r.text.strip().lower() == kr.text.strip().lower():
                    is_dup = True
                    break
            if is_dup:
                removed += 1
            else:
                kept.append(r)

        failed = [r for r in kept if r.metadata.get("success") is False]
        if len(failed) > max_failed:
            stale = sorted(failed, key=lambda r: r.metadata.get("ts", 0.0))[
                : len(failed) - max_failed
            ]
            stale_ids = {id(r) for r in stale}
            before = len(kept)
            kept = [r for r in kept if id(r) not in stale_ids]
            removed += before - len(kept)

        self._records = {r.id: r for r in kept}
        self._save()
        return removed

    def __len__(self) -> int:
        return len(self._records)
