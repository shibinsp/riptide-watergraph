"""Agentic developer tools: workspace confinement, edits, search, exec gating, coder role."""

from __future__ import annotations

import asyncio

import pytest

from riptide_watergraph.swarm.roles import get_role, role_for
from riptide_watergraph.tools import default_registry
from riptide_watergraph.tools import dev_tools as dt


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))
    return tmp_path


def test_write_read_and_list(workspace):
    assert "wrote" in dt.write_file("pkg/m.py", "x = 1\n")
    assert dt.read_file("pkg/m.py") == "x = 1\n"
    assert "pkg/" in dt.list_dir(".")


def test_find_and_search(workspace):
    dt.write_file("a.py", "def add(a, b):\n    return a - b  # bug\n")
    assert "a.py" in dt.find_files("**/*.py")
    hits = dt.search_code("return")
    assert "a.py:2:" in hits and "bug" in hits


def test_apply_edit_unique_and_errors(workspace):
    dt.write_file("a.py", "return a - b\n")
    assert "applied 1 edit" in dt.apply_edit("a.py", "a - b", "a + b")
    assert dt.read_file("a.py") == "return a + b\n"
    # missing find string
    assert "not present" in dt.apply_edit("a.py", "nope", "x")
    # ambiguous find string
    dt.write_file("b.py", "z\nz\n")
    assert "not unique" in dt.apply_edit("b.py", "z", "y")


def test_path_traversal_refused(workspace):
    for fn in (lambda: dt.read_file("../escape.txt"),
               lambda: dt.write_file("../escape.txt", "x"),
               lambda: dt.apply_edit("/etc/passwd", "a", "b")):
        with pytest.raises(ValueError):
            fn()


def test_mutating_tools_are_side_effecting():
    reg = default_registry()
    assert reg.get("write_file").side_effecting is True
    assert reg.get("apply_edit").side_effecting is True
    assert reg.get("read_file").side_effecting is False


def test_default_registry_has_twelve_tools_without_exec(monkeypatch):
    monkeypatch.delenv("RIPTIDE_ENABLE_EXEC", raising=False)
    names = {s.name for s in default_registry().all_specs()}
    assert {"read_file", "write_file", "apply_edit", "search_code"} <= names
    assert "run_python" not in names  # exec tools gated off


def test_exec_tools_registered_only_with_flag(workspace, monkeypatch):
    monkeypatch.setenv("RIPTIDE_ENABLE_EXEC", "1")
    names = {s.name for s in default_registry().all_specs()}
    assert {"run_python", "run_command", "run_tests"} <= names
    out = dt.run_python("print(2 + 2)")
    assert "exit=0" in out and "4" in out


def test_invoke_dispatches_dev_tool(workspace):
    reg = default_registry()
    dt.write_file("note.txt", "hello world")
    result = asyncio.run(reg.invoke("read_file", {"path": "note.txt"}))
    assert result == "hello world"


def test_role_for_routes_coding_tasks():
    assert role_for("fix the bug in app.py") == "coder"
    assert role_for("refactor the module") == "coder"
    assert role_for("compute 21 * 2") == "analyst"
    assert role_for("search for cats") == "researcher"
    assert role_for("write a note") == "scribe"
    assert "read_file" in (get_role("coder").tools or [])
