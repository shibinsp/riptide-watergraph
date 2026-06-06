# OpenAI-compatible API

Added in **v0.14.0**.

`riptide serve` exposes a `POST /v1/chat/completions` endpoint that speaks the OpenAI
chat-completions wire format — so any **OpenAI SDK**, **LangChain**, **OpenWebUI**, or `curl`
client can point at riptide and get the **full agentic graph** (memory, swarm, tools, guardrails)
behind a familiar API.

The **last message** is the task; earlier `user`/`assistant` messages become the conversation
history. `stream=true` returns `chat.completion.chunk` SSE deltas (terminated by `data: [DONE]`);
otherwise a single `chat.completion` object.

## OpenAI Python SDK

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key="not-needed")
resp = client.chat.completions.create(
    model="riptide-watergraph",
    messages=[{"role": "user", "content": "What is 21 * 2?"}],
)
print(resp.choices[0].message.content)
```

For a real model behind the graph, configure a provider/key first (via the Studio **Connections**
view or `OPENAI_API_KEY` + `RIPTIDE_WATERGRAPH_MODEL`).

## curl

```bash
curl -s http://127.0.0.1:8000/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{"model":"demo","messages":[{"role":"user","content":"compute 21 * 2"}],"offline":true}'
```

```json
{
  "id": "chatcmpl-…",
  "object": "chat.completion",
  "created": 1717000000,
  "model": "demo",
  "choices": [{"index": 0, "message": {"role": "assistant", "content": "…"}, "finish_reason": "stop"}],
  "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
}
```

## Streaming

```bash
curl -N http://127.0.0.1:8000/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{"messages":[{"role":"user","content":"hello"}],"stream":true,"offline":true}'
```

emits `data: {…chat.completion.chunk…}` lines and a final `data: [DONE]`.

## Notes

- **`offline: true`** is a riptide extension (not in the OpenAI schema) — it runs the deterministic
  `DemoGateway`, so the endpoint works with no API key (handy for tests and demos). Omit it to run
  against the configured model.
- The endpoint is single-turn-per-call but carries history from the `messages` array, so a chat
  client's running transcript works as expected.
- Supported request fields: `messages`, `model`, `stream`, `temperature`, `top_p`, `max_tokens`,
  `tenant_id`, `offline`. An over-budget tenant returns HTTP 402; empty `messages` returns 400.
- The API is unauthenticated — keep it behind an auth proxy if exposed beyond localhost.
