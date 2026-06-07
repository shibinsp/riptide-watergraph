"""Autonomy v0.19.0: goal proposers + journal + bounded loop + service + CLI."""

from __future__ import annotations

import asyncio
import json

import pytest

from riptide_watergraph.autonomy import (
    Journal,
    LLMGoalProposer,
    TemplateGoalProposer,
    run_autonomous,
)
from riptide_watergraph.autonomy.proposer import _parse_goals
from riptide_watergraph.cli import main
from riptide_watergraph.interfaces.autonomy import GoalProposer, JournalEntry
from riptide_watergraph.interfaces.gateway import CompletionResult


def _run(coro):
    return asyncio.run(coro)


# --------------------------- proposers ---------------------------

def test_template_proposer_opens_then_refines():
    p = TemplateGoalProposer()
    opening = _run(p.propose("build a thing", []))
    assert len(opening) == 2
    follow = _run(p.propose("build a thing", [JournalEntry(goal="g", result="r")]))
    assert len(follow) == 1  # refinement once work has started


def test_llm_proposer_parses_goals(make_gateway):
    gw = make_gateway(lambda s, u: CompletionResult(content='["do A", "do B"]'))
    goals = _run(LLMGoalProposer(gw, model="demo").propose("m", []))
    assert [g.description for g in goals] == ["do A", "do B"]


def test_parse_goals_variants():
    assert _parse_goals(None) == []
    assert _parse_goals("not json") == []
    assert _parse_goals(json.dumps({"a": 1})) == []  # not a list
    fenced = "```json\n" + json.dumps(["keep", "", 5, "also"]) + "\n```"
    assert _parse_goals(fenced) == ["keep", "also"]  # blanks + non-strings dropped


# --------------------------- journal ---------------------------

def test_journal_roundtrip_and_recovery(tmp_path):
    j = Journal(tmp_path / "sub" / "journal.json")
    assert j.entries() == [] and len(j) == 0
    j.append(JournalEntry(goal="g1", result="r1"))
    j.append(JournalEntry(goal="g2", result="r2"))
    assert len(Journal(tmp_path / "sub" / "journal.json")) == 2  # reloaded from disk
    assert Journal(tmp_path / "missing.json").entries() == []
    (tmp_path / "corrupt.json").write_text("{bad", encoding="utf-8")
    assert Journal(tmp_path / "corrupt.json").entries() == []


# --------------------------- bounded loop ---------------------------

class _EmptyProposer(GoalProposer):
    async def propose(self, mission, history):
        return []


def test_loop_stops_with_no_goals(tmp_path):
    report = run_autonomous("m", executor=lambda d: "x", proposer=_EmptyProposer(),
                            journal=Journal(tmp_path / "j.json"), max_steps=3)
    assert report.steps == 0 and report.entries == []


def test_loop_re_proposes_when_queue_drains(tmp_path):
    # TemplateGoalProposer opens with 2 goals; with max_steps=3 the queue drains and refills.
    report = run_autonomous("explore", executor=lambda d: f"did:{d[:6]}",
                            proposer=TemplateGoalProposer(),
                            journal=Journal(tmp_path / "j.json"), max_steps=3)
    assert report.steps == 3 and len(report.entries) == 3


def test_loop_respects_max_steps_cap(tmp_path):
    report = run_autonomous("explore", executor=lambda d: "ok",
                            proposer=TemplateGoalProposer(),
                            journal=Journal(tmp_path / "j.json"), max_steps=1)
    assert report.steps == 1  # stopped at the cap before the queue drained


# --------------------------- service + CLI ---------------------------

@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CHECKPOINT_PATH", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("RIPTIDE_WATERGRAPH_DISABLE_TRACING", "1")
    return tmp_path


def test_run_autonomous_mission_offline(env):
    from riptide_watergraph.service import run_autonomous_mission
    report = run_autonomous_mission("summarize water facts", max_steps=2, offline=True)
    assert report.steps == 2 and len(report.entries) == 2


def test_cli_auto_offline(env, capsys):
    assert main(["auto", "research the water cycle", "--max-steps", "2", "--offline"]) == 0
    assert "autonomous run: 2 step" in capsys.readouterr().out
