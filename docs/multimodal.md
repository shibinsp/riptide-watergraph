# Multimodal perception (vision)

Added in **v0.20.0** — the first experimental research seam beyond the cognitive-scaffolding roadmap.

The gateway `Message` can now carry **images** alongside text, so any vision-capable model reads them.
It's additive: `Message.images` defaults to empty, and `to_dict()` only switches to the OpenAI
multimodal parts list (`{"type": "text"}` + `{"type": "image_url"}`) when images are present — every
existing text path is unchanged. Offline, a vision-aware `DemoGateway` returns a deterministic response
so the whole path runs without a key.

## CLI

```bash
riptide see "What is in this image?" --image ./photo.jpg --offline
riptide see "Compare these" --image a.png --image https://example.com/b.png   # files or URLs (repeatable)
#  question: What is in this image?
#  images:   1
#
#  ANSWER
#  ...
```

A local path is read into a `data:` URI automatically; URLs and `data:` URIs pass through.

## OpenAI-compatible /v1 (vision)

`POST /v1/chat/completions` accepts OpenAI's native multimodal `content`, so a standard vision client
works unchanged:

```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key="not-needed")
resp = client.chat.completions.create(
    model="riptide-watergraph",
    messages=[{"role": "user", "content": [
        {"type": "text", "text": "What's in this image?"},
        {"type": "image_url", "image_url": {"url": "https://example.com/cat.png"}},
    ]}],
)
print(resp.choices[0].message.content)
```

When the latest message carries images, the endpoint answers multimodally (single-agent, no graph).

## In code

```python
from riptide_watergraph.service import vision_chat, image_to_data_uri

answer = vision_chat("Describe this", [image_to_data_uri("photo.jpg")])
```

Or build a vision message directly:

```python
from riptide_watergraph.interfaces.gateway import Message

msg = Message(role="user", content="What is this?", images=["data:image/png;base64,..."])
msg.to_dict()  # -> OpenAI multimodal content parts
```

## Notes

- A real vision model (e.g. `gpt-4o`, `claude-3.5-sonnet`) reads the images when you configure a live
  gateway; offline, the deterministic `DemoGateway` describes how many images it received.
- `images` accepts **URLs** and **`data:` URIs**. `image_to_data_uri` base64-encodes a local file with a
  guessed MIME type.
- This is an **experimental research seam** — the first of the multimodal / environment / RL tracks
  beyond the core roadmap.
