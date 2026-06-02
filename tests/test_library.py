"""The stdlib tool library: every tool invokes to a string; key tools are correct."""

from __future__ import annotations

from typing import Any

import pytest

from riptide_watergraph.tools.library import library_specs

# Format-sensitive tools get realistic inputs to exercise their success paths; the rest
# get generic args. Every handler is wrapped to never raise, so coverage is exercised
# regardless, but realistic inputs cover the happy paths too.
_OVERRIDES: dict[str, dict[str, Any]] = {
    "json_validate": {"text": '{"a": 1}'},
    "json_pretty": {"text": '{"b":2,"a":1}'},
    "json_minify": {"text": '{ "a": 1 }'},
    "json_keys": {"text": '{"a":1,"b":2}'},
    "json_get": {"text": '{"a":{"b":5}}', "path": "a.b"},
    "json_merge": {"a": '{"x":1}', "b": '{"y":2}'},
    "count_json_items": {"text": "[1,2,3]"},
    "flatten_json": {"text": '{"a":{"b":1}}'},
    "csv_to_json": {"text": "a,b\n1,2"},
    "json_to_csv": {"text": '[{"a":1,"b":2}]'},
    "hex_decode": {"text": "68656c6c6f"},
    "base64_decode": {"text": "aGVsbG8="},
    "base32_decode": {"text": "NBSWY3DP"},
    "roman_to_number": {"text": "MMXXIV"},
    "number_to_roman": {"n": 2024},
    "base_convert": {"value": "255", "from_base": 10, "to_base": 16},
    "parse_date": {"text": "2026-06-02"},
    "to_unix": {"text": "2026-06-02T00:00:00"},
    "format_date": {"date": "2026-06-02", "pattern": "%Y/%m/%d"},
    "weekday_name": {"date": "2026-06-02"},
    "iso_week": {"date": "2026-06-02"},
    "add_days": {"date": "2026-06-02", "days": 5},
    "date_diff_days": {"a": "2026-06-01", "b": "2026-06-05"},
    "days_in_month": {"year": 2026, "month": 2},
    "hex_to_rgb": {"hex": "#1296b8"},
    "regex_findall": {"pattern": r"\d+", "text": "a1b22"},
    "regex_match": {"pattern": r"\d+", "text": "a1"},
    "regex_replace": {"pattern": r"\d", "repl": "#", "text": "a1b2"},
    "regex_split": {"pattern": r",", "text": "a,b,c"},
    "regex_groups": {"pattern": r"(\d)(\w)", "text": "1a"},
}


def _generic_args(schema: dict[str, Any]) -> dict[str, Any]:
    props = schema.get("properties", {})
    args: dict[str, Any] = {}
    for key in schema.get("required", []):
        ty = props.get(key, {}).get("type", "string")
        if ty == "integer":
            args[key] = 3
        elif ty == "number":
            args[key] = 3.0
        elif ty == "boolean":
            args[key] = True
        elif ty == "array":
            args[key] = [3, 1, 2]
        else:
            args[key] = "Hello World 42"
    return args


_SPECS = library_specs()


@pytest.mark.parametrize("spec", _SPECS, ids=[s.name for s in _SPECS])
def test_every_tool_returns_a_string(spec):
    args = _OVERRIDES.get(spec.name) or _generic_args(spec.json_schema)
    assert spec.handler is not None
    result = spec.handler(**args)
    assert isinstance(result, str)


def test_library_has_100_plus_tools():
    assert len(_SPECS) >= 100
    assert all(s.category and not s.side_effecting for s in _SPECS)


def test_key_tools_are_correct():
    by_name = {s.name: s.handler for s in _SPECS}
    assert by_name["sha256"](text="hello") == (
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824")
    assert by_name["base64_encode"](text="hi") == "aGk="
    assert by_name["mean"](numbers=[1, 2, 3, 4]) == "2.5"
    assert by_name["slugify"](text="Hello, World!") == "hello-world"
    assert by_name["number_to_roman"](n=2024) == "MMXXIV"
    assert by_name["c_to_f"](c=100) == "212.0"
