"""Phase B: embeddings make dense retrieval real; reranker reorders candidates."""

from __future__ import annotations

import math

from riptide_watergraph.interfaces.memory import MemoryRecord, RetrievedItem
from riptide_watergraph.memory import HashingEmbedding, LexicalOverlapReranker
from riptide_watergraph.memory.ranking import hybrid_rank


def test_hashing_embedding_deterministic_and_normalized():
    emb = HashingEmbedding(dim=64)
    a1, a2, b = emb.embed(["water flows", "water flows", "granite rock"])
    assert a1 == a2  # deterministic
    assert a1 != b
    assert abs(math.sqrt(sum(x * x for x in a1)) - 1.0) < 1e-9  # L2-normalized


def test_dense_signal_changes_ranking():
    # None of the records share a lexical token with the query "gamma".
    a = MemoryRecord(id="A", text="alpha", embedding=[0.0, 1.0])
    b = MemoryRecord(id="B", text="beta", embedding=[1.0, 0.0])
    c = MemoryRecord(id="C", text="gamma", embedding=[0.0, 1.0])  # lexical match
    records = [a, b, c]

    lexical = hybrid_rank("gamma", records, k=3)
    assert lexical[0].record.id == "C"  # only lexical match leads
    assert lexical[-1].record.id == "B"  # B is last lexically

    # With a query embedding aligned to B, the dense signal lifts B to the top.
    hybrid = hybrid_rank("gamma", records, query_embedding=[1.0, 0.0], k=3)
    assert hybrid[0].record.id == "B"


def test_reranker_reorders_by_overlap():
    items = [
        RetrievedItem(record=MemoryRecord(id="lo", text="totally unrelated"), score=9.0),
        RetrievedItem(
            record=MemoryRecord(id="hi", text="count the words carefully"), score=0.1
        ),
    ]
    out = LexicalOverlapReranker().rerank("count the words", items, k=2)
    assert out[0].record.id == "hi"  # higher query overlap wins despite lower score
