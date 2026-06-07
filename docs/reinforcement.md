# Reward / RL

Added in **v0.22.0** — the final research seam of the roadmap.

A `RewardModel` turns an outcome into a scalar in `[0, 1]`, and a deterministic **UCB bandit** over
candidate strategies learns which one earns the most reward for a task — online policy improvement from a
reward signal (the substrate for reinforcement learning).

```
for each round:  bandit.select() → strategy ──▶ run it → answer ──▶ reward_model.reward(...) ──▶ bandit.update()
                 (UCB: try each once,                                (0..1 scalar)              (running mean)
                  then exploit the best)                                                        └─ best() = argmax mean
```

## CLI

```bash
riptide rl "summarize the water cycle" --rounds 8 --offline
#  learned strategy values for: summarize the water cycle
#    reward 0.71  stepwise     (pulls 4)
#    reward 0.55  direct       (pulls 2)
#    ...
#  BEST STRATEGY: stepwise
```

The arms are the diverse reasoning styles from [deliberation](deliberation.md); the bandit learns which
style maximizes reward for *this* task.

## In code

```python
from riptide_watergraph.service import optimize_strategy_for_task

report = optimize_strategy_for_task("explain reciprocal rank fusion", rounds=8)
print(report.best, [(a.arm, a.mean_reward) for a in report.arms])
```

Or drive the primitive directly with your own arms / runner / reward:

```python
from riptide_watergraph.rl import optimize_strategy, HeuristicRewardModel

report = optimize_strategy(
    task, arms=["concise", "detailed", "stepwise"],
    runner=lambda arm, t: my_model(arm, t),     # run a strategy on the task
    reward_model=HeuristicRewardModel(), rounds=10,
)
```

## The seam (swappable)

| Interface | Default | Purpose |
|-----------|---------|---------|
| `RewardModel` | `HeuristicRewardModel` (offline) / `LLMRewardModel` | score an outcome as a scalar reward |
| `Bandit` | UCB1 (deterministic) | balance exploring arms vs. exploiting the best |
| `optimize_strategy(...)` | — | run the reward-driven bandit loop → `StrategyReport` |

The `Bandit` is **deterministic** (UCB1, no randomness) so runs are reproducible, and the
`HeuristicRewardModel` is offline — the whole RL loop runs at 100% coverage without a key.

## Honest scope

This is **not** policy-gradient RL or weight updates — that's a model-training problem. It's a bandit
over *strategies* with a reward signal: the framework-level slice of RL (online selection of the
highest-reward approach). It completes the roadmap's research seams alongside
[multimodal perception](multimodal.md) and [environments](environments.md).
