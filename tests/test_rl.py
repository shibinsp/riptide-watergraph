"""Reward/RL v0.22.0: reward models + UCB bandit + strategy learning + service + CLI."""

from __future__ import annotations

import asyncio
import json

import pytest

from riptide_watergraph.cli import main
from riptide_watergraph.interfaces.gateway import CompletionResult
from riptide_watergraph.rl import (
    Bandit,
    HeuristicRewardModel,
    LLMRewardModel,
    optimize_strategy,
)
from riptide_watergraph.rl.reward import _parse_reward


def _run(coro):
    return asyncio.run(coro)


# --------------------------- reward models ---------------------------

def test_heuristic_reward_rewards_overlap():
    rm = HeuristicRewardModel()
    assert _run(rm.reward("water cycle facts", "")) == 0.0
    on = _run(rm.reward("water cycle facts", "the water cycle moves water"))
    off = _run(rm.reward("water cycle facts", "bananas"))
    assert on > off


def test_llm_reward_parses(make_gateway):
    gw = make_gateway(lambda s, u: CompletionResult(content='{"reward": 0.8}'))
    assert _run(LLMRewardModel(gw, model="demo").reward("t", "a")) == 0.8


def test_parse_reward_variants():
    assert _parse_reward(None) == 0.0
    assert _parse_reward("nope") == 0.0
    assert _parse_reward("```json\n0.7\n```") == 0.7        # bare number, fenced
    assert _parse_reward(json.dumps({"reward": 5})) == 1.0   # clamped
    assert _parse_reward(json.dumps({})) == 0.0              # dict without a reward key
    assert _parse_reward(json.dumps({"reward": "x"})) == 0.0  # unparseable value


# --------------------------- UCB bandit ---------------------------

def test_bandit_requires_arms():
    with pytest.raises(ValueError, match="at least one arm"):
        Bandit([])


def test_bandit_explores_then_exploits():
    b = Bandit(["a", "b"])
    assert b.select() == "a"  # untried first
    b.update("a", 1.0)
    assert b.select() == "b"  # the other untried arm
    b.update("b", 0.0)
    # both tried once; UCB now favors the higher-mean "a"
    assert b.select() == "a"
    assert b.best() == "a"


# --------------------------- strategy learning ---------------------------

def test_optimize_strategy_learns_best_arm():
    # "good" answers overlap the task; "bad" don't, so the reward model separates them.
    def runner(arm, task):
        return "water cycle rain clouds" if arm == "good" else "zzz"
    report = optimize_strategy("describe the water cycle", ["good", "bad"],
                               runner=runner, reward_model=HeuristicRewardModel(), rounds=6)
    assert report.best == "good"
    by_arm = {s.arm: s for s in report.arms}
    assert by_arm["good"].mean_reward > by_arm["bad"].mean_reward
    assert sum(s.pulls for s in report.arms) == 6


# --------------------------- service + CLI ---------------------------

@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RIPTIDE_WATERGRAPH_DISABLE_TRACING", "1")
    return tmp_path


def test_optimize_strategy_for_task_offline(env):
    from riptide_watergraph.service import optimize_strategy_for_task
    report = optimize_strategy_for_task("compute 21 * 2", rounds=6, offline=True)
    assert report.best in {s.arm for s in report.arms}
    assert sum(s.pulls for s in report.arms) == 6


def test_cli_rl_offline(env, capsys):
    assert main(["rl", "summarize the water cycle", "--rounds", "6", "--offline"]) == 0
    assert "BEST STRATEGY" in capsys.readouterr().out
