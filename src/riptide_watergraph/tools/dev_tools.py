"""Agentic developer tools for coding & bug-fixing tasks.

All file tools are confined to a **workspace sandbox** (``Settings.workspace_dir``): a path
that escapes the sandbox via ``..`` or an absolute path is refused, so a tool call can never
read or write arbitrary locations. Mutating tools are ``side_effecting=True`` (they route
through the human-approval gate). Code-execution tools (``run_python``/``run_command``/
``run_tests``) are **opt-in**: they are registered only when ``RIPTIDE_ENABLE_EXEC=1``, because
the HTTP server auto-approves side-effecting tools — running shell commands must be a
deliberate operator choice, never the default.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from ..config import get_settings
from ..interfaces.tools import ToolSpec

_MAX_READ_BYTES = 100_000
_MAX_MATCHES = 200
_EXEC_TIMEOUT_S = 30


def _workspace() -> Path:
    """Resolve (and create) the sandbox root all file tools are confined to."""
    root = Path(get_settings().workspace_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _confine(base: Path, path: str) -> Path:
    """Resolve ``path`` under ``base``; refuse ``..``/absolute escapes (path-traversal guard)."""
    target = (base / path).resolve()
    if target != base and base not in target.parents:
        raise ValueError(f"path escapes the workspace sandbox: {path!r}")
    return target


# --- read-only tools ---------------------------------------------------------


def read_file(path: str, max_bytes: int = _MAX_READ_BYTES) -> str:
    """Read a text file from the workspace (size-capped)."""
    target = _confine(_workspace(), path)
    if not target.is_file():
        return f"no such file: {path!r}"
    data = target.read_text(encoding="utf-8", errors="replace")
    if len(data) > max_bytes:
        return data[:max_bytes] + f"\n... [truncated at {max_bytes} bytes]"
    return data


def list_dir(path: str = ".") -> str:
    """List the entries of a workspace directory (dirs marked with a trailing '/')."""
    target = _confine(_workspace(), path)
    if not target.is_dir():
        return f"no such directory: {path!r}"
    entries = sorted(
        (p.name + ("/" if p.is_dir() else "")) for p in target.iterdir()
    )
    return "\n".join(entries) if entries else "(empty)"


def find_files(pattern: str) -> str:
    """Find files in the workspace matching a glob pattern (e.g. '**/*.py')."""
    base = _workspace()
    hits = [str(p.relative_to(base)) for p in sorted(base.glob(pattern)) if p.is_file()]
    return "\n".join(hits[:_MAX_MATCHES]) if hits else "(no matches)"


def search_code(query: str, glob: str = "**/*") -> str:
    """Regex-search workspace files; return ``path:line: text`` matches (capped)."""
    base = _workspace()
    try:
        rx = re.compile(query)
    except re.error as exc:
        return f"invalid regex: {exc}"
    out: list[str] = []
    for p in sorted(base.glob(glob)):
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if rx.search(line):
                out.append(f"{p.relative_to(base)}:{i}: {line.strip()[:200]}")
                if len(out) >= _MAX_MATCHES:
                    return "\n".join(out) + "\n... [truncated]"
    return "\n".join(out) if out else "(no matches)"


# --- mutating tools (side-effecting) -----------------------------------------


def write_file(path: str, content: str) -> str:
    """Create or overwrite a workspace file (side-effecting)."""
    target = _confine(_workspace(), path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"wrote {len(content)} chars to {target.name}"


def apply_edit(path: str, find: str, replace: str) -> str:
    """Replace an exact, unique ``find`` string with ``replace`` in a workspace file."""
    target = _confine(_workspace(), path)
    if not target.is_file():
        return f"no such file: {path!r}"
    text = target.read_text(encoding="utf-8")
    count = text.count(find)
    if count == 0:
        return f"edit failed: 'find' string not present in {path!r}"
    if count > 1:
        return f"edit failed: 'find' string is not unique in {path!r} ({count} matches)"
    target.write_text(text.replace(find, replace, 1), encoding="utf-8")
    return f"applied 1 edit to {target.name}"


# --- code execution (opt-in via RIPTIDE_ENABLE_EXEC=1) -----------------------


def _run(cmd: list[str], *, shell: bool = False) -> str:
    """Run a command in the workspace with a timeout; return combined output (capped)."""
    try:
        proc = subprocess.run(
            cmd if not shell else cmd[0],
            cwd=str(_workspace()),
            shell=shell,
            capture_output=True,
            text=True,
            timeout=_EXEC_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return f"timed out after {_EXEC_TIMEOUT_S}s"
    except Exception as exc:  # noqa: BLE001 - surface, never crash the run
        return f"execution error: {exc}"
    body = (proc.stdout or "") + (proc.stderr or "")
    if len(body) > _MAX_READ_BYTES:
        body = body[:_MAX_READ_BYTES] + "\n... [truncated]"
    return f"exit={proc.returncode}\n{body}".strip()


def run_python(code: str) -> str:
    """Execute a Python snippet in a subprocess (cwd=workspace, timed out)."""
    return _run([sys.executable, "-c", code])


def run_command(command: str) -> str:
    """Run a shell command in the workspace (cwd=workspace, timed out)."""
    return _run([command], shell=True)


def run_tests(path: str = "") -> str:
    """Run pytest in the workspace (optionally scoped to ``path``)."""
    cmd = [sys.executable, "-m", "pytest", "-q"]
    if path:
        cmd.append(path)
    return _run(cmd)


# --- specs -------------------------------------------------------------------


def _obj(**props: dict) -> dict:
    required = [k for k, v in props.items() if v.pop("_required", True)]
    return {
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": False,
    }


READ_ONLY_SPECS = [
    ToolSpec(
        name="read_file",
        description="Read a text file from the workspace sandbox.",
        json_schema=_obj(path={"type": "string"},
                         max_bytes={"type": "integer", "_required": False}),
        side_effecting=False,
        handler=read_file,
    ),
    ToolSpec(
        name="list_dir",
        description="List entries of a workspace directory.",
        json_schema=_obj(path={"type": "string", "_required": False}),
        side_effecting=False,
        handler=list_dir,
    ),
    ToolSpec(
        name="find_files",
        description="Find workspace files matching a glob pattern (e.g. '**/*.py').",
        json_schema=_obj(pattern={"type": "string"}),
        side_effecting=False,
        handler=find_files,
    ),
    ToolSpec(
        name="search_code",
        description="Regex-search workspace files and return matching lines with locations.",
        json_schema=_obj(query={"type": "string"},
                         glob={"type": "string", "_required": False}),
        side_effecting=False,
        handler=search_code,
    ),
]

MUTATING_SPECS = [
    ToolSpec(
        name="write_file",
        description="Create or overwrite a file in the workspace. Requires approval.",
        json_schema=_obj(path={"type": "string"}, content={"type": "string"}),
        side_effecting=True,
        handler=write_file,
    ),
    ToolSpec(
        name="apply_edit",
        description="Replace an exact, unique string in a workspace file. Requires approval.",
        json_schema=_obj(path={"type": "string"}, find={"type": "string"},
                         replace={"type": "string"}),
        side_effecting=True,
        handler=apply_edit,
    ),
]

EXEC_SPECS = [
    ToolSpec(
        name="run_python",
        description="Execute a Python snippet in the workspace (opt-in). Requires approval.",
        json_schema=_obj(code={"type": "string"}),
        side_effecting=True,
        handler=run_python,
    ),
    ToolSpec(
        name="run_command",
        description="Run a shell command in the workspace (opt-in). Requires approval.",
        json_schema=_obj(command={"type": "string"}),
        side_effecting=True,
        handler=run_command,
    ),
    ToolSpec(
        name="run_tests",
        description="Run pytest in the workspace (opt-in). Requires approval.",
        json_schema=_obj(path={"type": "string", "_required": False}),
        side_effecting=True,
        handler=run_tests,
    ),
]


def dev_tool_specs() -> list[ToolSpec]:
    """The agentic dev tools to register; exec tools only when RIPTIDE_ENABLE_EXEC=1."""
    specs = [*READ_ONLY_SPECS, *MUTATING_SPECS]
    if os.getenv("RIPTIDE_ENABLE_EXEC") == "1":
        specs += EXEC_SPECS
    return specs
