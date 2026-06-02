"""Tool registry interface — the reusable, MCP-compatible tool/skill seam.

Stage 1 ships ``StaticToolRegistry`` whose ``retrieve()`` returns all tools. Stage 3
adds versioning + on-demand retrieval (never dump all schemas into context).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field


class ToolSpec(BaseModel):
    """A tool's identity, schema, permissions, and (optional) handler."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    version: str = "0.1.0"
    description: str
    json_schema: dict[str, Any]  # OpenAI/MCP-compatible parameters schema
    side_effecting: bool = False  # if True, invocation routes through HITL approval
    category: str = "general"  # grouping for the registry/Studio gallery
    tags: list[str] = Field(default_factory=list)  # free-form labels for search/filter
    # Excluded from serialization; carries the actual callable.
    handler: Callable[..., Any] | None = Field(default=None, exclude=True)

    def to_openai_schema(self) -> dict[str, Any]:
        """Render as an OpenAI/LiteLLM `tools` entry."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.json_schema,
            },
        }


class ToolRegistry(ABC):
    """A catalog of tools with schema export, retrieval, and invocation."""

    @abstractmethod
    def register(self, spec: ToolSpec) -> None:
        """Add (or replace) a tool."""

    @abstractmethod
    def get(self, name: str, version: str | None = None) -> ToolSpec:
        """Look up a tool by name (and optional version)."""

    @abstractmethod
    def openai_schemas(self, names: list[str] | None = None) -> list[dict[str, Any]]:
        """Export OpenAI-format schemas for the named tools (or all)."""

    @abstractmethod
    async def retrieve(
        self, query: str, *, k: int = 5, allowed: set[str] | None = None
    ) -> list[ToolSpec]:
        """On-demand tool retrieval, optionally restricted to ``allowed`` tool names."""

    @abstractmethod
    async def invoke(self, name: str, arguments: dict[str, Any]) -> Any:
        """Execute a tool's handler with validated arguments."""
