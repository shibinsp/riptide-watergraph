"""Reranker seam — reorder a candidate set by relevance to the query.

Research consistently finds reranking the single most impactful retrieval component:
cheap hybrid recall to get candidates, then a sharper rerank to order the top-k.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .memory import RetrievedItem


@runtime_checkable
class Reranker(Protocol):
    def rerank(
        self, query: str, items: list[RetrievedItem], *, k: int
    ) -> list[RetrievedItem]: ...
