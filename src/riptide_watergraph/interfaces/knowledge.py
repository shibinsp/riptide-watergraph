"""Knowledge interface — the semantic-memory (knowledge-graph) seam.

Where procedural memory stores *lessons* and episodic memory stores *events*, semantic
memory stores **facts** as ``(subject, predicate, object)`` triples. A :class:`TripleExtractor`
turns text (e.g. an episodic trajectory) into triples; a knowledge graph indexes them so
facts about an entity can be recalled by traversal, not just by lexical match.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel

__all__ = ["Triple", "TripleExtractor"]


class Triple(BaseModel):
    """A semantic fact: ``subject predicate object`` (with provenance + weight)."""

    subject: str
    predicate: str
    object: str
    source: str = ""  # where the fact came from (e.g. a session id / task)
    weight: float = 1.0  # accumulates when the same fact is seen repeatedly

    def key(self) -> tuple[str, str, str]:
        """Identity of the fact (case-insensitive), for dedup/merge."""
        return (self.subject.lower(), self.predicate.lower(), self.object.lower())

    def as_text(self) -> str:
        return f"{self.subject} {self.predicate} {self.object}"


class TripleExtractor(ABC):
    """Extracts ``(subject, predicate, object)`` triples from a span of text."""

    @abstractmethod
    async def extract(self, text: str) -> list[Triple]:
        """Return zero or more semantic triples found in ``text``."""
