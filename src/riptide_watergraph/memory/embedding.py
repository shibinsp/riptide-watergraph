"""Embedding providers.

- ``HashingEmbedding``: deterministic, offline, no deps — hashes tokens into a fixed-dim
  bag-of-words vector. It makes the dense-retrieval pipeline real and testable, but it
  is lexical-flavored (no learned semantics). For genuine semantic recall use
  ``LiteLLMEmbedding`` (or any real embedder) — the dense path is unchanged.
- ``LiteLLMEmbedding``: real embeddings via LiteLLM (optional ``[litellm]`` extra).
"""

from __future__ import annotations

import hashlib
import math
import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class HashingEmbedding:
    """Deterministic hashed bag-of-words embedding (offline, dependency-free)."""

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dim
            for tok in _TOKEN_RE.findall(text.lower()):
                idx = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16) % self.dim
                vec[idx] += 1.0
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            vectors.append([x / norm for x in vec])
        return vectors


class LiteLLMEmbedding:
    """Real embeddings via LiteLLM (lazy import; needs the ``[litellm]`` extra)."""

    def __init__(self, model: str = "text-embedding-3-small") -> None:
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        import litellm

        resp = litellm.embedding(model=self.model, input=texts)
        data = resp["data"] if isinstance(resp, dict) else resp.data
        return [d["embedding"] if isinstance(d, dict) else d.embedding for d in data]
