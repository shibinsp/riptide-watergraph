"""SkillForge v0.15.0: self-authored skills — synthesis, forge, store, verify, node, CLI."""

from __future__ import annotations

import json

import pytest

from riptide_watergraph.cli import main
from riptide_watergraph.config import get_settings
from riptide_watergraph.graph.nodes import GraphContext, make_skill_forge
from riptide_watergraph.interfaces.gateway import CompletionResult
from riptide_watergraph.interfaces.skill import Skill, SkillStore, SkillSynthesizer, Trajectory
from riptide_watergraph.service import build_components
from riptide_watergraph.skills import (
    JsonFileSkillStore,
    LLMSkillSynthesizer,
    skill_to_spec,
    verify_skill,
)
from riptide_watergraph.skills.forge import render_template
from riptide_watergraph.skills.synthesis import _parse_skill
from riptide_watergraph.swarm import HeuristicSwarmComposer
from riptide_watergraph.tools import default_registry

_SKILL = Skill(
    name="greet",
    description="Greet someone by name.",
    parameters={"type": "object", "properties": {"who": {"type": "string"}}},
    template="Say hello to {who}.",
    tags=["social"],
)


# --------------------------- forge / render_template ---------------------------

def test_render_template_substitutes_and_leaves_unknown():
    assert render_template("Hi {who} from {missing}", {"who": "Sam"}) == "Hi Sam from {missing}"


async def test_skill_to_spec_handler_runs_through_gateway(make_gateway):
    gw = make_gateway(lambda sys, user: CompletionResult(content=f"<<{user}>>"))
    spec = skill_to_spec(_SKILL, gateway=gw, model="demo")
    assert spec.name == "skill.greet"
    assert spec.category == "skill" and "skill" in spec.tags and "social" in spec.tags
    out = await spec.handler(who="Sam")
    assert out == "<<Say hello to Sam.>>"


def test_skill_to_spec_handler_empty_content(make_gateway):
    import asyncio
    gw = make_gateway(lambda sys, user: CompletionResult(content=None))
    spec = skill_to_spec(_SKILL, gateway=gw, model="demo")
    assert asyncio.run(spec.handler(who="x")) == ""


# --------------------------- synthesis ---------------------------

def _skill_json() -> str:
    return json.dumps({
        "name": "summarize_text",
        "description": "Summarize text in one line.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}}},
        "template": "Summarize: {text}",
        "tags": ["text"],
    })


async def test_synthesizer_distills_on_success(make_gateway):
    gw = make_gateway(lambda sys, user: CompletionResult(content=_skill_json()))
    syn = LLMSkillSynthesizer(gw, model="demo")
    traj = Trajectory(task="summarize a doc", results=[{"subtask": "s", "output": "o"}],
                      success=True, session_id="sess1")
    skill = await syn.synthesize(traj)
    assert skill is not None
    assert skill.name == "summarize_text" and skill.provenance == "sess1"


async def test_synthesizer_skips_failed_run(make_gateway):
    gw = make_gateway(lambda sys, user: CompletionResult(content=_skill_json()))
    syn = LLMSkillSynthesizer(gw, model="demo")
    assert await syn.synthesize(Trajectory(task="t", success=False)) is None


def test_parse_skill_variants():
    traj = Trajectory(task="a-task-with-a-fairly-long-name", success=True)
    # no content / non-JSON / missing fields -> None
    assert _parse_skill(None, traj) is None
    assert _parse_skill("not json", traj) is None
    assert _parse_skill(json.dumps({"name": "x"}), traj) is None  # no template
    assert _parse_skill(json.dumps({"template": "t"}), traj) is None  # no name
    # fenced JSON + parameters-not-a-dict falls back to a default object schema
    fenced = "```json\n" + json.dumps({"name": "n", "template": "do {a}", "parameters": "bad"}) + "\n```"
    skill = _parse_skill(fenced, traj)
    assert skill is not None and skill.parameters == {"type": "object", "properties": {}}
    assert skill.description == "n"  # falls back to the name
    assert skill.provenance == traj.task[:48]  # no session id -> task prefix


# --------------------------- store ---------------------------

def test_store_roundtrip_and_missing_dir(tmp_path):
    store = JsonFileSkillStore(str(tmp_path / "skills"))
    assert store.load_all() == []  # directory does not exist yet
    store.save(_SKILL)
    loaded = store.load_all()
    assert len(loaded) == 1 and loaded[0].name == "greet"


def test_store_slugs_unsafe_names(tmp_path):
    store = JsonFileSkillStore(str(tmp_path))
    store.save(Skill(name="weird/Name!!", description="d", template="t",
                     parameters={"type": "object", "properties": {}}))
    assert (tmp_path / "weird_name_.json").exists()


# --------------------------- verify ---------------------------

