"""A broad library of read-only, stdlib-only tools, grouped into categories.

Every handler is a pure function returning a string and never raises (errors are returned
as ``"error: ..."``), so they are safe to run inline (``side_effecting=False``) with no
network or filesystem access. A gated **network** pack (``RIPTIDE_ENABLE_NETWORK=1``) adds
read-only HTTP/DNS tools via the stdlib ``urllib``.

The packs exist mainly to give the on-demand tool retriever (BM25, scoped per role) a rich
catalog to draw from — a worker still only ever sees its role's ``tool_k`` best matches.
"""

from __future__ import annotations

import base64
import colorsys
import datetime as _dt
import hashlib
import hmac
import html
import io
import json
import math
import os
import random
import re
import statistics
import textwrap
import unicodedata
import urllib.parse
import urllib.request
import uuid
import zlib
from typing import Any, Callable

from ..interfaces.tools import ToolSpec

_S = {"type": "string"}
_N = {"type": "number"}
_I = {"type": "integer"}
_B = {"type": "boolean"}


def _schema(props: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": required,
            "additionalProperties": False}


def _spec(name: str, description: str, handler: Callable[..., Any], props: dict[str, Any],
          required: list[str], category: str, tags: list[str]) -> ToolSpec:
    return ToolSpec(name=name, description=description, handler=handler,
                    json_schema=_schema(props, required), category=category, tags=tags,
                    side_effecting=False)


def _safe(fn: Callable[..., Any]) -> Callable[..., str]:
    def wrapped(**kw: Any) -> str:
        try:
            return str(fn(**kw))
        except Exception as exc:  # noqa: BLE001 - tools surface errors, never crash
            return f"error: {type(exc).__name__}: {exc}"
    return wrapped


_SPECS: list[ToolSpec] = []


def _add(name: str, desc: str, fn: Callable[..., Any], props: dict[str, Any],
         required: list[str], category: str = "general", *tags: str) -> None:
    _SPECS.append(_spec(name, desc, _safe(fn), props, required, category, list(tags)))


# Constants used by the pack handlers below (defined before use for clarity + typing).
_ROT13 = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
    "NOPQRSTUVWXYZABCDEFGHIJKLMnopqrstuvwxyzabcdefghijklm")
_ALNUM = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
_PWCHARS = _ALNUM + "!@#$%^&*()-_=+"
_LOREM = ("lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor "
          "incididunt ut labore et dolore magna aliqua").split()


# --- text (category: text) ---------------------------------------------------
_T = {"text": _S}
_add("char_count", "Count characters in text.", lambda text: len(text), _T, ["text"], "text", "string")
_add("line_count", "Count lines in text.", lambda text: len(text.splitlines()), _T, ["text"], "text")
_add("sentence_count", "Count sentences in text.", lambda text: len(re.findall(r"[.!?]+", text)), _T, ["text"], "text")
_add("lowercase_text", "Lowercase text.", lambda text: text.lower(), _T, ["text"], "text", "case")
_add("uppercase_text", "Uppercase text.", lambda text: text.upper(), _T, ["text"], "text", "case")
_add("titlecase", "Title-case text.", lambda text: text.title(), _T, ["text"], "text", "case")
_add("capitalize_text", "Capitalize the first character.", lambda text: text.capitalize(), _T, ["text"], "text")
_add("swapcase", "Swap the case of each character.", lambda text: text.swapcase(), _T, ["text"], "text")
_add("reverse_string", "Reverse a string.", lambda text: text[::-1], _T, ["text"], "text")
_add("strip_text", "Strip leading/trailing whitespace.", lambda text: text.strip(), _T, ["text"], "text")
_add("normalize_whitespace", "Collapse runs of whitespace to single spaces.",
     lambda text: re.sub(r"\s+", " ", text).strip(), _T, ["text"], "text")
