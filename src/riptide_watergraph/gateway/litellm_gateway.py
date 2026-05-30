"""LiteLLM-backed model gateway (API-first, OpenAI-compatible).

Works with any provider LiteLLM supports (OpenAI, Anthropic, etc.) and with a local
vLLM endpoint by pointing ``OPENAI_API_BASE`` at it. The gateway normalizes LiteLLM's
response into our ``CompletionResult``.
"""

from __future__ import annotations

import uuid
from typing import Any, AsyncIterator

from ..interfaces.gateway import CompletionResult, Message, ModelGateway


class LiteLLMGateway(ModelGateway):
    """Thin async wrapper over ``litellm.acompletion``."""

    def __init__(self, *, default_model: str | None = None) -> None:
        self.default_model = default_model

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
        # Imported lazily so importing the package doesn't require litellm at install.
        import litellm

        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        payload.update(kwargs)

        resp = await litellm.acompletion(**payload)
        return self._normalize(resp)

    async def stream(
        self,
        *,
        model: str,
        messages: list[Message],
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        import litellm

        stream = await litellm.acompletion(
            model=model or self.default_model,
            messages=[m.to_dict() for m in messages],
            stream=True,
            **kwargs,
        )
        async for chunk in stream:
            delta = _safe_get(chunk, "choices", 0, "delta", "content")
            if delta:
                yield delta

    @staticmethod
    def _normalize(resp: Any) -> CompletionResult:
        """Map a LiteLLM response object/dict into a CompletionResult."""
        as_dict = resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)
        choice = (as_dict.get("choices") or [{}])[0]
        msg = choice.get("message", {}) or {}
        tool_calls = list(msg.get("tool_calls") or [])
        # Some providers omit tool-call ids; assign a stable fallback so approvals and
        # metrics never reference a None id.
        for call in tool_calls:
            if isinstance(call, dict) and not call.get("id"):
                call["id"] = f"call_{uuid.uuid4().hex[:8]}"
        usage = as_dict.get("usage")
        return CompletionResult(
            content=msg.get("content"),
            tool_calls=tool_calls,
            raw=as_dict,
            model=as_dict.get("model", ""),
            usage=usage if isinstance(usage, dict) else None,
        )


def _safe_get(obj: Any, *path: Any) -> Any:
    """Best-effort nested lookup over dict-or-attr objects (for streaming chunks)."""
    cur = obj
    for key in path:
        if cur is None:
            return None
        if isinstance(key, int):
            try:
                cur = cur[key]
            except (KeyError, IndexError, TypeError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(key)
        else:
            cur = getattr(cur, key, None)
    return cur
