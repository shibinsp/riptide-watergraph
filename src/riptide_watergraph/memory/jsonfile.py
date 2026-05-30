"""Persistent JSON-file memory backend (Stage-2 default).

Unlike ``InMemoryMemory`` (per-process), this persists records to disk so lessons
accumulate across separate runs — which is what makes the self-learning loop
observable. Retrieval reuses the same BM25+RRF hybrid ranker.

Memory hygiene: ``write`` dedupes by record id (content-hashed lesson ids collapse
duplicates), and the store is capped to the most recent ``max_records`` to bound
growth and retrieval pollution. pgvector remains the named seam for scale.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..interfaces.memory import Memory, MemoryRecord, RetrievedItem
from .ranking import hybrid_rank


class JsonFileMemory(Memory):
    """A disk-backed Memory using BM25+RRF hybrid ranking."""

    def __init__(self, path: str | Path, *, max_records: int = 1000) -> None:
        self.path = Path(path)
        self.max_records = max_records
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
        for r in records:
            self._records[r.id] = r  # dedupe by id
        # Cap to most-recent insertions (dict preserves insertion order).
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
        return hybrid_rank(
            query,
            list(self._records.values()),
            query_embedding=query_embedding,
            k=k,
        )

    async def reflect(self, session_id: str) -> list[MemoryRecord]:
        # Reflection is driven by a Reflector in the graph's reflect node; the storage
        # backend itself has no reflection policy. (stub)
        return []

    def __len__(self) -> int:
        return len(self._records)
