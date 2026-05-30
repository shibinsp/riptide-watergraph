"""Phase A: tool security — path-traversal guard and safe calculator."""

from __future__ import annotations

from pathlib import Path

import pytest

from riptide_watergraph.tools.examples import calculator, write_note


def test_write_note_allows_paths_inside_cwd(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    msg = write_note("notes/a.txt", "hello")
    assert (tmp_path / "notes" / "a.txt").read_text(encoding="utf-8") == "hello"
    assert "wrote" in msg


def test_write_note_rejects_traversal(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        write_note("../escape.txt", "x")
    with pytest.raises(ValueError):
        write_note(str(Path(tmp_path).parent / "outside.txt"), "x")


def test_calculator_returns_error_instead_of_crashing():
    assert calculator("21 * 2") == "42.0"
    assert calculator("2 +").startswith("calculator error")
    # Disallowed constructs are rejected, not executed.
    assert calculator("__import__('os')").startswith("calculator error")
