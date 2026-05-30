"""Deterministic offline gateway for demos / CI smoke tests.

Produces plausible plan / tool-call / final-answer responses with no network or API
key, so ``riptide-watergraph run ... --offline`` exercises the full graph spine (including
the human-approval interrupt) locally. It is NOT a model — just enough scripted
behavior to drive the skeleton.
"""

from __future__ import annotations

import json
import re
from typing import Any, AsyncIterator

from ..interfaces.gateway import CompletionResult, Message, ModelGateway

_MATH_RE = re.compile(r"[-+]?\d[\d\s]*[-+*/].*\d")


class DemoGateway(ModelGateway):
    """Scripted, offline ModelGateway."""

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
        system = next((m.content or "" for m in messages if m.role == "system"), "")
        user = next((m.content or "" for m in messages if m.role == "user"), "")

        if "planning orchestrator" in system:
            return CompletionResult(content=json.dumps(self._plan(user)))

        if "You are a worker" in system:
            return self._worker(user)

        # finalize
        return CompletionResult(content=self._finalize(user))

    async def stream(
        self, *, model: str, messages: list[Message], **kwargs: Any
    ) -> AsyncIterator[str]:
        result = await self.complete(model=model, messages=messages)
        yield result.content or ""

    # --- scripted behavior ---

    @staticmethod
    def _plan(task: str) -> list[str]:
        # One subtask is enough to demo the spine.
        return [task]

    @staticmethod
    def _worker(subtask: str) -> CompletionResult:
        low = subtask.lower()
        if _MATH_RE.search(subtask):
            expr = subtask  # the safe calculator parses the arithmetic out
            return CompletionResult(
                tool_calls=[_call("calculator", {"expression": _extract_expr(expr)})]
            )
        if any(w in low for w in ("save", "note", "write", "record")):
            return CompletionResult(
                tool_calls=[
                    _call(
                        "write_note",
                        {
                            "path": ".riptide_watergraph/demo_note.txt",
                            "text": f"Note for task: {subtask}",
                        },
                    )
                ]
            )
        return CompletionResult(content=f"(offline) handled: {subtask}")

    @staticmethod
    def _finalize(user: str) -> str:
        return "(offline) Task complete. See worker results above."


def _call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"demo_{name}",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


def _extract_expr(text: str) -> str:
    """Pull an arithmetic expression out of free text (best-effort)."""
    match = re.search(r"[-+]?\d[\d\s+\-*/().]*\d", text)
    return match.group(0).strip() if match else "0"