def test_verify_rejects_structural_problems(make_gateway):
    gw = make_gateway(lambda sys, user: CompletionResult(content="ok"))
    assert verify_skill(Skill(name=" ", description="d", template="t",
                              parameters={"type": "object"}), gateway=gw, model="m")[0] is False
    assert verify_skill(Skill(name="n", description="d", template=" ",
                              parameters={"type": "object"}), gateway=gw, model="m")[0] is False
    bad = Skill(name="n", description="d", template="t", parameters={"type": "array"})
    assert verify_skill(bad, gateway=gw, model="m")[0] is False


def test_verify_smoke_ok_and_skipped(make_gateway):
    gw = make_gateway(lambda sys, user: CompletionResult(content="ok"))
    assert verify_skill(_SKILL, gateway=gw, model="m") == (True, "")
    assert verify_skill(_SKILL, gateway=gw, model="m", smoke=False) == (True, "")


def test_verify_smoke_failure(make_gateway):
    def boom(sys, user):
        raise RuntimeError("nope")
    gw = make_gateway(boom)
    ok, reason = verify_skill(_SKILL, gateway=gw, model="m")
    assert ok is False and "smoke invocation failed" in reason


# --------------------------- graph node ---------------------------

class _StubSynth(SkillSynthesizer):
    def __init__(self, skill):
        self.skill = skill

    async def synthesize(self, trajectory):
        return self.skill


class _StubStore(SkillStore):
    def __init__(self):
        self.saved = []

    def save(self, skill):
        self.saved.append(skill)

    def load_all(self):
        return list(self.saved)


def _ctx(make_gateway, synth, store):
    gw = make_gateway(lambda sys, user: CompletionResult(content="ok"))
    return GraphContext(
        gateway=gw, registry=default_registry(),
        composer=HeuristicSwarmComposer(model="demo"), model="demo",
        skill_synthesizer=synth, skill_store=store,
    )


_SUCCESS_STATE = {
    "task": "greet people", "final_answer": "done",
    "results": [{"subtask": "a", "output": "x", "tool_calls": []}], "metrics": {},
}


def test_skill_forge_registers_on_success(make_gateway):
    store = _StubStore()
    ctx = _ctx(make_gateway, _StubSynth(_SKILL), store)
    out = make_skill_forge(ctx)(_SUCCESS_STATE)
    assert out == {"learned_skills": ["skill.greet"]}
    assert store.saved and store.saved[0].name == "greet"
    assert "skill.greet" in [s.name for s in ctx.registry.all_specs()]


def test_skill_forge_noop_on_failure(make_gateway):
    ctx = _ctx(make_gateway, _StubSynth(_SKILL), _StubStore())
    # no final_answer -> not a success -> no-op
    assert make_skill_forge(ctx)({"task": "t", "results": [], "metrics": {}}) == {}


def test_skill_forge_noop_when_nothing_distilled(make_gateway):
    ctx = _ctx(make_gateway, _StubSynth(None), _StubStore())
    assert make_skill_forge(ctx)(_SUCCESS_STATE) == {}


def test_skill_forge_noop_when_verify_fails(make_gateway):
    bad = Skill(name="x", description="d", template="", parameters={"type": "object"})
    ctx = _ctx(make_gateway, _StubSynth(bad), _StubStore())
    assert make_skill_forge(ctx)(_SUCCESS_STATE) == {}


# --------------------------- service plumbing ---------------------------

@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CHECKPOINT_PATH", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("RIPTIDE_WATERGRAPH_DISABLE_TRACING", "1")
    return tmp_path


def test_build_components_loads_learned_skills(env):
    settings = get_settings()
    JsonFileSkillStore(settings.tenant_skills_dir("default")).save(_SKILL)
    comp = build_components(settings, offline=True, memory_on=False, guardrails_on=False,
                            skills_on=True)
    assert comp.skill_synthesizer is not None and comp.skill_store is not None
    assert "skill.greet" in [s.name for s in comp.registry.all_specs()]


def test_build_components_skills_off(env):
    comp = build_components(get_settings(), offline=True, memory_on=False,
                            guardrails_on=False, skills_on=False)
    assert comp.skill_synthesizer is None and comp.skill_store is None


def test_run_task_with_learn_skills_offline(env):
    from riptide_watergraph.service import run_task
    result = run_task("compute 21 * 2", offline=True, memory_on=False, learn_skills=True)
    assert result.final_answer is not None  # runs end-to-end with the skill_forge node wired


# --------------------------- CLI ---------------------------

def test_cli_run_learn_skills_offline(env, capsys):
    # Pre-seed a skill so the load-on-startup path runs, then the offline run authors one.
    JsonFileSkillStore(get_settings().tenant_skills_dir("default")).save(_SKILL)
    assert main(["run", "compute 21 * 2", "--offline", "--no-memory", "--learn-skills"]) == 0
    assert "learned" in capsys.readouterr().out  # the skill_forge node authored a skill


def test_cli_skills_empty_and_listed(env, capsys):
    assert main(["skills"]) == 0
    assert "no learned skills" in capsys.readouterr().out
    JsonFileSkillStore(get_settings().tenant_skills_dir("default")).save(_SKILL)
    assert main(["skills", "--tenant", "default"]) == 0
    assert "skill.greet" in capsys.readouterr().out
