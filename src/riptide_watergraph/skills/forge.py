"""Turn a learned Skill into a runnable ToolSpec (a prompt-program).

A prompt-program skill's handler renders the template with the call arguments and runs a
single gateway completion — no code execution, safe by construction. The resulting
``skill.<name>`` tool is retrieved and invoked by the worker exactly like any other tool.
"""

from __future__ import annotations

import re
from typing import Any

from ..interfaces.gateway import Message, ModelGateway
from ..interfaces.skill import Skill
from ..interfaces.tools import ToolSpec

__all__ = ["skill_to_spec", "render_template", "SKILL_PREFIX"]

SKILL_PREFIX = "skill."
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def render_template(template: str, args: dict[str, Any]) -> str:
    """Substitute ``{name}`` placeholders from ``args``; leave unknown ones intact."""

    def _sub(match: re.Match[str]) -> str:
        key = match.group(1)
        return str(args[key]) if key in args else match.group(0)

    return _PLACEHOLDER.sub(_sub, template)


def skill_to_spec(skill: Skill, *, gateway: ModelGateway, model: str) -> ToolSpec:
    """Bind a Skill into an invokable ToolSpec namespaced ``skill.<name>``."""
    full_name = f"{SKILL_PREFIX}{skill.name}"
    system = (
        f"You are executing a learned skill: {skill.description}. "
        "Follow the instructions precisely and return only the result."
    )

    async def handler(**kwargs: Any) -> str:
        prompt = render_template(skill.template, kwargs)
        result = await gateway.complete(
            model=model,
            messages=[Message(role="system", content=system),
                      Message(role="user", content=prompt)],
        )
        return result.content or ""

    return ToolSpec(
        name=full_name,
        version=skill.version,
        description=skill.description,
        json_schema=skill.parameters,
        side_effecting=skill.side_effecting,
        category="skill",
        tags=["skill", *skill.tags],
        handler=handler,
    )
