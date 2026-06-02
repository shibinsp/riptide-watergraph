"""Workflow spec validation, plan flattening, and the persistent store."""

from __future__ import annotations

import pytest

from riptide_watergraph.workflows import (
    WorkflowSpec,
    WorkflowStore,
    WorkflowValidationError,
    spec_to_plan,
    validate_spec,
)


def _spec(nodes, edges=None, **kw):
    return WorkflowSpec(nodes=nodes, edges=edges or [], **kw)


def test_validate_rejects_empty_dup_dangling_self_and_cycle():
    with pytest.raises(WorkflowValidationError):
        validate_spec(_spec([]))
    with pytest.raises(WorkflowValidationError):
        validate_spec(_spec([{"id": "a"}, {"id": "a"}]))
    with pytest.raises(WorkflowValidationError):
        validate_spec(_spec([{"id": "a"}], [{"source": "a", "target": "ghost"}]))
    with pytest.raises(WorkflowValidationError):
        validate_spec(_spec([{"id": "a"}], [{"source": "a", "target": "a"}]))
    with pytest.raises(WorkflowValidationError):
        validate_spec(_spec([{"id": "a"}, {"id": "b"}],
                            [{"source": "a", "target": "b"}, {"source": "b", "target": "a"}]))


def test_spec_to_plan_chain():
    spec = _spec(
        [{"id": "n1", "role": "researcher", "subtask": "find"},
         {"id": "n2", "role": "analyst", "subtask": "count"},
         {"id": "n3", "role": "scribe", "subtask": "write"}],
        [{"source": "n1", "target": "n2"}, {"source": "n2", "target": "n3"}],
    )
    plan, roles, deps = spec_to_plan(spec)
    assert plan == ["find", "count", "write"]
    assert roles == ["researcher", "analyst", "scribe"]
    assert deps == [[], [0], [1]]


def test_spec_to_plan_fanout_indices():
    spec = _spec(
        [{"id": "n1", "subtask": "a"}, {"id": "n2", "subtask": "b"}, {"id": "n3", "subtask": "c"}],
        [{"source": "n1", "target": "n2"}, {"source": "n1", "target": "n3"}],
    )
    plan, _roles, deps = spec_to_plan(spec)
    assert plan[0] == "a"
    assert deps == [[], [0], [0]]


def test_subtask_falls_back_to_label_then_role():
    spec = _spec([{"id": "x", "role": "scribe", "label": "the label"}])
    plan, _r, _d = spec_to_plan(spec)
    assert plan == ["the label"]
    spec2 = _spec([{"id": "x", "role": "scribe"}])
    assert spec_to_plan(spec2)[0] == ["scribe"]


def test_store_round_trip_and_unsafe_name(tmp_path):
    store = WorkflowStore(str(tmp_path))
    spec = _spec([{"id": "a", "role": "generalist", "subtask": "hi"}], name="My Flow")
    store.save(spec)
    assert "my-flow" in store.list()
    assert store.get("My Flow").nodes[0].id == "a"
    assert store.delete("My Flow") is True
    assert store.get("My Flow") is None
    # traversal-ish names are slugified to a safe stem inside the workflows dir...
    safe = store._path("../escape")
    assert safe.parent == (tmp_path / "workflows")
    # ...and a name that slugifies to nothing is rejected outright.
    with pytest.raises(WorkflowValidationError):
        store._path("..")
