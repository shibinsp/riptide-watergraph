"""Rerankers applied to the fused candidate set before returning top-k."""

from __future__ import annotations

from ..interfaces.memory import RetrievedItem
from .ranking import tokenize


class LexicalOverlapReranker:
    """Deterministic, offline reranker: order by query/record token Jaccard overlap.

    A real deployment would swap in a cross-encoder (e.g. a MiniLM reranker or Cohere
    Rerank) behind this same interface; this keeps reranking testable without a model.
    """

    def rerank(
        self, query: str, items: list[RetrievedItem], *, k: int
    ) -> list[RetrievedItem]:
        q = set(tokenize(query))

        def overlap(item: RetrievedItem) -> float:
            d = set(tokenize(item.record.text))
            if not q or not d:
                return 0.0
            return len(q & d) / len(q | d)

        return sorted(items, key=overlap, reverse=True)[:k]
