"""Validate a learned skill before it is registered as a runnable tool.

Checks structural validity (name, template, JSON-Schema-object parameters) and, when
``smoke=True``, performs a single sample invocation that must not raise. Unverified skills
are never registered — a guard against malformed self-authored capabilities.
"""

from __future__ import annotations

import asyncio
from typing import Any

from ..interfaces.gateway import ModelGateway
from ..interfaces.skill import Skill
from .forge import skill_to_spec

__all__ = ["verify_skill"]


def _sample_args(parameters: dict[str, Any]) -> dict[str, Any]:
    """A trivial argument set derived from the schema's declared properties."""
    props = (parameters or {}).get("properties") or {}
    return {name: f"sample_{name}" for name in props}


def verify_skill(
    skill: Skill, *, gateway: ModelGateway, model: str, smoke: bool = True
) -> tuple[bool, str]:
    """Return ``(ok, reason)``; ``ok`` is False with a reason if the skill is invalid."""
    if not skill.name.strip():
        return (False, "skill has no name")
    if not skill.template.strip():
        return (False, "skill has no template")
    if not isinstance(skill.parameters, dict) or skill.parameters.get("type") != "object":
        return (False, "parameters must be a JSON-Schema object")
    if not smoke:
        return (True, "")
    spec = skill_to_spec(skill, gateway=gateway, model=model)
    assert spec.handler is not None  # always set by skill_to_spec
    try:
        asyncio.run(spec.handler(**_sample_args(skill.parameters)))
    except Exception as exc:  # noqa: BLE001 - any failure means the skill isn't safe to register
        return (False, f"smoke invocation failed: {exc}")
    return (True, "")
