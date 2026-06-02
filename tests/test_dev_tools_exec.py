"""Edge + exec coverage for tools/dev_tools.py.

Read-only/mutating error branches run against a tmp workspace; the exec wrappers are
covered with a mocked ``_run`` (no real subprocess), and ``_run``'s timeout/error/truncate
branches with a mocked ``subprocess.run``.
"""

from __future__ import annotations

import subprocess
import types

import pytest

from riptide_watergraph.tools import dev_tools as dt


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path / "ws"))
    return dt._workspace()


def test_read_file_missing_and_truncate(ws):
    assert "no such file" in dt.read_file("nope.txt")
    (ws / "big.txt").write_text("x" * 50, encoding="utf-8")
    assert "[truncated at 10 bytes]" in dt.read_file("big.txt", max_bytes=10)


def test_list_dir_missing(ws):
    assert "no such directory" in dt.list_dir("nodir")


def test_search_code_invalid_regex(ws):
    assert "invalid regex" in dt.search_code("(")


def test_search_code_skips_directories(ws):
    (ws / "sub").mkdir()
    (ws / "a.txt").write_text("match here", encoding="utf-8")
    assert "a.txt" in dt.search_code("match")  # the 'sub' dir is skipped (not a file)


def test_search_code_truncates(ws):
    (ws / "many.txt").write_text("\n".join(["match"] * 201), encoding="utf-8")
    assert "[truncated]" in dt.search_code("match")


def test_apply_edit_missing_file(ws):
    assert "no such file" in dt.apply_edit("nope.txt", "a", "b")


def test_exec_wrappers_use_run(monkeypatch):
    calls = []
    monkeypatch.setattr(dt, "_run", lambda cmd, **kw: calls.append((cmd, kw)) or "ok")
    assert dt.run_python("print(1)") == "ok"
    assert dt.run_command("echo hi") == "ok"
    assert dt.run_tests() == "ok"
    assert dt.run_tests("tests/x.py") == "ok"   # path-append branch
    assert dt.run_node("1+1") == "ok"
    assert dt.lint_python() == "ok"
    assert dt.format_python() == "ok"
    assert any(kw.get("shell") for _, kw in calls)  # run_command passes shell=True


def test_run_timeout(ws, monkeypatch):
    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="x", timeout=dt._EXEC_TIMEOUT_S)
    monkeypatch.setattr(dt.subprocess, "run", boom)
    assert "timed out" in dt._run(["x"])


def test_run_generic_error(ws, monkeypatch):
    monkeypatch.setattr(dt.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    assert "execution error" in dt._run(["x"])


def test_run_truncates_output(ws, monkeypatch):
    proc = types.SimpleNamespace(stdout="y" * (dt._MAX_READ_BYTES + 10), stderr="", returncode=0)
    monkeypatch.setattr(dt.subprocess, "run", lambda *a, **k: proc)
    assert "[truncated]" in dt._run(["x"])
