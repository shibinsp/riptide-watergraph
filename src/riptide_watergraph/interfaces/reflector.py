"""Reflector interface — the self-learning seam.

A Reflector turns a completed task **trajectory** into distilled, retrievable lessons
(procedural memory). This is the concrete realization of "improvement without
fine-tuning": store what worked / what failed, retrieve it on similar future tasks.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from .memory import MemoryRecord


class Trajectory(BaseModel):
    """A completed run, handed to the Reflector for distillation."""

    task: str
    plan: list[str] = Field(default_factory=list)
    results: list[dict] = Field(default_factory=list)
    success: bool = False
    metrics: dict = Field(default_factory=dict)
    session_id: str = ""


class Reflector(ABC):
    """Distills lessons from a trajectory."""

    @abstractmethod
    async def reflect(self, trajectory: Trajectory) -> list[MemoryRecord]:
        """Return zero or more lessons (procedural memory) to persist."""