_add("slugify", "Make a URL-safe slug from text.",
     lambda text: re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-"), _T, ["text"], "text", "web")
_add("snake_case", "Convert text to snake_case.",
     lambda text: re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_"), _T, ["text"], "text")
_add("kebab_case", "Convert text to kebab-case.",
     lambda text: re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-"), _T, ["text"], "text")
_add("camel_case", "Convert text to camelCase.",
     lambda text: (lambda w: w[0].lower() + "".join(p.title() for p in w[1:]) if w else "")(
         re.split(r"[^a-zA-Z0-9]+", text)), _T, ["text"], "text")
_add("truncate_text", "Truncate text to n characters with an ellipsis.",
     lambda text, n: text if len(text) <= n else text[: max(0, n - 1)] + "…",
     {"text": _S, "n": _I}, ["text", "n"], "text")
_add("wrap_text", "Wrap text to a given width.",
     lambda text, width: textwrap.fill(text, width=width), {"text": _S, "width": _I}, ["text", "width"], "text")
_add("dedent_text", "Remove common leading whitespace from every line.",
     lambda text: textwrap.dedent(text), _T, ["text"], "text")
_add("indent_text", "Indent every line by a prefix.",
     lambda text, prefix: textwrap.indent(text, prefix), {"text": _S, "prefix": _S}, ["text", "prefix"], "text")
_add("repeat_text", "Repeat text n times.", lambda text, n: text * max(0, n),
     {"text": _S, "n": _I}, ["text", "n"], "text")
_add("pad_left", "Left-pad text to a width with a fill char.",
     lambda text, width, fill=" ": text.rjust(width, fill[:1] or " "),
     {"text": _S, "width": _I, "fill": _S}, ["text", "width"], "text")
_add("pad_right", "Right-pad text to a width with a fill char.",
     lambda text, width, fill=" ": text.ljust(width, fill[:1] or " "),
     {"text": _S, "width": _I, "fill": _S}, ["text", "width"], "text")
_add("count_substring", "Count occurrences of a substring.",
     lambda text, sub: text.count(sub), {"text": _S, "sub": _S}, ["text", "sub"], "text")
_add("replace_substring", "Replace all occurrences of a substring.",
     lambda text, old, new: text.replace(old, new), {"text": _S, "old": _S, "new": _S},
     ["text", "old", "new"], "text")
_add("remove_punctuation", "Remove punctuation from text.",
     lambda text: re.sub(r"[^\w\s]", "", text), _T, ["text"], "text")
_add("count_vowels", "Count vowels in text.",
     lambda text: sum(text.lower().count(v) for v in "aeiou"), _T, ["text"], "text")
_add("unicode_name", "Name of the first character's Unicode code point.",
     lambda text: unicodedata.name(text[:1] or " "), _T, ["text"], "text", "unicode")
_add("ascii_only", "Strip non-ASCII characters.",
     lambda text: text.encode("ascii", "ignore").decode("ascii"), _T, ["text"], "text")

# --- regex (category: regex) -------------------------------------------------
_add("regex_findall", "Find all regex matches (JSON list).",
     lambda pattern, text: json.dumps(re.findall(pattern, text)),
     {"pattern": _S, "text": _S}, ["pattern", "text"], "regex")
_add("regex_match", "Whether the regex matches anywhere in the text.",
     lambda pattern, text: bool(re.search(pattern, text)),
     {"pattern": _S, "text": _S}, ["pattern", "text"], "regex")
_add("regex_replace", "Replace regex matches with a replacement.",
     lambda pattern, repl, text: re.sub(pattern, repl, text),
     {"pattern": _S, "repl": _S, "text": _S}, ["pattern", "repl", "text"], "regex")
_add("regex_split", "Split text by a regex (JSON list).",
     lambda pattern, text: json.dumps(re.split(pattern, text)),
     {"pattern": _S, "text": _S}, ["pattern", "text"], "regex")
_add("regex_groups", "First match's capture groups (JSON list).",
     lambda pattern, text: json.dumps(_regex_groups(pattern, text)),
     {"pattern": _S, "text": _S}, ["pattern", "text"], "regex")
_add("regex_escape", "Escape regex metacharacters in a string.",
     lambda text: re.escape(text), _T, ["text"], "regex")

# --- json / data (category: data) --------------------------------------------
_add("json_validate", "Report whether a string is valid JSON.",
     lambda text: "valid" if _try_json(text) else "invalid", _T, ["text"], "data", "json")
_add("json_pretty", "Pretty-print JSON with indentation.",
     lambda text: json.dumps(json.loads(text), indent=2, sort_keys=True), _T, ["text"], "data", "json")
_add("json_minify", "Minify JSON (no whitespace).",
     lambda text: json.dumps(json.loads(text), separators=(",", ":")), _T, ["text"], "data", "json")
_add("json_keys", "Top-level keys of a JSON object (JSON list).",
     lambda text: json.dumps(list(json.loads(text).keys())), _T, ["text"], "data", "json")
_add("json_get", "Get a dotted path from a JSON object.",
     lambda text, path: json.dumps(_dig(json.loads(text), path)),
     {"text": _S, "path": _S}, ["text", "path"], "data", "json")
_add("json_merge", "Shallow-merge two JSON objects.",
     lambda a, b: json.dumps({**json.loads(a), **json.loads(b)}),
     {"a": _S, "b": _S}, ["a", "b"], "data", "json")
_add("csv_to_json", "Convert CSV text (with header) to a JSON array of objects.",
     lambda text: _csv_to_json(text), _T, ["text"], "data", "csv")
_add("json_to_csv", "Convert a JSON array of objects to CSV.",
     lambda text: _json_to_csv(text), _T, ["text"], "data", "csv")
_add("count_json_items", "Count items in a JSON array or keys in an object.",
     lambda text: len(json.loads(text)), _T, ["text"], "data", "json")
_add("flatten_json", "Flatten a nested JSON object to dotted keys.",
     lambda text: json.dumps(_flatten(json.loads(text))), _T, ["text"], "data", "json")

# --- encoding (category: encoding) -------------------------------------------
_add("base64_encode", "Base64-encode text.",
     lambda text: base64.b64encode(text.encode()).decode(), _T, ["text"], "encoding")
_add("base64_decode", "Base64-decode text.",
     lambda text: base64.b64decode(text.encode()).decode("utf-8", "replace"), _T, ["text"], "encoding")
_add("base32_encode", "Base32-encode text.",
     lambda text: base64.b32encode(text.encode()).decode(), _T, ["text"], "encoding")
_add("base32_decode", "Base32-decode text.",
     lambda text: base64.b32decode(text.encode()).decode("utf-8", "replace"), _T, ["text"], "encoding")
_add("hex_encode", "Hex-encode text.", lambda text: text.encode().hex(), _T, ["text"], "encoding")
_add("hex_decode", "Hex-decode text.",
     lambda text: bytes.fromhex(text).decode("utf-8", "replace"), _T, ["text"], "encoding")
_add("url_encode", "Percent-encode a string for URLs.",
     lambda text: urllib.parse.quote(text), _T, ["text"], "encoding", "web")
_add("url_decode", "Decode a percent-encoded URL string.",
     lambda text: urllib.parse.unquote(text), _T, ["text"], "encoding", "web")
_add("html_escape", "Escape HTML special characters.", lambda text: html.escape(text), _T, ["text"], "encoding", "web")
_add("html_unescape", "Unescape HTML entities.", lambda text: html.unescape(text), _T, ["text"], "encoding", "web")
_add("rot13", "Apply the ROT13 cipher.",
     lambda text: text.translate(_ROT13), _T, ["text"], "encoding")
_add("ascii_codes", "Code points of each character (JSON list).",
     lambda text: json.dumps([ord(c) for c in text]), _T, ["text"], "encoding")
_add("url_parse", "Parse a URL into components (JSON).",
     lambda url: json.dumps(urllib.parse.urlparse(url)._asdict()), {"url": _S}, ["url"], "encoding", "web")
_add("query_to_json", "Parse a URL query string to JSON.",
     lambda query: json.dumps(dict(urllib.parse.parse_qsl(query))), {"query": _S}, ["query"], "encoding", "web")

# --- hashing (category: hashing) ---------------------------------------------
for _algo in ("md5", "sha1", "sha256", "sha512", "sha3_256", "blake2b"):
    _add(_algo, f"Compute the {_algo} hex digest of text.",
         (lambda a: (lambda text: hashlib.new(a, text.encode()).hexdigest()))(_algo),
         _T, ["text"], "hashing", "crypto")
_add("crc32", "Compute the CRC32 checksum of text.",
     lambda text: format(zlib.crc32(text.encode()) & 0xFFFFFFFF, "08x"), _T, ["text"], "hashing")
_add("hmac_sha256", "Compute an HMAC-SHA256 of text with a key.",
     lambda text, key: hmac.new(key.encode(), text.encode(), hashlib.sha256).hexdigest(),
     {"text": _S, "key": _S}, ["text", "key"], "hashing", "crypto")

# --- math / stats (category: math) -------------------------------------------
_NUMS = {"numbers": {"type": "array", "items": _N}}
_add("sum_numbers", "Sum a list of numbers.", lambda numbers: sum(numbers), _NUMS, ["numbers"], "math")
_add("mean", "Arithmetic mean of numbers.", lambda numbers: statistics.fmean(numbers), _NUMS, ["numbers"], "math", "stats")
_add("median", "Median of numbers.", lambda numbers: statistics.median(numbers), _NUMS, ["numbers"], "math", "stats")
_add("mode", "Most common value among numbers.", lambda numbers: statistics.mode(numbers), _NUMS, ["numbers"], "math", "stats")
_add("stdev", "Sample standard deviation.", lambda numbers: statistics.pstdev(numbers), _NUMS, ["numbers"], "math", "stats")
_add("variance", "Population variance.", lambda numbers: statistics.pvariance(numbers), _NUMS, ["numbers"], "math", "stats")
_add("min_number", "Minimum of numbers.", lambda numbers: min(numbers), _NUMS, ["numbers"], "math")
_add("max_number", "Maximum of numbers.", lambda numbers: max(numbers), _NUMS, ["numbers"], "math")
_add("range_number", "Range (max - min) of numbers.", lambda numbers: max(numbers) - min(numbers), _NUMS, ["numbers"], "math")
_add("gcd", "Greatest common divisor of two integers.", lambda a, b: math.gcd(a, b), {"a": _I, "b": _I}, ["a", "b"], "math")
_add("lcm", "Least common multiple of two integers.", lambda a, b: math.lcm(a, b), {"a": _I, "b": _I}, ["a", "b"], "math")
_add("factorial", "Factorial of a non-negative integer.", lambda n: math.factorial(n), {"n": _I}, ["n"], "math")
_add("is_prime", "Whether an integer is prime.", lambda n: _is_prime(n), {"n": _I}, ["n"], "math")
_add("fibonacci", "The nth Fibonacci number.", lambda n: _fib(n), {"n": _I}, ["n"], "math")
_add("round_number", "Round a number to n decimal places.",
     lambda x, ndigits=0: round(x, ndigits), {"x": _N, "ndigits": _I}, ["x"], "math")
_add("clamp", "Clamp x to the [lo, hi] range.",
     lambda x, lo, hi: max(lo, min(hi, x)), {"x": _N, "lo": _N, "hi": _N}, ["x", "lo", "hi"], "math")
_add("percent_of", "What percent a is of b.",
     lambda a, b: (a / b * 100) if b else 0, {"a": _N, "b": _N}, ["a", "b"], "math")
_add("power", "Raise base to an exponent.", lambda base, exp: math.pow(base, exp),
     {"base": _N, "exp": _N}, ["base", "exp"], "math")
_add("sqrt", "Square root of a number.", lambda x: math.sqrt(x), {"x": _N}, ["x"], "math")
_add("log", "Logarithm of x to an optional base (default e).",
     lambda x, base=math.e: math.log(x, base), {"x": _N, "base": _N}, ["x"], "math")
_add("hypotenuse", "Hypotenuse for legs a and b.", lambda a, b: math.hypot(a, b),
     {"a": _N, "b": _N}, ["a", "b"], "math")

# --- datetime (category: datetime) -------------------------------------------
_add("parse_date", "Parse an ISO date/time and echo it back as ISO.",
     lambda text: _dt.datetime.fromisoformat(text).isoformat(), _T, ["text"], "datetime")
_add("date_diff_days", "Whole days between two ISO dates (b - a).",
     lambda a, b: (_dt.date.fromisoformat(b) - _dt.date.fromisoformat(a)).days,
     {"a": _S, "b": _S}, ["a", "b"], "datetime")
_add("add_days", "Add days to an ISO date.",
     lambda date, days: (_dt.date.fromisoformat(date) + _dt.timedelta(days=days)).isoformat(),
     {"date": _S, "days": _I}, ["date", "days"], "datetime")
_add("weekday_name", "Weekday name of an ISO date.",
     lambda date: _dt.date.fromisoformat(date).strftime("%A"), {"date": _S}, ["date"], "datetime")
_add("to_unix", "Convert an ISO date/time to a Unix timestamp.",
     lambda text: int(_dt.datetime.fromisoformat(text).timestamp()), _T, ["text"], "datetime")
_add("from_unix", "Convert a Unix timestamp to an ISO date/time (UTC).",
     lambda ts: _dt.datetime.fromtimestamp(ts, _dt.timezone.utc).isoformat(), {"ts": _N}, ["ts"], "datetime")
_add("is_leap_year", "Whether a year is a leap year.",
     lambda year: (year % 4 == 0 and year % 100 != 0) or year % 400 == 0, {"year": _I}, ["year"], "datetime")
_add("days_in_month", "Number of days in a given year/month.",
     lambda year, month: _days_in_month(year, month), {"year": _I, "month": _I}, ["year", "month"], "datetime")
_add("iso_week", "ISO week number of an ISO date.",
     lambda date: _dt.date.fromisoformat(date).isocalendar()[1], {"date": _S}, ["date"], "datetime")
_add("format_date", "Reformat an ISO date with a strftime pattern.",
     lambda date, pattern: _dt.date.fromisoformat(date).strftime(pattern),
     {"date": _S, "pattern": _S}, ["date", "pattern"], "datetime")

# --- units / convert (category: units) ---------------------------------------
_add("c_to_f", "Celsius to Fahrenheit.", lambda c: c * 9 / 5 + 32, {"c": _N}, ["c"], "units")
_add("f_to_c", "Fahrenheit to Celsius.", lambda f: (f - 32) * 5 / 9, {"f": _N}, ["f"], "units")
_add("km_to_mi", "Kilometres to miles.", lambda km: km * 0.621371, {"km": _N}, ["km"], "units")
_add("mi_to_km", "Miles to kilometres.", lambda mi: mi / 0.621371, {"mi": _N}, ["mi"], "units")
_add("kg_to_lb", "Kilograms to pounds.", lambda kg: kg * 2.20462, {"kg": _N}, ["kg"], "units")
_add("lb_to_kg", "Pounds to kilograms.", lambda lb: lb / 2.20462, {"lb": _N}, ["lb"], "units")
_add("m_to_ft", "Metres to feet.", lambda m: m * 3.28084, {"m": _N}, ["m"], "units")
_add("ft_to_m", "Feet to metres.", lambda ft: ft / 3.28084, {"ft": _N}, ["ft"], "units")
_add("deg_to_rad", "Degrees to radians.", lambda deg: math.radians(deg), {"deg": _N}, ["deg"], "units")
_add("rad_to_deg", "Radians to degrees.", lambda rad: math.degrees(rad), {"rad": _N}, ["rad"], "units")
_add("bytes_to_human", "Human-readable size for a byte count.", lambda n: _human_bytes(n), {"n": _N}, ["n"], "units")
_add("number_to_roman", "Convert an integer (1-3999) to Roman numerals.",
     lambda n: _to_roman(n), {"n": _I}, ["n"], "units")
_add("roman_to_number", "Convert Roman numerals to an integer.",
     lambda text: _from_roman(text), _T, ["text"], "units")
_add("base_convert", "Convert an integer string from one base to another (2-36).",
     lambda value, from_base, to_base: _base_convert(value, from_base, to_base),
     {"value": _S, "from_base": _I, "to_base": _I}, ["value", "from_base", "to_base"], "units")

# --- collections / list (category: collections) ------------------------------
_LISTS = {"items": {"type": "array"}}
_add("sort_list", "Sort a JSON array.", lambda items: json.dumps(sorted(items, key=str)), _LISTS, ["items"], "collections")
_add("unique_list", "Unique items of a JSON array (order-preserving).",
     lambda items: json.dumps(_unique(items)), _LISTS, ["items"], "collections")
_add("reverse_list", "Reverse a JSON array.", lambda items: json.dumps(list(reversed(items))), _LISTS, ["items"], "collections")
_add("flatten_list", "Flatten a one-level-nested JSON array.",
     lambda items: json.dumps([x for sub in items for x in (sub if isinstance(sub, list) else [sub])]),
     _LISTS, ["items"], "collections")
_add("chunk_list", "Split a JSON array into chunks of size n.",
     lambda items, n: json.dumps([items[i:i + n] for i in range(0, len(items), max(1, n))]),
     {"items": {"type": "array"}, "n": _I}, ["items", "n"], "collections")
_add("count_frequency", "Frequency of each item in a JSON array (JSON object).",
     lambda items: json.dumps(_freq(items)), _LISTS, ["items"], "collections")
_add("length_of", "Length of a JSON array.", lambda items: len(items), _LISTS, ["items"], "collections")
_add("sort_lines", "Sort lines of text alphabetically.",
     lambda text: "\n".join(sorted(text.splitlines())), _T, ["text"], "collections", "text")
_add("unique_lines", "Remove duplicate lines (order-preserving).",
     lambda text: "\n".join(dict.fromkeys(text.splitlines())), _T, ["text"], "collections", "text")
_add("shuffle_list", "Shuffle a JSON array deterministically with a seed.",
     lambda items, seed=0: json.dumps(_shuffled(items, seed)),
     {"items": {"type": "array"}, "seed": _I}, ["items"], "collections")
_add("sample_list", "Sample k items from a JSON array deterministically with a seed.",
     lambda items, k, seed=0: json.dumps(random.Random(seed).sample(items, min(k, len(items)))),
     {"items": {"type": "array"}, "k": _I, "seed": _I}, ["items", "k"], "collections")

# --- random / generate (category: generate) ----------------------------------
_add("random_int", "Deterministic random int in [lo, hi] for a seed.",
     lambda lo, hi, seed=0: random.Random(seed).randint(lo, hi),
     {"lo": _I, "hi": _I, "seed": _I}, ["lo", "hi"], "generate")
_add("random_float", "Deterministic random float in [0,1) for a seed.",
     lambda seed=0: random.Random(seed).random(), {"seed": _I}, [], "generate")
_add("random_choice", "Deterministically pick one item from a JSON array for a seed.",
     lambda items, seed=0: json.dumps(random.Random(seed).choice(items)),
     {"items": {"type": "array"}, "seed": _I}, ["items"], "generate")
_add("random_string", "Deterministic random alphanumeric string of length n.",
     lambda n, seed=0: "".join(random.Random(seed).choices(_ALNUM, k=n)),
     {"n": _I, "seed": _I}, ["n"], "generate")
_add("uuid4", "Generate a random UUID4.", lambda: str(uuid.uuid4()), {}, [], "generate")
_add("password_gen", "Generate a strong password of length n (seeded).",
     lambda n=16, seed=0: "".join(random.Random(seed).choices(_PWCHARS, k=n)),
     {"n": _I, "seed": _I}, [], "generate")
_add("dice_roll", "Roll a d-sided die (seeded).",
     lambda sides=6, seed=0: random.Random(seed).randint(1, sides), {"sides": _I, "seed": _I}, [], "generate")
_add("lorem_ipsum", "Generate n words of lorem-ipsum text (seeded).",
     lambda n=20, seed=0: " ".join(random.Random(seed).choices(_LOREM, k=n)),
     {"n": _I, "seed": _I}, [], "generate")

# --- extract / parse (category: extract) -------------------------------------
_add("extract_emails", "Extract email addresses from text (JSON list).",
     lambda text: json.dumps(re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)), _T, ["text"], "extract")
_add("extract_urls", "Extract URLs from text (JSON list).",
     lambda text: json.dumps(re.findall(r"https?://[^\s)]+", text)), _T, ["text"], "extract", "web")
_add("extract_numbers", "Extract numbers from text (JSON list).",
     lambda text: json.dumps(re.findall(r"-?\d+\.?\d*", text)), _T, ["text"], "extract")
_add("extract_hashtags", "Extract #hashtags from text (JSON list).",
     lambda text: json.dumps(re.findall(r"#\w+", text)), _T, ["text"], "extract")
_add("extract_mentions", "Extract @mentions from text (JSON list).",
     lambda text: json.dumps(re.findall(r"@\w+", text)), _T, ["text"], "extract")
_add("strip_html_tags", "Remove HTML tags from text.",
     lambda text: re.sub(r"<[^>]+>", "", text), _T, ["text"], "extract", "web")

# --- code / text-dev (category: code) ----------------------------------------
_add("count_loc", "Count non-blank lines of code.",
     lambda text: sum(1 for line in text.splitlines() if line.strip()), _T, ["text"], "code")
_add("extract_python_imports", "Extract imported modules from Python source (JSON list).",
     lambda text: json.dumps(sorted(set(re.findall(r"^\s*(?:import|from)\s+([\w.]+)", text, re.M)))),
     _T, ["text"], "code")
_add("extract_function_names", "Extract Python function names (JSON list).",
     lambda text: json.dumps(re.findall(r"def\s+(\w+)\s*\(", text)), _T, ["text"], "code")
_add("count_todos", "Count TODO/FIXME markers in text.",
     lambda text: len(re.findall(r"\b(?:TODO|FIXME|XXX)\b", text)), _T, ["text"], "code")
_add("indent_to_spaces", "Convert leading tabs to spaces.",
     lambda text, width=4: "\n".join(re.sub(r"^\t+", lambda m: " " * (width * len(m.group())), ln)
                                      for ln in text.splitlines()),
     {"text": _S, "width": _I}, ["text"], "code")
_add("diff_lines", "Lines added/removed between two texts (JSON object).",
     lambda a, b: _line_diff(a, b), {"a": _S, "b": _S}, ["a", "b"], "code")

# --- color (category: color) -------------------------------------------------
_add("hex_to_rgb", "Convert a #RRGGBB hex color to an RGB JSON list.",
     lambda hex: json.dumps(_hex_to_rgb(hex)), {"hex": _S}, ["hex"], "color")
_add("rgb_to_hex", "Convert r,g,b (0-255) to a #RRGGBB hex color.",
     lambda r, g, b: "#%02x%02x%02x" % (int(r), int(g), int(b)),
     {"r": _I, "g": _I, "b": _I}, ["r", "g", "b"], "color")
_add("rgb_to_hsl", "Convert r,g,b (0-255) to HSL (JSON list).",
     lambda r, g, b: json.dumps([round(x, 3) for x in colorsys.rgb_to_hls(r / 255, g / 255, b / 255)]),
     {"r": _I, "g": _I, "b": _I}, ["r", "g", "b"], "color")


# --- gated network pack ------------------------------------------------------
def _http_get(url: str, max_bytes: int = 100_000) -> str:
    if not url.lower().startswith(("http://", "https://")):
        return "error: only http/https URLs are allowed"
    with urllib.request.urlopen(url, timeout=15) as resp:  # noqa: S310 - scheme checked
        return resp.read(max_bytes).decode("utf-8", "replace")


def _http_status(url: str) -> str:
    if not url.lower().startswith(("http://", "https://")):
        return "error: only http/https URLs are allowed"
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - scheme checked
        return str(resp.status)


def _fetch_json(url: str) -> str:
    return json.dumps(json.loads(_http_get(url)))


def network_specs() -> list[ToolSpec]:
    """Read-only network tools — registered only when RIPTIDE_ENABLE_NETWORK=1."""
    specs: list[ToolSpec] = []
    n = lambda name, desc, fn, props, req, *tags: specs.append(  # noqa: E731
        _spec(name, desc, _safe(fn), props, req, "network", list(tags)))
    n("http_get", "Fetch the text body of an http(s) URL (size-capped).", _http_get,
      {"url": _S, "max_bytes": _I}, ["url"], "web")
    n("http_status", "Get the HTTP status code for a URL (HEAD).", _http_status, {"url": _S}, ["url"], "web")
    n("fetch_json", "Fetch and parse JSON from an http(s) URL.", _fetch_json, {"url": _S}, ["url"], "web")
    return specs


def library_specs() -> list[ToolSpec]:
    """All always-on library tools, plus the network pack when enabled."""
    specs = list(_SPECS)
    if os.getenv("RIPTIDE_ENABLE_NETWORK") == "1":
        specs += network_specs()
    return specs


# --- internal helpers --------------------------------------------------------
def _regex_groups(pattern: str, text: str) -> list[Any]:
    m = re.search(pattern, text)
    return list(m.groups()) if m else []


def _try_json(text: str) -> bool:
    try:
        json.loads(text)
        return True
    except (ValueError, TypeError):
        return False


def _unique(items: list[Any]) -> list[Any]:
    seen: set[str] = set()
    out: list[Any] = []
    for x in items:
        k = json.dumps(x, sort_keys=True)
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


def _dig(obj: Any, path: str) -> Any:
    for part in path.split("."):
        obj = obj[int(part)] if isinstance(obj, list) else obj[part]
    return obj


def _flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(_flatten(v, f"{prefix}{k}."))
    else:
        out[prefix.rstrip(".")] = obj
    return out


def _csv_to_json(text: str) -> str:
    import csv
    rows = list(csv.DictReader(io.StringIO(text)))
    return json.dumps(rows)


def _json_to_csv(text: str) -> str:
    import csv
    data = json.loads(text)
    if not data:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(data[0].keys()))
    writer.writeheader()
    writer.writerows(data)
    return buf.getvalue().strip()


def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    for i in range(2, int(n ** 0.5) + 1):
        if n % i == 0:
            return False
    return True


def _fib(n: int) -> int:
    a, b = 0, 1
    for _ in range(max(0, n)):
        a, b = b, a + b
    return a


def _days_in_month(year: int, month: int) -> int:
    import calendar
    return calendar.monthrange(year, month)[1]


def _human_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if abs(n) < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}EB"


