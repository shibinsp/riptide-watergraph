"""Example tools for the walking skeleton.

- ``calculator`` — pure/read-only; runs inline without approval.
- ``write_note`` — side-effecting (writes a file); routes through the HITL approval
  gate, and (critically) is executed only AFTER approval so resume stays idempotent.
"""

from __future__ import annotations

import ast
import operator
from pathlib import Path

from ..interfaces.tools import ToolSpec
from .registry import StaticToolRegistry

# --- calculator (safe arithmetic eval) ---

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("unsupported expression")


def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression safely."""
    try:
        tree = ast.parse(expression, mode="eval")
        return str(_eval_node(tree))
    except Exception as exc:  # noqa: BLE001 - surface a message, never crash
        return f"calculator error: {exc}"


def write_note(path: str, text: str) -> str:
    """Write ``text`` to ``path`` (side-effecting).

    Confined to the current working directory: absolute paths or ``..`` traversal that
    escape the cwd are refused, so a tool call can't write to arbitrary locations.
    """
    base = Path.cwd().resolve()
    target = (base / path).resolve()
    if target != base and base not in target.parents:
        raise ValueError(f"refusing to write outside the working directory: {path!r}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return f"wrote {len(text)} chars to {target}"


# --- additional read-only tools (give on-demand retrieval something to rank) ---


def word_count(text: str) -> str:
    """Count the words in a piece of text."""
    return str(len(text.split()))


def uppercase(text: str) -> str:
    """Convert text to upper case."""
    return text.upper()


def reverse_text(text: str) -> str:
    """Reverse the characters of a string."""
    return text[::-1]


def web_search(query: str) -> str:
    """Offline stand-in for a web search lookup."""
    return f"(stub) top result for {query!r}"


CALCULATOR_SPEC = ToolSpec(
    name="calculator",
    description="Evaluate a basic arithmetic expression (e.g. '21 * 2').",
    json_schema={
        "type": "object",
        "properties": {"expression": {"type": "string"}},
        "required": ["expression"],
        "additionalProperties": False,
    },
    side_effecting=False,
    handler=calculator,
)

WRITE_NOTE_SPEC = ToolSpec(
    name="write_note",
    description="Write text to a file on disk. Requires human approval.",
    json_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "text": {"type": "string"},
        },
        "required": ["path", "text"],
        "additionalProperties": False,
    },
    side_effecting=True,
    handler=write_note,
)


def _text_tool(name: str, description: str, handler) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=description,
        json_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
        side_effecting=False,
        handler=handler,
    )


WORD_COUNT_SPEC = _text_tool("word_count", "Count the words in a piece of text.", word_count)
UPPERCASE_SPEC = _text_tool("uppercase", "Convert text to upper case.", uppercase)
REVERSE_TEXT_SPEC = _text_tool("reverse_text", "Reverse the characters of a string.", reverse_text)

WEB_SEARCH_SPEC = ToolSpec(
    name="web_search",
    description="Search the web for a query and return the top result.",
    json_schema={
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
        "additionalProperties": False,
    },
    side_effecting=False,
    handler=web_search,
)

ALL_SPECS = [
    CALCULATOR_SPEC,
    WRITE_NOTE_SPEC,
    WORD_COUNT_SPEC,
    UPPERCASE_SPEC,
    REVERSE_TEXT_SPEC,
    WEB_SEARCH_SPEC,
]


def default_registry() -> StaticToolRegistry:
    """A registry preloaded with the example tools."""
    reg = StaticToolRegistry()
    for spec in ALL_SPECS:
        reg.register(spec)
    return reg
