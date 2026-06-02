"""Visual workflow specs: the data model behind the Studio drag-and-drop canvas.

A workflow is a small DAG: each **node** is a step (an instruction assigned to a role) and each
**edge** declares a dependency (``source`` must finish before ``target``). ``spec_to_plan``
topologically flattens it into the ``(plan, roles, dependencies)`` shape the graph already
executes as a swarm (see ``graph/waves.topological_levels`` + ``swarm/plan_composer``).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .config import get_settings


class WorkflowValidationError(ValueError):
    """Raised when a workflow spec is malformed (cycle, dangling edge, etc.)."""

    def __init__(self, messages: list[str]) -> None:
        self.messages = messages
        super().__init__("; ".join(messages))


class WorkflowNode(BaseModel):
    id: str
    role: str = "generalist"
    subtask: str = ""  # the worker instruction; falls back to label then role
    label: str = ""
    x: float = 0.0  # canvas coords — persisted, UI-only, ignored by the engine
    y: float = 0.0


class WorkflowEdge(BaseModel):
    source: str  # upstream node id (must finish first)
    target: str  # downstream node id (depends on source)


class WorkflowSpec(BaseModel):
    name: str = "untitled"
    goal: str = ""  # graph task (memory recall + usage log); defaults to name
    mode: Literal["auto", "swarm", "single"] = "auto"
    nodes: list[WorkflowNode] = Field(default_factory=list)
    edges: list[WorkflowEdge] = Field(default_factory=list)


def _topo_order(ids: list[str], deps: dict[str, set[str]]) -> list[str]:
    """Kahn topological sort; raises on a cycle. Stable by original order."""
    indeg = {i: len(deps[i]) for i in ids}
    queue = [i for i in ids if indeg[i] == 0]  # preserves original order
    order: list[str] = []
    while queue:
        n = queue.pop(0)
        order.append(n)
        for m in ids:  # children of n, in original order
            if n in deps[m]:
                indeg[m] -= 1
                if indeg[m] == 0:
                    queue.append(m)
    if len(order) != len(ids):
        raise WorkflowValidationError(["workflow has a cycle"])
    return order


def validate_spec(spec: WorkflowSpec) -> None:
    """Validate a spec: non-empty, unique ids, edges reference real nodes, acyclic."""
    errors: list[str] = []
    ids = [n.id for n in spec.nodes]
    if not ids:
        errors.append("workflow has no nodes")
    if len(ids) != len(set(ids)):
        errors.append("duplicate node ids")
    idset = set(ids)
    for e in spec.edges:
        if e.source == e.target:
            errors.append(f"self-edge on node {e.source!r}")
        if e.source not in idset or e.target not in idset:
            errors.append(f"edge references unknown node: {e.source!r}->{e.target!r}")
    if errors:
        raise WorkflowValidationError(errors)
    deps: dict[str, set[str]] = {i: set() for i in ids}
    for e in spec.edges:
        deps[e.target].add(e.source)
    _topo_order(ids, deps)  # raises on cycle


def spec_to_plan(spec: WorkflowSpec) -> tuple[list[str], list[str], list[list[int]]]:
    """Flatten a validated spec into ``(plan, roles, dependencies)`` (topo-ordered)."""
    ids = [n.id for n in spec.nodes]
    deps: dict[str, set[str]] = {i: set() for i in ids}
    for e in spec.edges:
        deps[e.target].add(e.source)
    order = _topo_order(ids, deps)
    by_id = {n.id: n for n in spec.nodes}
    index = {nid: i for i, nid in enumerate(order)}
    plan = [by_id[nid].subtask or by_id[nid].label or by_id[nid].role for nid in order]
    roles = [by_id[nid].role for nid in order]
    dependencies = [sorted(index[s] for s in deps[nid]) for nid in order]
    return plan, roles, dependencies


_SAFE_NAME = re.compile(r"[^a-z0-9._-]+")


def _slug(name: str) -> str:
    slug = _SAFE_NAME.sub("-", name.strip().lower()).strip("-.")
    if not slug or slug in (".", ".."):
        raise WorkflowValidationError([f"invalid workflow name: {name!r}"])
    return slug


class WorkflowStore:
    """Persist named workflow specs as JSON files under ``data_dir/workflows/``."""

    def __init__(self, data_dir: str | None = None) -> None:
        self._override = data_dir  # if None, resolved from settings on each access

    @property
    def _dir(self) -> Path:
        base = self._override or get_settings().data_dir
        return Path(base) / "workflows"

    def _path(self, name: str) -> Path:
        target = (self._dir / f"{_slug(name)}.json").resolve()
        if self._dir.resolve() not in target.parents:
            raise WorkflowValidationError([f"unsafe workflow name: {name!r}"])
        return target

    def list(self) -> list[str]:
        if not self._dir.exists():
            return []
        return sorted(p.stem for p in self._dir.glob("*.json"))

    def save(self, spec: WorkflowSpec) -> None:
        path = self._path(spec.name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(spec.model_dump_json(indent=2), encoding="utf-8")

    def get(self, name: str) -> WorkflowSpec | None:
        path = self._path(name)
        if not path.is_file():
            return None
        return WorkflowSpec.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def delete(self, name: str) -> bool:
        path = self._path(name)
        if path.is_file():
            path.unlink()
            return True
        return False
