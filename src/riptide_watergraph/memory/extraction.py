"""Triple extractors — turn text into ``(subject, predicate, object)`` semantic facts.

``RuleTripleExtractor`` is deterministic and offline (pattern-based, no model), so the
knowledge-graph path is fully testable without an API key. ``LLMTripleExtractor`` asks a
model for higher-recall extraction and is used when a real gateway is available.
"""

from __future__ import annotations

import json
import re

from ..interfaces.gateway import Message, ModelGateway
from ..interfaces.knowledge import Triple, TripleExtractor

__all__ = ["RuleTripleExtractor", "LLMTripleExtractor"]

# Relation verbs the rule extractor recognizes (normalized to a canonical predicate).
_PREDICATES = {
    "is": "is", "are": "is", "was": "is", "were": "is",
    "has": "has", "have": "has",
    "uses": "uses", "use": "uses",
    "requires": "requires", "require": "requires", "needs": "requires", "need": "requires",
    "contains": "contains", "contain": "contains", "includes": "contains", "include": "contains",
    "produces": "produces", "produce": "produces", "causes": "causes", "cause": "causes",
}
_VERBS = "|".join(sorted(_PREDICATES, key=len, reverse=True))
_CLAUSE = re.compile(rf"^(.{{2,60}}?)\s+({_VERBS})\s+(.{{2,80}})$", re.IGNORECASE)
_SPLIT = re.compile(r"[.;\n|]+")


def _clean(span: str) -> str:
    return re.sub(r"\s+", " ", span).strip(" \t\"'`.,:-")


class RuleTripleExtractor(TripleExtractor):
    """Deterministic, offline extraction via simple subject-verb-object patterns."""

    async def extract(self, text: str) -> list[Triple]:
        triples: list[Triple] = []
        for clause in _SPLIT.split(text or ""):
            m = _CLAUSE.match(clause.strip())
            if not m:
                continue
            subj, verb, obj = _clean(m.group(1)), m.group(2).lower(), _clean(m.group(3))
            if subj and obj:
                triples.append(Triple(subject=subj, predicate=_PREDICATES[verb], object=obj))
        return triples


_SYSTEM = (
    "You are a knowledge-extraction module. Extract factual (subject, predicate, object) "
    "triples from the text. Reply ONLY as a JSON array: "
    '[{"subject": "...", "predicate": "...", "object": "..."}]. Use [] if there are none.'
)


class LLMTripleExtractor(TripleExtractor):
    """Higher-recall extraction via a ModelGateway (used when a real model is configured)."""

    def __init__(self, gateway: ModelGateway, *, model: str) -> None:
        self.gateway = gateway
        self.model = model

    async def extract(self, text: str) -> list[Triple]:
        result = await self.gateway.complete(
            model=self.model,
            messages=[Message(role="system", content=_SYSTEM),
                      Message(role="user", content=text)],
        )
        return _parse_triples(result.content)


def _parse_triples(content: str | None) -> list[Triple]:
    """Parse an LLM reply into triples; tolerant of code fences, skips malformed rows."""
    if not content:
        return []
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    out: list[Triple] = []
    for row in parsed:
        if isinstance(row, dict) and row.get("subject") and row.get("predicate") and row.get("object"):
            out.append(Triple(subject=str(row["subject"]), predicate=str(row["predicate"]),
                              object=str(row["object"])))
    return out
