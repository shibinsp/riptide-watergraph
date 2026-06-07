"""A persistent, append-only journal of autonomous work (per-tenant)."""

from __future__ import annotations

import json
from pathlib import Path

from ..interfaces.autonomy import JournalEntry

__all__ = ["Journal"]


class Journal:
    """An append-only list of ``JournalEntry`` persisted to a JSON file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._entries: list[JournalEntry] = self._load()

    def _load(self) -> list[JournalEntry]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        return [JournalEntry(**item) for item in raw]

    def entries(self) -> list[JournalEntry]:
        return list(self._entries)

    def append(self, entry: JournalEntry) -> None:
        self._entries.append(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([e.model_dump() for e in self._entries], indent=2), encoding="utf-8"
        )

    def __len__(self) -> int:
        return len(self._entries)
