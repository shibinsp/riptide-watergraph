# Streaming & interactive HITL

Added in **v0.11.0**.

## Direct token streaming

`service.stream_chat_tokens(message, ...)` is an async generator that yields the model's output
**token-by-token** straight from `gateway.stream()` — single-agent, no graph, no tools. Useful for a
type-as-you-read chat experience.

```python
from riptide_watergraph.service import stream_chat_tokens

async for token in stream_chat_tokens("Explain RRF fusion in one line", offline=False):
    print(token, end="", flush=True)
```

In the Studio, the Chat view's **"Direct token stream"** toggle renders it via
`GET /api/chat/stream` (SSE: `{event:"token"}` deltas then `{event:"done"}`). Offline the `DemoGateway`
yields the answer once; a live LiteLLM gateway yields real deltas.

!!! note
    The direct stream bypasses the graph, so it has no tools or swarm. For multi-agent runs use the
    graph chat (`stream_task` / the Playground live trace).

## Interactive human-in-the-loop approval

`service.run_interactive(task, ...)` runs with `auto_approve=False`. When the graph reaches a
**side-effecting tool** it pauses and returns a `PendingApproval` carrying the `thread_id` and the action
(tool + arguments + subtask). The run state is persisted durably in the `SqliteSaver` thread, so a later
`resume_interactive(...)` continues it — **across separate HTTP requests**.

```python
from riptide_watergraph.service import run_interactive, resume_interactive, PendingApproval

res = run_interactive("save a note about water", offline=True)
if isinstance(res, PendingApproval):              # paused at a write tool
    print("approve?", res.action)
    res = resume_interactive(res.thread_id, approved=True, task="save a note about water")
print(res.final_answer)
```

In the Studio, the Chat view's **"Ask before running tools"** toggle renders an **approval card**
(Approve / Deny) backed by:

| Endpoint | Purpose |
|----------|---------|
| `POST /api/run/interactive` | start a run; returns `pending_approval` or a completed `RunResult` |
| `POST /api/run/{thread_id}/resume` | approve/deny (or answer a clarification) and continue |

The same mechanism powers clarifying-question HITL — a worker can emit `ask_human(question)` and the run
pauses for a free-text answer.
