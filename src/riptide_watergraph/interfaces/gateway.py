"""Model gateway interface — the provider-agnostic seam over any LLM."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from pydantic import BaseModel, Field


class Message(BaseModel):
    """A single chat message in OpenAI-compatible shape."""

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Render to the dict shape LiteLLM/OpenAI expect, dropping empty fields."""
        out: dict[str, Any] = {"role": self.role}
        if self.content is not None:
            out["content"] = self.content
        if self.tool_calls:
            out["tool_calls"] = self.tool_calls
        if self.tool_call_id is not None:
            out["tool_call_id"] = self.tool_call_id
        if self.name is not None:
            out["name"] = self.name
        return out


class CompletionResult(BaseModel):
    """Normalized result of a single completion call."""

    content: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)
    model: str = ""
    usage: dict[str, int] | None = None


class ModelGateway(ABC):
    """Provider-agnostic completion interface.

    Stage 1 ships ``LiteLLMGateway``; a local vLLM endpoint is a drop-in later by
    pointing LiteLLM at an OpenAI-compatible base URL.
    """

    @abstractmethod
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
        """Run one (non-streaming) completion and return a normalized result."""

    @abstractmethod
    def stream(
        self,
        *,
        model: str,
        messages: list[Message],
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream completion text chunks (implementations are async generators)."""
