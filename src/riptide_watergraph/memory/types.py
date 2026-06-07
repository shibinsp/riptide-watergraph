"""Memory type taxonomy (CoALA-style) used to tag stored records.

- ``WORKING``    — transient context for the current task (not persisted long-term).
- ``EPISODIC``   — concrete past events / trajectories.
- ``SEMANTIC``   — distilled facts.
- ``PROCEDURAL`` — reusable strategies / lessons (what the self-learning loop writes).

The split is an engineering structure, not a claim of cognitive fidelity. Records carry
their type in ``MemoryRecord.metadata['type']``.
"""

from __future__ import annotations

import hashlib
from enum import Enum

from ..interfaces.memory import MemoryRecord


class MemoryType(str, Enum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


def lesson_record(
    text: str,
    *,
    task: str = "",
    success: bool | None = None,
    tags: list[str] | None = None,
) -> MemoryRecord:
    """Build a PROCEDURAL memory record (a distilled lesson).

    The id is a content hash so identical lessons dedupe instead of multiplying —
    basic memory hygiene against retrieval pollution.
    """
    digest = hashlib.sha1(text.strip().lower().encode("utf-8")).hexdigest()[:12]
    return MemoryRecord(
        id=f"procedural-{digest}",
        text=text.strip(),
        metadata={
            "type": MemoryType.PROCEDURAL.value,
            "task": task,
            "success": success,
            "tags": tags or [],
        },
    )


def fact_record(text: str, *, source: str = "", tags: list[str] | None = None) -> MemoryRecord:
    """Build a SEMANTIC memory record (a distilled fact, e.g. from the knowledge graph).

    Like ``lesson_record``, the id is a content hash so identical facts dedupe instead of
    accumulating. Semantic records are recalled into prompts alongside procedural lessons.
    """
    digest = hashlib.sha1(text.strip().lower().encode("utf-8")).hexdigest()[:12]
    return MemoryRecord(
        id=f"semantic-{digest}",
        text=text.strip(),
        metadata={
            "type": MemoryType.SEMANTIC.value,
            "source": source,
            "tags": tags or [],
        },
    )
