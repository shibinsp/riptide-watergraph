"""Resilience wrapper for any ModelGateway.

Adds per-call timeouts and exponential-backoff retries around a wrapped gateway, so a
transient API timeout or 5xx doesn't crash the whole graph run. Composable: wrap the
real gateway once and pass it to ``build_graph`` — nodes are unchanged.

Hand-rolled (no extra dependency) to keep the core lean.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

from ..interfaces.gateway import CompletionResult, Message, ModelGateway


class ResilientGateway(ModelGateway):
    """Wrap a gateway with timeout + retry/backoff."""

    def __init__(
        self,
        inner: ModelGateway,
        *,
        max_attempts: int = 3,
        timeout_s: float = 60.0,
        base_backoff_s: float = 0.5,
    ) -> None:
        self.inner = inner
        self.max_attempts = max(1, max_attempts)
        self.timeout_s = timeout_s
        self.base_backoff_s = base_backoff_s

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
        last_exc: Exception | None = None
        for attempt in range(self.max_attempts):
            try:
                return await asyncio.wait_for(
                    self.inner.complete(
                        model=model,
                        messages=messages,
                        tools=tools,
                        tool_choice=tool_choice,
                        temperature=temperature,
                        **kwargs,
                    ),
                    timeout=self.timeout_s,
                )
            except (asyncio.TimeoutError, Exception) as exc:  # noqa: BLE001
                last_exc = exc
                if attempt + 1 >= self.max_attempts:
                    break
                await asyncio.sleep(self.base_backoff_s * (2**attempt))
        assert last_exc is not None
        raise last_exc

    async def stream(
        self, *, model: str, messages: list[Message], **kwargs: Any
    ) -> AsyncIterator[str]:
        # Streaming is passed through without retry (mid-stream retry would duplicate
        # already-yielded tokens). A connect-time failure still surfaces to the caller.
        async for chunk in self.inner.stream(model=model, messages=messages, **kwargs):
            yield chunk
