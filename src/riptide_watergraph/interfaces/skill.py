"""Skill interface — the self-authored-capability seam (SkillForge).

Where the :class:`~riptide_watergraph.interfaces.reflector.Reflector` distills a *lesson*
(text injected into prompts), a :class:`SkillSynthesizer` distills a **Skill**: a reusable,
parameterized procedure the agent extracts from a successful run and registers as a runnable
tool. Over time the agent's own toolset grows — capability acquisition, not just advice.

A v0.15.0 Skill is a **prompt-program**: a parameterized prompt template executed through the
gateway (no code execution — safe by construction). Code-backed skills are a gated follow-up.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from .reflector import Trajectory

__all__ = ["Skill", "SkillSynthesizer", "SkillStore", "Trajectory"]


class Skill(BaseModel):
    """A distilled, reusable capability, registered as a ``skill.<name>`` tool."""

    name: str  # bare name; registered as ``skill.<name>``
    description: str
    parameters: dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}}
    )  # JSON Schema for the skill's arguments
    template: str = ""  # prompt template with ``{param}`` placeholders
    provenance: str = ""  # the task/session this skill was distilled from
    version: str = "0.1.0"
    tags: list[str] = Field(default_factory=list)
    side_effecting: bool = False  # if True, invocation routes through HITL approval


class SkillSynthesizer(ABC):
    """Distills a reusable Skill from a (successful) trajectory."""

    @abstractmethod
    async def synthesize(self, trajectory: Trajectory) -> Skill | None:
        """Return a reusable Skill, or ``None`` if nothing generalizable was found."""


class SkillStore(ABC):
    """Persists learned skills so they survive across runs/processes."""

    @abstractmethod
    def save(self, skill: Skill) -> None:
        """Persist (or replace) a skill by name."""

    @abstractmethod
    def load_all(self) -> list[Skill]:
        """Load every persisted skill."""
