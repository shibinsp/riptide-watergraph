# Environments (embodiment)

Added in **v0.21.0** — an experimental research seam.

Everything else answers a prompt. An **Environment** turns "answer a question" into "act, observe, and
get rewarded": the agent `reset()`s, then `step(action)`s, receiving an `Observation` (text + reward +
done) each time. A `rollout` runs an LLM **policy** in the environment until the episode ends. This is the
substrate for interactive, feedback-driven agents — and, later, reinforcement learning.

```
reset() ──▶ observation ──▶ policy(obs) → action ──▶ step(action) ──▶ observation (+reward, +done)
                              (LLM or a function)        (the environment)         └─ loop until done / max_steps
```

## CLI

```bash
riptide env guessing --max-steps 10 --offline
#  environment 'guessing': 10 step(s), total reward 0.0
#    1. obs: Guess a whole number between 1 and 100. | action: ... | reward 0.0
#    ...
```

(Offline, the deterministic gateway is a weak policy — the point is the loop; a real model plays it well.)

## In code

```python
from riptide_watergraph.environments import make_environment, rollout

env = make_environment("guessing")

# A policy maps an observation (text) to an action (text) — here, binary search:
state = {"lo": 1, "hi": 100}
def policy(obs: str) -> str:
    if "higher" in obs: state["lo"] = state["mid"] + 1
    elif "lower" in obs: state["hi"] = state["mid"] - 1
    state["mid"] = (state["lo"] + state["hi"]) // 2
    return str(state["mid"])

result = rollout(env, policy, max_steps=20)
print(result.total_reward, result.steps)   # 1.0 (solved) in ~7 steps
```

Run an **LLM** policy through the service:

```python
from riptide_watergraph.service import run_in_environment

result = run_in_environment("guessing", max_steps=10)   # uses the configured model as the policy
```

## The seam (swappable)

| Interface | Default | Purpose |
|-----------|---------|---------|
| `Environment` | `GuessingGameEnv` (toy) | `reset()` / `step(action)` → `Observation(text, reward, done)` |
| `rollout(env, policy, ...)` | — | run a policy to episode end; returns `Rollout(steps, total_reward, transitions)` |
| `make_environment(name)` | registry | build a named environment (`ENVIRONMENTS`) |

Implement `Environment` to plug in your own world (a code repo, a browser, a game). The bundled
`GuessingGameEnv` is deterministic so the whole act/observe/reward loop runs offline at 100% coverage.

## Roadmap context

An experimental seam alongside [multimodal perception](multimodal.md). With a reward signal in hand, this
is the substrate the remaining research direction (reward/RL, learned policies) would build on.
