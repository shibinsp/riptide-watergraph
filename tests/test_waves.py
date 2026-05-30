"""Phase C: topological wave scheduling."""

from __future__ import annotations

from riptide_watergraph.graph.waves import topological_levels


def test_independent_subtasks_form_one_wave():
    assert topological_levels([[], [], []]) == [[0, 1, 2]]


def test_chain_forms_sequential_waves():
    assert topological_levels([[], [0], [1]]) == [[0], [1], [2]]


def test_fan_in_two_then_one():
    # 0 and 1 are independent; 2 depends on both.
    assert topological_levels([[], [], [0, 1]]) == [[0, 1], [2]]


def test_cycle_does_not_hang():
    levels = topological_levels([[1], [0]])  # 0<->1 cycle
    # All nodes are still scheduled (as a remainder wave), never an infinite loop.
    assert sorted(i for w in levels for i in w) == [0, 1]


def test_empty():
    assert topological_levels([]) == []
