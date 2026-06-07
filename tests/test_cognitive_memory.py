"""Cognitive memory v0.16.0: knowledge graph + triple extraction + consolidation sleep cycle."""

from __future__ import annotations

import asyncio
import json

import pytest

from riptide_watergraph.cli import main
from riptide_watergraph.config import get_settings
from riptide_watergraph.interfaces.gateway import CompletionResult
from riptide_watergraph.interfaces.knowledge import Triple
from riptide_watergraph.interfaces.memory import MemoryRecord
from riptide_watergraph.memory import (
    HashingEmbedding,
    JsonFileMemory,
    KnowledgeGraph,
    LexicalOverlapReranker,
    LLMTripleExtractor,
    RuleTripleExtractor,
    consolidate_memory,
)
from riptide_watergraph.memory.extraction import _parse_triples


def _run(coro):
    return asyncio.run(coro)


# --------------------------- rule extractor ---------------------------

def test_rule_extractor_finds_triples():
    ex = RuleTripleExtractor()
    triples = _run(ex.extract("Water is essential. The pump requires power; engines use fuel"))
    got = {(t.subject.lower(), t.predicate, t.object.lower()) for t in triples}
    assert ("water", "is", "essential") in got
    assert ("the pump", "requires", "power") in got
    assert ("engines", "uses", "fuel") in got


def test_rule_extractor_normalizes_synonyms_and_skips_nonmatches():
    ex = RuleTripleExtractor()
    triples = _run(ex.extract("Cats are animals"))
    assert triples[0].predicate == "is"  # "are" -> canonical "is"
    assert _run(ex.extract("just some words without a relation")) == []
    assert _run(ex.extract("")) == []


# --------------------------- LLM extractor ---------------------------

def test_llm_extractor_parses_array(make_gateway):
    payload = json.dumps([{"subject": "sun", "predicate": "produces", "object": "light"}])
    gw = make_gateway(lambda s, u: CompletionResult(content=payload))
    triples = _run(LLMTripleExtractor(gw, model="demo").extract("the sun"))
    assert len(triples) == 1 and triples[0].object == "light"


def test_parse_triples_variants():
    assert _parse_triples(None) == []
    assert _parse_triples("not json") == []
    assert _parse_triples(json.dumps({"a": 1})) == []  # not a list
    # malformed rows skipped; valid row + fenced block kept
    fenced = "```json\n" + json.dumps([
        {"subject": "x", "predicate": "is", "object": "y"},
        {"subject": "missing object"},
        "not a dict",
    ]) + "\n```"
    out = _parse_triples(fenced)
    assert len(out) == 1 and out[0].subject == "x"


# --------------------------- knowledge graph ---------------------------

def test_kg_merge_weight_and_source():
    kg = KnowledgeGraph()
    kg.add(Triple(subject="A", predicate="is", object="B"))
    kg.add(Triple(subject="a", predicate="IS", object="b", source="sess1"))  # same key
    assert len(kg) == 1
    t = kg.triples[0]
    assert t.weight == 2.0 and t.source == "sess1"  # weight accumulates, source backfilled


def test_kg_query_and_render():
    kg = KnowledgeGraph([
        Triple(subject="water", predicate="is", object="liquid", weight=3.0),
        Triple(subject="water", predicate="has", object="hydrogen"),
        Triple(subject="ice", predicate="is", object="solid"),
    ])
    assert set(kg.entities()) == {"water", "liquid", "hydrogen", "ice", "solid"}
    assert len(kg.neighbors("WATER")) == 2  # case-insensitive
    facts = kg.facts_about("water", limit=1)
    assert facts == ["water is liquid"]  # highest weight first
    recs = kg.to_records()
    assert all(r.metadata["type"] == "semantic" for r in recs)


def test_kg_persistence_roundtrip_and_recovery(tmp_path):
    kg = KnowledgeGraph([Triple(subject="a", predicate="is", object="b")])
    path = tmp_path / "kg" / "knowledge.json"
    kg.save(path)
    assert len(KnowledgeGraph.load(path)) == 1
    assert len(KnowledgeGraph.load(tmp_path / "missing.json")) == 0  # missing -> empty
    (tmp_path / "corrupt.json").write_text("{not json", encoding="utf-8")
    assert len(KnowledgeGraph.load(tmp_path / "corrupt.json")) == 0  # corrupt -> empty


# --------------------------- consolidation sleep cycle ---------------------------

@pytest.fixture
def memory(tmp_path):
    return JsonFileMemory(str(tmp_path / "mem.json"), embedding=HashingEmbedding(),
                          reranker=LexicalOverlapReranker())


def _episodic(rec_id, text, task="t"):
    return MemoryRecord(id=rec_id, text=text, metadata={"type": "episodic", "task": task})


def test_consolidate_promotes_episodic_to_semantic(memory, tmp_path):
    _run(memory.write([
        _episodic("e1", "Water is liquid. Ice is solid.", task="states of matter"),
        MemoryRecord(id="p1", text="some lesson", metadata={"type": "procedural"}),
    ]))
    report = consolidate_memory(memory, extractor=RuleTripleExtractor(),
                                kg_path=str(tmp_path / "kg.json"))
    assert report.episodic_scanned == 1  # the procedural record is skipped
    assert report.triples >= 2 and report.facts_written >= 2
    # semantic facts are now in memory (so the recall node surfaces them) with provenance
    semantic = [r for r in memory.all_records() if r.metadata.get("type") == "semantic"]
    assert any("water is liquid" in r.text.lower() for r in semantic)
    kg = KnowledgeGraph.load(str(tmp_path / "kg.json"))
    assert all(t.source == "states of matter" for t in kg.triples)  # stamped from the task


def test_consolidate_all_records_and_no_triples(memory, tmp_path):
    _run(memory.write([MemoryRecord(id="x", text="words with no relation",
                                    metadata={"type": "semantic"})]))
    report = consolidate_memory(memory, extractor=RuleTripleExtractor(),
                                kg_path=str(tmp_path / "kg.json"), episodic_only=False)
    assert report.episodic_scanned == 1  # episodic_only=False scans everything
    assert report.triples == 0 and report.facts_written == 0  # nothing extractable


# --------------------------- CLI ---------------------------

def test_cli_consolidate(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RIPTIDE_WATERGRAPH_DISABLE_TRACING", "1")
    settings = get_settings()
    mem = JsonFileMemory(settings.tenant_memory_path("default"), embedding=HashingEmbedding())
    _run(mem.write([_episodic("e1", "The cycle produces rain.")]))
    assert main(["consolidate", "--tenant", "default"]) == 0
    assert "consolidated" in capsys.readouterr().out
