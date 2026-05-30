"""Agent interface — the thin agent-core seam over a model gateway."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .gateway import CompletionResult, Message


class Agent(ABC):
    """A minimal agent: a name plus an ``act`` step over a message history."""

    name: str

    @abstractmethod
    async def act(self, messages: list[Message]) -> CompletionResult:
        """Take one turn given the conversation so far."""
