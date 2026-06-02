"""Edge-branch coverage for tools/library.py helpers + the gated network pack.

The main happy paths are covered by test_library.py's invoke-every-spec sweep; here we hit
the remaining conditional branches directly, and exercise the network handlers with a fake
``urlopen`` (no real HTTP).
"""

from __future__ import annotations

import urllib.request

import pytest

from riptide_watergraph.tools import library as lib


def test_helper_edge_branches():
    assert lib._json_to_csv("[]") == ""                       # empty data
    assert lib._is_prime(1) is False                          # n < 2
    assert lib._is_prime(4) is False                          # composite divisor
    assert lib._is_prime(7) is True
    assert lib._human_bytes(2 ** 60).endswith("EB")           # overflow past PB
    assert lib._base_convert("0", 10, 16) == "0"              # zero short-circuit
    assert lib._levenshtein("", "abc") == 3                   # empty first string
    assert lib._luhn("abc") is False                          # no digits
    assert lib._luhn("59") is True                            # doubled digit > 9 path
    assert lib._pw_strength("Abcdef1!") >= 4                  # special-char branch
    assert lib._quantile([], 0.5) == 0.0                      # empty list
    assert lib._zscore(1.0, [1.0]) == 0.0                     # < 2 samples
    assert lib._annuity(100.0, 0.0, 12) == pytest.approx(8.33, abs=0.01)  # zero-rate
    assert lib._add_months("2026-01-31", 1) == "2026-02-28"   # day clamp
    assert lib._end_of_month("2026-02-10") == "2026-02-28"
    assert lib._age("2000-06-05", "2026-06-03") == 25         # birthday not yet reached


def test_to_roman_out_of_range():
    with pytest.raises(ValueError):
        lib._to_roman(5000)


def test_num_to_words_branches():
    assert lib._num_to_words(5) == "five"
    assert lib._num_to_words(25) == "twenty-five"
    assert lib._num_to_words(125) == "one hundred twenty-five"
    assert lib._num_to_words(1000) == "out of range (0-999)"


# ---------- gated network pack (fake urlopen) ----------

class _FakeResp:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, n=None):
        return b'{"ok": true}'


def test_network_handlers(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _FakeResp())
    assert lib._http_get("http://example.com") == '{"ok": true}'
    assert lib._http_status("http://example.com") == "200"
    assert lib._fetch_json("http://example.com") == '{"ok": true}'
    # scheme guard
    assert "only http" in lib._http_get("ftp://x")
    assert "only http" in lib._http_status("ftp://x")


def test_network_specs_and_gated_registration(monkeypatch):
    specs = lib.network_specs()
    assert {s.name for s in specs} == {"http_get", "http_status", "fetch_json"}
    monkeypatch.setenv("RIPTIDE_ENABLE_NETWORK", "1")
    names = {s.name for s in lib.library_specs()}
    assert {"http_get", "fetch_json"} <= names  # network pack appended when enabled
