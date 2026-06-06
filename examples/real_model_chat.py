"""Run one task against a real LLM through the library (needs an API key).

Setup:
    pip install -e ".[all]"
    export OPENAI_API_KEY=sk-...
    export RIPTIDE_WATERGRAPH_MODEL=gpt-4o-mini      # any LiteLLM model string

Run: python examples/real_model_chat.py "What is the capital of France?"
"""

from __future__ import annotations

import sys

from riptide_watergraph.service import run_task


def main() -> None:
    task = " ".join(sys.argv[1:]) or "Summarize what an agentic framework is in one sentence."
    # offline=False routes through LiteLLM (wrapped in ResilientGateway) using the
    # model from settings (RIPTIDE_WATERGRAPH_MODEL). auto_approve runs headless.
    result = run_task(task, offline=False, memory_on=False)
    print(f"task:   {task}")
    print(f"mode:   {result.mode}")
    print(f"answer: {result.final_answer}")


if __name__ == "__main__":
    main()
