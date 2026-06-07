"""LLM-backed skill synthesis.

Given a *successful* trajectory, ask the model to distill a reusable, parameterized skill
(a prompt-program) that would solve similar tasks directly next time. A non-JSON / nameless
/ template-less reply yields no skill — the quality gate keeps junk out of the skill store.
"""

from __future__ import annotations

import json

from ..interfaces.gateway import Message, ModelGateway
from ..interfaces.skill import Skill, SkillSynthesizer, Trajectory

__all__ = ["LLMSkillSynthesizer"]

_SYSTEM = (
    "You are a skill-synthesis module. Given a task an agent solved successfully, distill a "
    "REUSABLE, parameterized skill that would let it solve similar tasks directly next time. "
    'Reply ONLY as JSON: {"name": "snake_case_verb", "description": "<one line>", '
    '"parameters": {"type": "object", "properties": {"<arg>": {"type": "string"}}}, '
    '"template": "<instructions using {arg} placeholders>", "tags": ["<keyword>"]}. '
    "If nothing reusable generalizes, reply {}."
)


class LLMSkillSynthesizer(SkillSynthesizer):
    """Synthesize a Skill from a trajectory via a ModelGateway."""

    def __init__(self, gateway: ModelGateway, *, model: str) -> None:
        self.gateway = gateway
        self.model = model

    async def synthesize(self, trajectory: Trajectory) -> Skill | None:
        if not trajectory.success:
            return None
        transcript = "\n".join(
            f"- {r.get('subtask', '')}: {r.get('output', '')}"
            for r in trajectory.results
        )
        user = f"Task: {trajectory.task}\nSteps:\n{transcript}"
        result = await self.gateway.complete(
            model=self.model,
            messages=[Message(role="system", content=_SYSTEM),
                      Message(role="user", content=user)],
        )
        return _parse_skill(result.content, trajectory)


def _parse_skill(content: str | None, trajectory: Trajectory) -> Skill | None:
    """Parse the synthesis reply into a Skill; tolerant of code fences."""
    if not content:
        return None
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict) or not parsed.get("name") or not parsed.get("template"):
        return None
    params = parsed.get("parameters")
    if not isinstance(params, dict):
        params = {"type": "object", "properties": {}}
    return Skill(
        name=str(parsed["name"]).strip(),
        description=str(parsed.get("description") or parsed["name"]).strip(),
        parameters=params,
        template=str(parsed["template"]),
        provenance=trajectory.session_id or trajectory.task[:48],
        tags=[str(t) for t in (parsed.get("tags") or [])],
    )
