"""Deliberate reasoning v0.17.0: verifiers + verified best-of-N + confidence + CLI."""

from __future__ import annotations

import asyncio
import importlib
import json

import pytest

from riptide_watergraph.cli import main
from riptide_watergraph.interfaces.gateway import CompletionResult
from riptide_watergraph.reasoning import (
    Candidate,
    DeliberationResult,
    HeuristicVerifier,
    LLMVerifier,
    deliberate,
)
from riptide_watergraph.reasoning.verifier import _parse_verdict


def _run(coro):
    return asyncio.run(coro)


# --------------------------- verifiers ---------------------------

def test_heuristic_verifier_scores_overlap_and_empty():
    v = HeuristicVerifier()
    assert _run(v.score("about water cycles", "")).score == 0.0
    on = _run(v.score("about water cycles", "the water cycle moves water")).score
    off = _run(v.score("about water cycles", "bananas")).score
    assert on > off  # task/answer overlap raises the score


def test_llm_verifier_parses_score(make_gateway):
    gw = make_gateway(lambda s, u: CompletionResult(content='{"score": 0.9, "reason": "good"}'))
    verdict = _run(LLMVerifier(gw, model="demo").score("t", "a"))
    assert verdict.score == 0.9 and verdict.reason == "good"


def test_parse_verdict_variants():
    assert _parse_verdict(None).score == 0.0
    assert _parse_verdict("not json").score == 0.0
    assert _parse_verdict(json.dumps({"reason": "x"})).score == 0.0  # no score key
    # clamps out-of-range + tolerates a code fence
    assert _parse_verdict("```json\n{\"score\": 5}\n```").score == 1.0
    assert _parse_verdict(json.dumps({"score": -2})).score == 0.0


# --------------------------- deliberation (best-of-N) ---------------------------

def test_deliberate_picks_highest_scoring_candidate(make_gateway):
    # The "stepwise" style answers on-topic (high overlap); others go off-topic.
    def responder(system, user):
        good = "step by step" in system
        return CompletionResult(content="water cycle facts" if good else "unrelated noise")
    gw = make_gateway(responder)
    result = _run(deliberate("tell me about the water cycle", gateway=gw, model="demo",
                             verifier=HeuristicVerifier(), samples=3))
    assert isinstance(result, DeliberationResult)
    assert result.answer == "water cycle facts"  # best-of-N selected the on-topic candidate
    assert result.candidates[0].score >= result.candidates[-1].score  # ranked
    assert 0.0 <= result.confidence <= 1.0


def test_deliberate_single_sample_full_agreement(make_gateway):
    gw = make_gateway(lambda s, u: CompletionResult(content="the one answer"))
    result = _run(deliberate("q", gateway=gw, model="demo", verifier=HeuristicVerifier(),
                             samples=1))
    assert len(result.candidates) == 1 and result.confidence > 0  # agreement = 1.0


def test_deliberation_result_confident_threshold():
    r = DeliberationResult(task="t", answer="a", score=0.8, confidence=0.7,
                           candidates=[Candidate(style="s", answer="a", score=0.8)])
    assert r.confident() is True
    assert r.confident(threshold=0.9) is False


# --------------------------- service + CLI ---------------------------

@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RIPTIDE_WATERGRAPH_DISABLE_TRACING", "1")
    return tmp_path


def test_deliberate_task_offline(env):
    from riptide_watergraph.service import deliberate_task
    result = deliberate_task("compute 21 * 2", samples=2, offline=True)
    assert isinstance(result, DeliberationResult) and len(result.candidates) == 2


def test_cli_deliberate_offline(env, capsys):
    assert main(["deliberate", "compute 21 * 2", "--samples", "2", "--offline"]) == 0
    assert "BEST" in capsys.readouterr().out


def test_cli_deliberate_low_confidence_branch(env, monkeypatch, capsys):
    """A low-confidence result prints the escalation hint."""
    climod = importlib.import_module("riptide_watergraph.cli")

    def fake(task, *, samples, offline):
        return DeliberationResult(task=task, answer="maybe", score=0.3, confidence=0.2,
                                  candidates=[Candidate(style="a", answer="maybe", score=0.3),
                                              Candidate(style="b", answer="other", score=0.1)])
    monkeypatch.setattr(climod, "deliberate_task", fake)
    assert main(["deliberate", "x", "--offline"]) == 0
    assert "low confidence" in capsys.readouterr().out
