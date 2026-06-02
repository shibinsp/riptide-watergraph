"""Live LiteLLM smoke test — runs only with a real API key (skipped in CI).

    pip install -e ".[litellm]"
    export OPENAI_API_KEY=sk-...        # or ANTHROPIC_API_KEY
    export RIPTIDE_WATERGRAPH_MODEL=gpt-4o-mini
    pytest tests/test_litellm_live.py

CI has no key, so this is skipped there; the litellm gateway code is covered offline by
tests/test_litellm_gateway.py (faked boundary).
"""

from __future__ import annotations

import os

import pytest

from riptide_watergraph.gateway import LiteLLMGateway
from riptide_watergraph.interfaces.gateway import Message

pytestmark = pytest.mark.skipif(
    not (os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")),
    reason="set OPENAI_API_KEY / ANTHROPIC_API_KEY (and install [litellm]) to run the live test",
)


async def test_live_complete_and_stream():
    model = os.getenv("RIPTIDE_WATERGRAPH_MODEL", "gpt-4o-mini")
    gw = LiteLLMGateway(default_model=model)
    res = await gw.complete(model=model,
                            messages=[Message(role="user", content="Reply with the word OK.")])
    assert res.content
    chunks = [c async for c in gw.stream(
        model=model, messages=[Message(role="user", content="Say: one two three")])]
    assert "".join(chunks).strip()
