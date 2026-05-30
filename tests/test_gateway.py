"""Gateway normalization + memory ranking integration (no live API calls)."""

from __future__ import annotations

from riptide_watergraph import InMemoryMemory
from riptide_watergraph.gateway.litellm_gateway import LiteLLMGateway
from riptide_watergraph.interfaces.memory import MemoryRecord


def test_litellm_normalize_content_and_tool_calls():
    raw = {
        "model": "gpt-4o-mini",
        "choices": [
            {
                "message": {
                    "content": "hello",
                    "tool_calls": [
                        {
                            "id": "c1",
                            "type": "function",
                            "function": {"name": "calculator", "arguments": "{}"},
                        }
                    ],
                }
            }
        ],
        "usage": {"prompt_tokens": 3, "completion_tokens": 1},
    }
    result = LiteLLMGateway._normalize(raw)
    assert result.content == "hello"
    assert result.model == "gpt-4o-mini"
    assert result.tool_calls[0]["function"]["name"] == "calculator"
    assert result.usage == {"prompt_tokens": 3, "completion_tokens": 1}


async def test_inmemory_retrieve_uses_hybrid_ranking():
    mem = InMemoryMemory()
    await mem.write(
        [
            MemoryRecord(id="a", text="the river flows with clear water"),
            MemoryRecord(id="b", text="mountains and snow and rock"),
            MemoryRecord(id="c", text="water is essential for life"),
        ]
    )
    hits = await mem.retrieve("water", k=2)
    assert len(hits) == 2
    # The two water-mentioning records should rank above the mountain one.
    ids = {h.record.id for h in hits}
    assert ids == {"a", "c"}
