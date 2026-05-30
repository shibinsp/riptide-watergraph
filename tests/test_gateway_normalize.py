"""Coverage for LiteLLMGateway._normalize edge cases and tracing no-ops."""

from __future__ import annotations

from riptide_watergraph.gateway.litellm_gateway import LiteLLMGateway
from riptide_watergraph.observability.tracing import init_tracing, span
from riptide_watergraph.config import Settings


def test_normalize_empty_choices():
    result = LiteLLMGateway._normalize({"model": "m", "choices": []})
    assert result.content is None
    assert result.tool_calls == []


def test_normalize_assigns_fallback_tool_call_id():
    raw = {
        "model": "m",
        "choices": [{"message": {"content": None, "tool_calls": [
            {"type": "function", "function": {"name": "calc", "arguments": "{}"}},
        ]}}],
    }
    result = LiteLLMGateway._normalize(raw)
    assert result.tool_calls[0]["id"]  # a fallback id was assigned


def test_normalize_ignores_non_dict_usage():
    result = LiteLLMGateway._normalize({"model": "m", "choices": [{"message": {}}], "usage": "nope"})
    assert result.usage is None


def test_tracing_disabled_is_noop():
    # Disabled tracing leaves no tracer; span() is a no-op context manager.
    init_tracing(Settings(agentic_water_disable_tracing=True))
    with span("x", attr=1):
        pass  # must not raise
