"""The consolidation "sleep" cycle — promote episodic memory into semantic knowledge.

Run periodically (``riptide consolidate``), this reads accumulated episodic records, extracts
``(subject, predicate, object)`` triples into a persistent knowledge graph, writes the facts
back as SEMANTIC records (which the existing ``recall`` node surfaces into prompts), and runs
the store's hygiene pass. It is the offline counterpart to in-run reflection: distilling many
experiences into durable, queryable knowledge.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from pydantic import BaseModel

from ..interfaces.knowledge import TripleExtractor
from .jsonfile import JsonFileMemory
from .knowledge_graph import KnowledgeGraph
from .types import MemoryType

__all__ = ["ConsolidationReport", "consolidate_memory"]


class ConsolidationReport(BaseModel):
    """What one sleep cycle did."""

    records_scanned: int = 0
    episodic_scanned: int = 0
    triples: int = 0
    facts_written: int = 0
    pruned: int = 0


def consolidate_memory(
    memory: JsonFileMemory,
    *,
    extractor: TripleExtractor,
    kg_path: str | Path,
    episodic_only: bool = True,
) -> ConsolidationReport:
    """Extract knowledge from memory into a graph + semantic facts. Returns a report."""
    records = memory.all_records()
    sources = [
        r for r in records
        if not episodic_only or r.metadata.get("type") == MemoryType.EPISODIC.value
    ]

    kg = KnowledgeGraph.load(kg_path)  # accumulate knowledge across cycles
    for rec in sources:
        triples = asyncio.run(extractor.extract(rec.text))
        for t in triples:
            if not t.source:
                t.source = rec.metadata.get("task") or rec.id
        kg.add_many(triples)
    kg.save(kg_path)

    facts = kg.to_records()
    if facts:
        asyncio.run(memory.write(facts))
    pruned = memory.consolidate()

    return ConsolidationReport(
        records_scanned=len(records),
        episodic_scanned=len(sources),
        triples=len(kg),
        facts_written=len(facts),
        pruned=pruned,
    )
