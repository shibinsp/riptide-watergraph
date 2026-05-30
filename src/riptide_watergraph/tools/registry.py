"""Static tool registry with versioning + on-demand retrieval (Stage 3).

- **Versioning:** tools are keyed by ``(name, version)``; ``get`` resolves the latest
  version unless one is pinned.
- **On-demand retrieval:** ``retrieve`` ranks tools by relevance to a query (BM25 over
  name+description) and returns only the top-k — so we never dump every tool schema
  into the model's context (they can run to tens of thousands of tokens).
- **Validation:** arguments are checked against each tool's JSON schema before
  invocation; this is what the tool-call reliability gate measures.

MCP interoperability is a thin adapter over this same ``ToolSpec`` shape (future seam).
"""

from __future__ import annotations

import asyncio
from typing import Any

import jsonschema

from ..interfaces.tools import ToolRegistry, ToolSpec
from ..memory.ranking import bm25_score, tokenize


class ToolValidationError(ValueError):
    """Raised when a tool call fails name/argument validation."""


def _version_key(version: str) -> tuple:
    """Sortable key for a semver-ish string; falls back to lexicographic."""
    try:
        return (0, tuple(int(p) for p in version.split(".")))
    except ValueError:
        return (1, version)


class StaticToolRegistry(ToolRegistry):
    """An in-memory catalog keyed by name and version."""

    def __init__(self) -> None:
        self._tools: dict[str, dict[str, ToolSpec]] = {}  # name -> {version: spec}
        self._latest: dict[str, str] = {}  # name -> latest version

    def register(self, spec: ToolSpec) -> None:
        self._tools.setdefault(spec.name, {})[spec.version] = spec
        self._latest[spec.name] = max(self._tools[spec.name], key=_version_key)

    def get(self, name: str, version: str | None = None) -> ToolSpec:
        if name not in self._tools:
            raise ToolValidationError(f"unknown_tool: {name!r}")
        versions = self._tools[name]
        v = version or self._latest[name]
        if v not in versions:
            raise ToolValidationError(
                f"version_mismatch: {name!r} has no version {v!r} "
                f"(available: {sorted(versions)})"
            )
        return versions[v]

    def list_versions(self, name: str) -> list[str]:
        """All registered versions of a tool, oldest-first."""
        if name not in self._tools:
            raise ToolValidationError(f"unknown_tool: {name!r}")
        return sorted(self._tools[name], key=_version_key)

    def all_specs(self) -> list[ToolSpec]:
        """The latest version of every registered tool."""
        return [self._tools[n][self._latest[n]] for n in self._tools]

    def openai_schemas(self, names: list[str] | None = None) -> list[dict[str, Any]]:
        specs = (
            [self.get(n) for n in names if n in self._tools]
            if names is not None
            else self.all_specs()
        )
        return [s.to_openai_schema() for s in specs]

    async def retrieve(self, query: str, *, k: int = 5) -> list[ToolSpec]:
        """Return the top-k tools most relevant to ``query`` (BM25 over name+desc)."""
        specs = self.all_specs()
        if not specs or k <= 0:
            return specs[:k] if k > 0 else []
        if len(specs) <= k:
            return specs
        q_tok = tokenize(query)
        doc_tok = [tokenize(f"{s.name} {s.name} {s.description}") for s in specs]
        scores = bm25_score(q_tok, doc_tok)
        order = sorted(range(len(specs)), key=lambda i: scores[i], reverse=True)
        return [specs[i] for i in order[:k]]

    def validate_call(self, name: str, arguments: dict[str, Any]) -> ToolSpec:
        """Validate a tool call: known name + args matching the JSON schema."""
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
