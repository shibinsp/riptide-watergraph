"""Shared test fixtures: a deterministic mock gateway."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Callable

import pytest

from riptide_watergraph.interfaces.gateway import CompletionResult, Message, ModelGateway


class MockGateway(ModelGateway):
    """Gateway driven by a scripted responder, for deterministic graph tests.

    ``responder`` receives the system prompt text and the user message text and
    returns a ``CompletionResult``.
    """

    def __init__(self, responder: Callable[[str, str], CompletionResult]) -> None:
        self.responder = responder
        self.calls: list[list[Message]] = []

    async def complete(
        self,
        *,
        model: str,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> CompletionResult:
        self.calls.append(messages)
        system = next((m.content or "" for m in messages if m.role == "system"), "")
        user = next((m.content or "" for m in messages if m.role == "user"), "")
        return self.responder(system, user)

    async def stream(
        self, *, model: str, messages: list[Message], **kwargs: Any
    ) -> AsyncIterator[str]:
        result = await self.complete(model=model, messages=messages)
        yield result.content or ""


def tool_call(name: str, arguments: dict[str, Any], call_id: str = "call_1") -> dict:
    """Build an OpenAI-format tool call (arguments serialized as a JSON string)."""
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


@pytest.fixture
def make_gateway() -> Callable[[Callable[[str, str], CompletionResult]], MockGateway]:
    def _factory(responder: Callable[[str, str], CompletionResult]) -> MockGateway:
        return MockGateway(responder)

    return _factory
