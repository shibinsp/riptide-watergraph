"""LiteLLMGateway coverage without a network call.

`litellm` is imported lazily inside `complete()`/`stream()`, so a fake module in
`sys.modules` lets both methods execute end-to-end offline. `_normalize`/`_safe_get` and
`Message.to_dict` are also unit-tested directly.
"""

from __future__ import annotations

import sys
import types

from riptide_watergraph.gateway.litellm_gateway import LiteLLMGateway, _safe_get
from riptide_watergraph.interfaces.gateway import Message


class _Resp:
    def model_dump(self):
        return {
            "model": "fake-model",
            "choices": [{"message": {"content": "hi", "tool_calls": [
                {"type": "function", "function": {"name": "f", "arguments": "{}"}}]}}],
            "usage": {"total_tokens": 5},
        }


def _install_fake_litellm(monkeypatch, *, stream_chunks=None):
    fake = types.ModuleType("litellm")

    async def acompletion(**payload):
        if payload.get("stream"):
            async def gen():
                for ch in stream_chunks:
                    yield ch
            return gen()
        return _Resp()

    fake.acompletion = acompletion
    monkeypatch.setitem(sys.modules, "litellm", fake)
    return fake


async def test_complete_normalizes_response(monkeypatch):
    _install_fake_litellm(monkeypatch)
    gw = LiteLLMGateway(default_model="fake-model")
    res = await gw.complete(
        model="", messages=[Message(role="user", content="u")],
        tools=[{"type": "function", "function": {"name": "f"}}],
        tool_choice="auto", temperature=0.5, top_p=0.9,
    )
    assert res.content == "hi"
    assert res.tool_calls and res.tool_calls[0]["id"].startswith("call_")  # id backfilled
    assert res.usage == {"total_tokens": 5}


async def test_stream_yields_nonempty_deltas(monkeypatch):
    _install_fake_litellm(monkeypatch, stream_chunks=[
        {"choices": [{"delta": {"content": "Hel"}}]},
        {"choices": [{"delta": {"content": "lo"}}]},
        {"choices": [{"delta": {}}]},  # no content -> skipped
    ])
    gw = LiteLLMGateway(default_model="fake-model")
    out = [c async for c in gw.stream(model="fake-model",
                                      messages=[Message(role="user", content="hi")])]
    assert out == ["Hel", "lo"]


def test_safe_get_paths():
    assert _safe_get(None, "a") is None
    assert _safe_get({"a": {"b": 1}}, "a", "b") == 1
    assert _safe_get([{"x": 9}], 0, "x") == 9
    assert _safe_get({}, 0) is None             # int index on a dict -> TypeError -> None
    assert _safe_get({"a": 1}, "a", "b") is None  # getattr fallback on a non-dict
    obj = types.SimpleNamespace(attr=types.SimpleNamespace(deep=7))
    assert _safe_get(obj, "attr", "deep") == 7


def test_message_to_dict_branches():
    m = Message(role="assistant", content="c", tool_calls=[{"id": "1"}],
                tool_call_id="t", name="n")
    assert m.to_dict() == {"role": "assistant", "content": "c",
                           "tool_calls": [{"id": "1"}], "tool_call_id": "t", "name": "n"}
    assert Message(role="user").to_dict() == {"role": "user"}  # all-empty fields dropped
