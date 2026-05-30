"""Ranking core semantics (BM25 + Reciprocal Rank Fusion)."""

from __future__ import annotations

from riptide_watergraph.memory.ranking import bm25_score, rrf_fuse


def test_rrf_fuse_scores_and_order():
    fused = rrf_fuse([[1, 2, 3], [2, 1, 4]], 60)
    scores = dict(fused)
    assert abs(scores[1] - (1 / 61 + 1 / 62)) < 1e-12
    assert abs(scores[2] - (1 / 62 + 1 / 61)) < 1e-12
    ids = [d for d, _ in fused]
    assert ids[0] == 1 and ids[1] == 2  # tie broken by ascending id


def test_rrf_fuse_default_k():
    assert rrf_fuse([[7, 8]]) == rrf_fuse([[7, 8]], 60)


def test_bm25_monotonic_on_term_frequency():
    scores = bm25_score(["water"], [["water", "water"], ["air"]])
    assert scores[0] > scores[1]


def test_bm25_empty_corpus():
    assert bm25_score(["water"], []) == []


def test_bm25_rewards_rarer_terms():
    docs = [["rare", "common"], ["common"], ["common"]]
    rare = bm25_score(["rare"], docs)
    common = bm25_score(["common"], docs)
    assert rare[0] > common[0]
