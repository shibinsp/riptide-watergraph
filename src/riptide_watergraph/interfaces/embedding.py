"""Embedding provider seam — turns text into dense vectors for hybrid retrieval."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Anything that can embed a batch of texts into fixed-length vectors."""

    def embed(self, texts: list[str]) -> list[list[float]]: ...
