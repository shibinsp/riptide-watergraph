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
    tree = ast.parse(expression, mode="eval")
    return str(_eval_node(tree))


def write_note(path: str, text: str) -> str:
    """Write ``text`` to ``path`` (side-effecting)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return f"wrote {len(text)} chars to {p}"


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


def default_registry() -> StaticToolRegistry:
    """A registry preloaded with the example tools."""
    reg = StaticToolRegistry()
    reg.register(CALCULATOR_SPEC)
    reg.register(WRITE_NOTE_SPEC)
    return reg
