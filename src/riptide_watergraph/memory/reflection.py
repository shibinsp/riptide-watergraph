"""LLM-backed reflection (Reflexion / ReasoningBank pattern).

Given a completed trajectory, ask the model to judge the outcome and distill ONE
concise, reusable lesson — a generalizable strategy, not an episode replay. The lesson
is stored as procedural memory and retrieved on similar future tasks.
"""

from __future__ import annotations

import json

from ..interfaces.gateway import Message, ModelGateway
from ..interfaces.memory import MemoryRecord
from ..interfaces.reflector import Reflector, Trajectory
from .types import lesson_record

_SYSTEM = (
    "You are a reflection module. Given a task and how an agent attempted it, distill "
    "ONE concise, reusable lesson that would help on similar future tasks — name the "
    "right tool and argument shape when relevant. Reply ONLY as JSON: "
    '{"lesson": "<one sentence>", "tags": ["<keyword>", ...]}.'
)


class LLMReflector(Reflector):
    """Reflector that distills a lesson via a ModelGateway."""

    def __init__(self, gateway: ModelGateway, *, model: str) -> None:
        self.gateway = gateway
        self.model = model

    async def reflect(self, trajectory: Trajectory) -> list[MemoryRecord]:
        transcript = "\n".join(
            f"- {r.get('subtask', '')}: {r.get('output', '')}"
            for r in trajectory.results
        )
        outcome = "SUCCESS" if trajectory.success else "FAILURE"
        user = (
            f"Task: {trajectory.task}\n"
            f"Outcome: {outcome}\n"
            f"Tool-call metrics: {json.dumps(trajectory.metrics)}\n"
            f"Steps:\n{transcript}"
        )
        result = await self.gateway.complete(
            model=self.model,
            messages=[Message(role="system", content=_SYSTEM),
                      Message(role="user", content=user)],
        )
        lesson_text, tags = _parse_lesson(result.content, trajectory.task)
        if not lesson_text:
            return []
        return [
            lesson_record(
                lesson_text,
                task=trajectory.task,
                success=trajectory.success,
                tags=tags,
            )
        ]


def _parse_lesson(content: str | None, task: str) -> tuple[str, list[str]]:
    """Parse the reflection reply into (lesson_text, tags); tolerant of fences."""
    if not content:
        return "", []
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and parsed.get("lesson"):
            tags = parsed.get("tags") or []
            return str(parsed["lesson"]).strip(), [str(t) for t in tags]
    except json.JSONDecodeError:
        pass
    # Fallback: treat the whole reply as the lesson.
    return text, []
