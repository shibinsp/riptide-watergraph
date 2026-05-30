"""Memory interface — the model-agnostic long-term memory + self-learning seam.

Stage 1 ships ``InMemoryMemory`` (pure-Python hybrid ranking). ``reflect()`` is the
hook for the Stage-2 self-learning loop: distill successful/failed trajectories into
retrievable lessons. In Stage 1 it is a no-op stub.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class MemoryRecord(BaseModel):
    """One unit stored in memory (an episode, fact, or distilled lesson)."""

    id: str
    text: str
    metadata: dict = Field(default_factory=dict)
    embedding: list[float] | None = None


class RetrievedItem(BaseModel):
    """A record returned from retrieval, with its fused relevance score."""

    record: MemoryRecord
    score: float


class Memory(ABC):
    """Long-term memory with hybrid retrieval and a reflection hook."""

    @abstractmethod
    async def write(self, records: list[MemoryRecord]) -> list[str]:
        """Persist records; return their ids."""

    @abstractmethod
    async def retrieve(
        self,
        query: str,
        *,
        k: int = 10,
        query_embedding: list[float] | None = None,
    ) -> list[RetrievedItem]:
        """Hybrid (lexical + optional dense) retrieval of the top-k records."""

    @abstractmethod
    async def reflect(self, session_id: str) -> list[MemoryRecord]:
        """Consolidate a session into distilled lessons (self-learning loop).

        Stage-1 stub returns ``[]``. Stage 2 implements the Reflexion/ReasoningBank
        pattern: judge the trajectory, write generalizable lessons to memory.
        """
