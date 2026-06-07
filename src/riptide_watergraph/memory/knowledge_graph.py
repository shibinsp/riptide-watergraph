"""A small, pure-Python knowledge graph of semantic ``Triple`` facts.

Facts are merged by identity (case-insensitive subject/predicate/object), accumulating a
``weight`` each time a fact recurs — so frequently-seen knowledge ranks higher. The graph
persists to JSON and can render facts about an entity (for recall) or convert to SEMANTIC
``MemoryRecord``s (so the existing recall node surfaces them at runtime).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from ..interfaces.knowledge import Triple
from ..interfaces.memory import MemoryRecord
from .types import fact_record

__all__ = ["KnowledgeGraph"]


class KnowledgeGraph:
    """An index of semantic triples with merge-on-add, query, and persistence."""

    def __init__(self, triples: Iterable[Triple] | None = None) -> None:
        self._by_key: dict[tuple[str, str, str], Triple] = {}
        if triples:
            self.add_many(triples)

    def add(self, triple: Triple) -> None:
        existing = self._by_key.get(triple.key())
        if existing is None:
            self._by_key[triple.key()] = triple.model_copy()
        else:
            existing.weight += triple.weight
            if not existing.source and triple.source:
                existing.source = triple.source

    def add_many(self, triples: Iterable[Triple]) -> None:
        for t in triples:
            self.add(t)

    @property
    def triples(self) -> list[Triple]:
        return list(self._by_key.values())

    def entities(self) -> list[str]:
        names: set[str] = set()
        for t in self._by_key.values():
            names.add(t.subject)
            names.add(t.object)
        return sorted(names)

    def neighbors(self, entity: str) -> list[Triple]:
        e = entity.lower()
        return [t for t in self._by_key.values()
                if t.subject.lower() == e or t.object.lower() == e]

    def facts_about(self, entity: str, *, limit: int = 10) -> list[str]:
        ranked = sorted(self.neighbors(entity), key=lambda t: t.weight, reverse=True)
        return [t.as_text() for t in ranked[:limit]]

    def to_records(self) -> list[MemoryRecord]:
        return [fact_record(t.as_text(), source=t.source) for t in self._by_key.values()]

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps([t.model_dump() for t in self._by_key.values()], indent=2),
                     encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "KnowledgeGraph":
        p = Path(path)
        if not p.exists():
            return cls()
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        return cls(Triple(**item) for item in raw)

    def __len__(self) -> int:
        return len(self._by_key)
