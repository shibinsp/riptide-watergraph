"""Self-improvement v0.18.0: scorers + proposers + measured prompt optimization + CLI."""

from __future__ import annotations

import asyncio
import json

import pytest

from riptide_watergraph.cli import main
from riptide_watergraph.interfaces.gateway import CompletionResult
from riptide_watergraph.interfaces.optimizer import Example
from riptide_watergraph.optimize import (
    ExactMatchScorer,
    LLMPromptProposer,
    SubstringScorer,
    TemplateProposer,
    optimize_prompt,
)


def _run(coro):
    return asyncio.run(coro)


# --------------------------- scorers ---------------------------

def test_scorers():
    assert SubstringScorer().score("the answer is 42 today", "42") == 1.0
    assert SubstringScorer().score("nope", "42") == 0.0
    assert ExactMatchScorer().score("  Hello   World ", "hello world") == 1.0
    assert ExactMatchScorer().score("hello", "world") == 0.0


# --------------------------- proposers ---------------------------

def test_template_proposer_is_deterministic():
    variants = _run(TemplateProposer().propose("Base.", [], n=3))
    assert len(variants) == 3 and all(v.startswith("Base.") for v in variants)
    assert variants[0] != variants[1]  # distinct strategy hints


def test_llm_proposer_collects_nonempty(make_gateway):
    seen = {"i": 0}

    def responder(system, user):
        seen["i"] += 1
        return CompletionResult(content="" if seen["i"] == 1 else f"rewrite {seen['i']}")
    gw = make_gateway(responder)
    variants = _run(LLMPromptProposer(gw, model="demo").propose(
        "p", [Example(input="x", expected="y")], n=3))
    assert variants == ["rewrite 2", "rewrite 3"]  # the empty reply is dropped


# --------------------------- optimizer (keep only gains) ---------------------------

def test_optimize_adopts_a_strictly_better_variant():
    examples = [Example(input="q", expected="step")]
    # The runner's output depends on the prompt: only the "step by step" variant matches.
    def runner(prompt, inp):
        return "step" if "step by step" in prompt else "base"
    result = optimize_prompt("Answer.", examples, runner=runner,
                             proposer=TemplateProposer(), scorer=SubstringScorer(), candidates=5)
    assert result.base_score == 0.0
    assert result.improved is True and result.best_score == 1.0
    assert "step by step" in result.best_prompt
    assert len(result.candidates) == 5


def test_optimize_keeps_base_when_nothing_improves():
    examples = [Example(input="q", expected="x")]
    result = optimize_prompt("Answer.", examples, runner=lambda p, i: "always same",
                             proposer=TemplateProposer(), scorer=SubstringScorer(), candidates=3)
    assert result.improved is False and result.best_prompt == "Answer."


# --------------------------- service + CLI ---------------------------

@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RIPTIDE_WATERGRAPH_DISABLE_TRACING", "1")
    return tmp_path


def test_improve_prompt_service_offline(env):
    from riptide_watergraph.service import improve_prompt
    result = improve_prompt("Solve the task.", [Example(input="2+2", expected="4")],
                            offline=True, candidates=2)
    assert result.base_prompt == "Solve the task." and 0.0 <= result.best_score <= 1.0


def test_cli_improve_offline_with_out(env, tmp_path, capsys):
    examples = tmp_path / "ex.json"
    examples.write_text(json.dumps([{"input": "2 + 2", "expected": "4"}]), encoding="utf-8")
    out = tmp_path / "best.txt"
    code = main(["improve", "Answer the question.", "--examples", str(examples),
                 "--offline", "--candidates", "2", "--out", str(out)])
    assert code == 0
    assert "BEST PROMPT" in capsys.readouterr().out
    assert out.read_text(encoding="utf-8")  # the improved prompt was written


def test_cli_improve_offline_no_out(env, tmp_path, capsys):
    examples = tmp_path / "ex.json"
    examples.write_text(json.dumps([{"input": "q", "expected": "a"}]), encoding="utf-8")
    assert main(["improve", "Base instruction.", "--examples", str(examples), "--offline"]) == 0
    assert "base score" in capsys.readouterr().out
