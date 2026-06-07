"""Environment seam v0.21.0: Gym-like env + rollout + registry + service + CLI."""

from __future__ import annotations

import pytest

from riptide_watergraph.cli import main
from riptide_watergraph.environments import (
    GuessingGameEnv,
    make_environment,
    rollout,
)
from riptide_watergraph.environments.guessing import _first_int


# --------------------------- the toy environment ---------------------------

def test_guessing_env_hints_and_win():
    env = GuessingGameEnv(target=42, low=1, high=100)
    assert "between 1 and 100" in env.reset().text
    low = env.step("I guess 10")
    assert low.info["hint"] == "higher" and low.reward == 0.0 and not low.done
    high = env.step("maybe 90")
    assert high.info["hint"] == "lower"
    win = env.step("42")
    assert win.reward == 1.0 and win.done and win.text == "Correct!"


def test_guessing_env_non_number_and_timeout():
    env = GuessingGameEnv(target=5, low=1, high=10, max_turns=1)
    obs = env.step("no idea")  # unparseable + last allowed turn
    assert obs.text == "Please reply with a number." and obs.done is True


def test_first_int():
    assert _first_int("guess 17 please") == 17
    assert _first_int("nope") is None


# --------------------------- rollout ---------------------------

def test_rollout_binary_search_solves():
    env = GuessingGameEnv(target=37, low=1, high=100)
    state = {"low": 1, "high": 100}

    def policy(observation: str) -> str:
        if "higher" in observation:
            state["low"] = state["mid"] + 1
        elif "lower" in observation:
            state["high"] = state["mid"] - 1
        state["mid"] = (state["low"] + state["high"]) // 2
        return str(state["mid"])

    roll = rollout(env, policy, max_steps=20)
    assert roll.total_reward == 1.0
    assert roll.transitions[-1].done is True


def test_rollout_stops_at_max_steps():
    env = GuessingGameEnv(target=1, low=1, high=100, max_turns=99)
    roll = rollout(env, lambda obs: "50", max_steps=3)  # never guesses right
    assert roll.steps == 3 and roll.total_reward == 0.0


# --------------------------- registry ---------------------------

def test_make_environment_known_and_unknown():
    assert isinstance(make_environment("guessing"), GuessingGameEnv)
    with pytest.raises(ValueError, match="unknown environment"):
        make_environment("nope")


# --------------------------- service + CLI ---------------------------

@pytest.fixture
def env_vars(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RIPTIDE_WATERGRAPH_DISABLE_TRACING", "1")
    return tmp_path


def test_run_in_environment_offline(env_vars):
    from riptide_watergraph.service import run_in_environment
    roll = run_in_environment("guessing", max_steps=2, offline=True)
    assert roll.steps <= 2 and len(roll.transitions) == roll.steps


def test_cli_env_offline_and_unknown(env_vars, capsys):
    assert main(["env", "guessing", "--max-steps", "2", "--offline"]) == 0
    assert "environment 'guessing'" in capsys.readouterr().out
    assert main(["env", "bogus", "--offline"]) == 1
    assert "unknown environment" in capsys.readouterr().out