_ROMAN = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
          (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def _to_roman(n: int) -> str:
    if not 0 < n < 4000:
        raise ValueError("number out of range (1-3999)")
    out = []
    for value, sym in _ROMAN:
        while n >= value:
            out.append(sym)
            n -= value
    return "".join(out)


def _from_roman(text: str) -> int:
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total, prev = 0, 0
    for ch in reversed(text.upper()):
        v = vals[ch]
        total += -v if v < prev else v
        prev = max(prev, v)
    return total


def _base_convert(value: str, from_base: int, to_base: int) -> str:
    n = int(value, from_base)
    if n == 0:
        return "0"
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = []
    while n:
        out.append(digits[n % to_base])
        n //= to_base
    return "".join(reversed(out))


def _freq(items: list[Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for x in items:
        out[str(x)] = out.get(str(x), 0) + 1
    return out


def _shuffled(items: list[Any], seed: int) -> list[Any]:
    out = list(items)
    random.Random(seed).shuffle(out)
    return out


def _line_diff(a: str, b: str) -> str:
    sa, sb = set(a.splitlines()), set(b.splitlines())
    return json.dumps({"added": sorted(sb - sa), "removed": sorted(sa - sb)})


def _hex_to_rgb(hex_color: str) -> list[int]:
    h = hex_color.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]
