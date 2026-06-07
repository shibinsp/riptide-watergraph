"""SkillForge — self-authored, reusable capabilities (prompt-programs).

The agent distills a successful trajectory into a parameterized :class:`Skill`, verifies it,
and registers it as a ``skill.<name>`` tool so future runs can invoke it directly — its own
toolset grows over time. Off by default; enabled per-run (``--learn-skills``) or globally via
``RIPTIDE_ENABLE_SKILLS=1``.
"""

from __future__ import annotations

from ..interfaces.skill import Skill, SkillStore, SkillSynthesizer
from .forge import SKILL_PREFIX, render_template, skill_to_spec
from .store import JsonFileSkillStore
from .synthesis import LLMSkillSynthesizer
from .verify import verify_skill

__all__ = [
    "Skill",
    "SkillSynthesizer",
    "SkillStore",
    "LLMSkillSynthesizer",
    "JsonFileSkillStore",
    "skill_to_spec",
    "render_template",
    "verify_skill",
    "SKILL_PREFIX",
]
