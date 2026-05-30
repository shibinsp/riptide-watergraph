"""Static tool registry (Stage 1).

Validates arguments against each tool's JSON schema before invoking — this validation
is also what the tool-call reliability gate measures. ``retrieve()`` returns all tools
for now; Stage 3 adds versioned, on-demand retrieval (and MCP interop).
"""

from __future__ import annotations

import asyncio
from typing import Any

import jsonschema

from ..interfaces.tools import ToolRegistry, ToolSpec


class ToolValidationError(ValueError):
    """Raised when a tool call fails name/argument validation."""


class StaticToolRegistry(ToolRegistry):
    """An in-memory, name-keyed catalog of tools."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def get(self, name: str, version: str | None = None) -> ToolSpec:
        if name not in self._tools:
            raise ToolValidationError(f"unknown_tool: {name!r}")
        spec = self._tools[name]
        if version is not None and spec.version != version:
            raise ToolValidationError(
                f"version_mismatch: {name!r} has {spec.version}, asked {version}"
            )
        return spec

    def openai_schemas(self, names: list[str] | None = None) -> list[dict[str, Any]]:
        specs = (
            [self._tools[n] for n in names if n in self._tools]
            if names is not None
            else list(self._tools.values())
        )
        return [s.to_openai_schema() for s in specs]

    async def retrieve(self, query: str, *, k: int = 5) -> list[ToolSpec]:
        # Stage-1 stub: return everything (bounded by k).
        return list(self._tools.values())[:k]

    def validate_call(self, name: str, arguments: dict[str, Any]) -> ToolSpec:
        """Validate a tool call: known name + args matching the JSON schema.

        Returns the resolved ToolSpec, or raises ToolValidationError. This is the
        single check the reliability gate counts.
        """
        spec = self.get(name)
        try:
            jsonschema.validate(instance=arguments, schema=spec.json_schema)
        except jsonschema.ValidationError as exc:
            raise ToolValidationError(f"schema_violation: {exc.message}") from exc
        return spec

    async def invoke(self, name: str, arguments: dict[str, Any]) -> Any:
        spec = self.validate_call(name, arguments)
        if spec.handler is None:
            raise ToolValidationError(f"no_handler: {name!r}")
        result = spec.handler(**arguments)
        if asyncio.iscoroutine(result):
            result = await result
        return result
