"""On-demand tool retrieval + versioning."""

from __future__ import annotations

import pytest

from riptide_watergraph.interfaces.tools import ToolSpec
from riptide_watergraph.tools import default_registry
from riptide_watergraph.tools.registry import StaticToolRegistry, ToolValidationError


async def test_retrieve_ranks_relevant_tools_first():
    reg = default_registry()  # 6 tools
    hits = await reg.retrieve("evaluate an arithmetic expression", k=2)
    assert len(hits) == 2
    assert hits[0].name == "calculator"


async def test_retrieve_caps_at_k():
    reg = default_registry()
    hits = await reg.retrieve("anything", k=3)
    assert len(hits) == 3  # only top-k enter context, not all 6


async def test_retrieve_word_count_query():
    reg = default_registry()
    hits = await reg.retrieve("count the words in this text", k=1)
    assert hits[0].name == "word_count"


def _spec(version: str) -> ToolSpec:
    return ToolSpec(
        name="thing",
        version=version,
        description="does a thing",
        json_schema={"type": "object", "properties": {}, "additionalProperties": True},
    )


def test_versioning_resolves_latest_and_pinned():
    reg = StaticToolRegistry()
    reg.register(_spec("0.1.0"))
    reg.register(_spec("0.2.0"))
    reg.register(_spec("0.10.0"))  # numeric, not lexicographic, ordering

    assert reg.list_versions("thing") == ["0.1.0", "0.2.0", "0.10.0"]
    assert reg.get("thing").version == "0.10.0"          # latest by default
    assert reg.get("thing", "0.1.0").version == "0.1.0"  # pinned

    with pytest.raises(ToolValidationError):
        reg.get("thing", "9.9.9")
    with pytest.raises(ToolValidationError):
        reg.get("missing")
