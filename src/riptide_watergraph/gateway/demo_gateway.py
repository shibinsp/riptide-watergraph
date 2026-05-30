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
_SPLIT_RE = re.compile(r"\s+(?:and then|then|and|also|;|,|plus)\s+", re.IGNORECASE)


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

        if "You are a critic" in system:
            return CompletionResult(content=self._critic(user))

        if "reflection module" in system:
            return CompletionResult(content=self._reflect(user))

        if "planning composer" in system:
            return CompletionResult(content=self._compose(user))

        if "planning orchestrator" in system:
            return CompletionResult(content=json.dumps(self._plan(user)))

        if "You are a worker" in system:
            return self._worker(user, tools)

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
        # Split on connectives so multi-goal tasks decompose (and may trigger a swarm).
        parts = [p.strip() for p in _SPLIT_RE.split(task) if p.strip()]
        return parts or [task]

    @staticmethod
    def _worker(subtask: str, tools: list[dict[str, Any]] | None) -> CompletionResult:
        low = subtask.lower()
        available = {
            (t.get("function") or {}).get("name")
            for t in (tools or [])
        }

        def offer(name: str) -> bool:
            # If the model was given tools, only call ones actually offered.
            return name in available if available else True

        if _MATH_RE.search(subtask) and offer("calculator"):
            return CompletionResult(
                tool_calls=[_call("calculator", {"expression": _extract_expr(subtask)})]
            )
        if any(w in low for w in ("save", "note", "write", "record")) and offer("write_note"):
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
        if any(w in low for w in ("count", "words")) and offer("word_count"):
            return CompletionResult(tool_calls=[_call("word_count", {"text": subtask})])
        if any(w in low for w in ("upper", "capital")) and offer("uppercase"):
            return CompletionResult(tool_calls=[_call("uppercase", {"text": subtask})])
        if any(w in low for w in ("search", "find", "look up", "lookup")) and offer("web_search"):
            return CompletionResult(tool_calls=[_call("web_search", {"query": subtask})])
        return CompletionResult(content=f"(offline) handled: {subtask}")

    @staticmethod
    def _finalize(user: str) -> str:
        return "(offline) Task complete. See worker results above."

    @staticmethod
    def _compose(task: str) -> str:
        """Deterministic composer: 'then' => sequential waves, 'and'/',' => parallel."""
        segments = [s.strip() for s in re.split(r"\s+then\s+", task, flags=re.I) if s.strip()]
        plan: list[str] = []
        deps: list[list[int]] = []
        prev: list[int] = []
        for seg in segments:
            parts = [p.strip() for p in re.split(r"\s+and\s+|,\s*", seg, flags=re.I) if p.strip()]
            current: list[int] = []
            for part in parts:
                idx = len(plan)
                plan.append(part)
                deps.append(list(prev))  # depends on all of the previous wave
                current.append(idx)
            prev = current
        mode = "swarm" if len(plan) >= 2 else "single"
        subtasks = [{"task": plan[i], "depends_on": deps[i]} for i in range(len(plan))]
        return json.dumps({"mode": mode, "subtasks": subtasks})

    @staticmethod
    def _critic(user: str) -> str:
        """Offline critic: fail results that look invalid/empty, else pass."""
        result = user.split("Result:", 1)[1].strip() if "Result:" in user else user
        low = result.lower()
        bad = (not low) or any(
            w in low for w in ("invalid", "failed", "error", "needs approval")
        )
        return json.dumps({"verdict": "fail" if bad else "pass", "reason": "offline"})

    @staticmethod
    def _reflect(user: str) -> str:
        # Distill a deterministic lesson from the task line in the trajectory.
        task = ""
        for line in user.splitlines():
            if line.lower().startswith("task:"):
                task = line.split(":", 1)[1].strip()
                break
        lesson = (
            f"For tasks like '{task}', decompose into one concrete subtask and use "
            "the most specific available tool."
        )
        return json.dumps({"lesson": lesson, "tags": ["offline", "demo"]})


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
