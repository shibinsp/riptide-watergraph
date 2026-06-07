"""Persist learned skills as JSON files so they survive across runs and processes."""

from __future__ import annotations

import re
from pathlib import Path

from ..interfaces.skill import Skill, SkillStore

__all__ = ["JsonFileSkillStore"]

_UNSAFE = re.compile(r"[^a-z0-9_.-]+")


class JsonFileSkillStore(SkillStore):
    """One JSON file per skill under ``directory`` (slug-safe filenames)."""

    def __init__(self, directory: str) -> None:
        self.dir = Path(directory)

    def _slug(self, name: str) -> str:
        return _UNSAFE.sub("_", name.lower()) or "skill"

    def save(self, skill: Skill) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self.dir / f"{self._slug(skill.name)}.json"
        path.write_text(skill.model_dump_json(indent=2), encoding="utf-8")

    def load_all(self) -> list[Skill]:
        if not self.dir.exists():
            return []
        return [
            Skill.model_validate_json(p.read_text(encoding="utf-8"))
            for p in sorted(self.dir.glob("*.json"))
        ]
