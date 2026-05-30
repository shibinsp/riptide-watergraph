"""Hybrid retrieval ranking (pure Python).

Lexical (BM25) and optional dense (cosine) candidate lists are fused with Reciprocal
Rank Fusion. BM25 and RRF are implemented here directly; if this ever becomes a
profiled hot path at scale, swap these two functions for a native implementation
behind the same signatures — the rest of the framework is unaffected.
"""

from __future__ import annotations

import math
import re
from typing import Sequence

from ..interfaces.memory import MemoryRecord, RetrievedItem

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# RRF damping constant; 60 is the standard, robust default.
RRF_K = 60


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokenization."""
    return _TOKEN_RE.findall(text.lower())


def bm25_score(
    query_tokens: list[str],
    doc_tokens: list[list[str]],
    k1: float = 1.2,
    b: float = 0.75,
) -> list[float]:
    """Okapi BM25 scores for a query against tokenized docs (one score per doc).

    IDF is computed over exactly the documents passed in (self-contained corpus),
    which is what ranking an in-memory candidate set wants.
    """
    n_docs = len(doc_tokens)
    if n_docs == 0:
        return []

    doc_freq: dict[str, int] = {}
    for doc in doc_tokens:
        for tok in set(doc):
            doc_freq[tok] = doc_freq.get(tok, 0) + 1

    avgdl = sum(len(d) for d in doc_tokens) / n_docs
    query_terms = set(query_tokens)
    n = float(n_docs)

    scores: list[float] = []
    for doc in doc_tokens:
        dl = float(len(doc))
        tf: dict[str, int] = {}
        for tok in doc:
            tf[tok] = tf.get(tok, 0) + 1

        score = 0.0
        for term in query_terms:
            f = tf.get(term)
            if not f:
                continue
            df = float(doc_freq.get(term, 0))
            idf = math.log(((n - df + 0.5) / (df + 0.5)) + 1.0)
            denom = f + k1 * (1.0 - b + b * (dl / avgdl))
            score += idf * (f * (k1 + 1.0)) / denom
        scores.append(score)
    return scores


def rrf_fuse(ranked_lists: list[list[int]], k: int = RRF_K) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion -> (id, score) sorted by score desc, ties by id asc."""
    kf = float(k)
    scores: dict[int, float] = {}
    for lst in ranked_lists:
        for idx, doc_id in enumerate(lst):
            rank = idx + 1  # 1-based
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (kf + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


def _argsort_desc(values: Sequence[float]) -> list[int]:
    return sorted(range(len(values)), key=lambda i: values[i], reverse=True)


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def hybrid_rank(
    query: str,
    records: list[MemoryRecord],
    *,
    query_embedding: list[float] | None = None,
    k: int = 10,
) -> list[RetrievedItem]:
    """Rank ``records`` for ``query`` via BM25 + optional dense, fused with RRF."""
    if not records:
        return []

    # --- lexical candidate list (BM25) ---
    q_tok = tokenize(query)
    doc_tok = [tokenize(r.text) for r in records]
    bm25 = bm25_score(q_tok, doc_tok)
    lex_ranked = _argsort_desc(bm25)  # indices, best first

    ranked_lists: list[list[int]] = [lex_ranked]

    # --- optional dense candidate list (cosine) ---
    if query_embedding is not None:
        cos = [
            _cosine(query_embedding, r.embedding) if r.embedding else 0.0
            for r in records
        ]
        ranked_lists.append(_argsort_desc(cos))

    # --- fuse (RRF) ---
    fused = rrf_fuse(ranked_lists, RRF_K)  # [(idx, score)], sorted desc

    return [RetrievedItem(record=records[idx], score=score) for idx, score in fused[:k]]
