"""
loop.py — The core agent loop.

This is the most important file in the project. It implements the
tool-use cycle that connects user messages to Claude, Claude to tools,
and tools back to Claude until a final text response is produced.

The flow for a single turn:
    User message
      → Claude (with tools available)
        → Claude returns tool_use block(s)
          → We execute the tool(s)
            → Feed results back to Claude
              → Repeat until Claude returns stop_reason="end_turn"
                → Return the final text response

Keeping this loop as a plain while-loop (no framework) means any
teammate can read and debug it in under 2 minutes.
"""

import json
from typing import Any

import anthropic

from src.agent.handlers import execute_tool
from src.agent.prompts import SYSTEM_PROMPT
from src.agent.tools import TOOL_DEFINITIONS
from src.config import ANTHROPIC_API_KEY, MOCK_MODE, SMART_MODEL

# Module-level client (re-used across calls to avoid re-auth overhead)
_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def run_agent(
    messages: list[dict],
    *,
    mock_mode: bool = MOCK_MODE,
    max_iterations: int = 10,
    model: str = SMART_MODEL,
    extra_tools: list[dict] | None = None,
) -> tuple[str, list[dict], dict]:
    """
    Run one full agent turn and return when the model produces a text response.

    Args:
        messages:        Conversation history in Anthropic message format.
                         The caller is responsible for appending the new user
                         message before calling this function.
        mock_mode:       If True, tool handlers use fixture data (no sandbox).
        max_iterations:  Safety cap on tool-call rounds per turn.
        model:           Claude model ID to use.
        extra_tools:     Additional Anthropic tool specs to enable for this turn
                         (e.g. [WEB_SEARCH_TOOL] for fraud verification). Server
                         tools are executed by Anthropic; our dispatcher never
                         sees them, so we don't need handlers for them.

    Returns:
        (final_text, updated_messages, usage_summary)
        - final_text:       The assistant's last text response.
        - updated_messages: The full history including this turn's assistant +
                            tool-result messages (append to your history).
        - usage_summary:    {"input_tokens": int, "output_tokens": int}
    """
    tool_calls_made: list[dict] = []  # collected for the caller / UI
    total_usage = {"input_tokens": 0, "output_tokens": 0}
    new_messages: list[dict] = []  # messages added this turn
    effective_tools = TOOL_DEFINITIONS + (extra_tools or [])

    for iteration in range(max_iterations):
        # ── Call the model ─────────────────────────────────────────────────────
        response = _client.messages.create(
            model=model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=effective_tools,
            messages=messages + new_messages,
        )

        # Track token usage for cost awareness
        total_usage["input_tokens"] += response.usage.input_tokens
        total_usage["output_tokens"] += response.usage.output_tokens

        # Build the assistant turn from all content blocks
        assistant_message: dict[str, Any] = {
            "role": "assistant",
            "content": response.content,  # list of TextBlock / ToolUseBlock
        }
        new_messages.append(assistant_message)

        # ── Done? ──────────────────────────────────────────────────────────────
        if response.stop_reason == "end_turn":
            # Join ALL text blocks. With server tools like web_search, the model
            # may emit text before and after tool results — taking only the first
            # block would drop the actual answer.
            final_text = "".join(
                block.text for block in response.content if hasattr(block, "text")
            )
            return final_text, new_messages, total_usage

        # ── Handle tool calls ─────────────────────────────────────────────────
        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                tool_name = block.name
                tool_args = block.input
                print(f"[tool] {tool_name}({json.dumps(tool_args, ensure_ascii=False)})")

                # Execute the tool (mock or real)
                try:
                    result = execute_tool(tool_name, tool_args, mock_mode=mock_mode)
                except Exception as exc:
                    # Return the error to the model so it can explain / recover
                    result = {"error": type(exc).__name__, "details": str(exc)}

                print(f"[tool] → {json.dumps(result, ensure_ascii=False)[:200]}")
                tool_calls_made.append(
                    {"name": tool_name, "args": tool_args, "result": result}
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )

            # Feed all tool results back to the model in a single user turn
            new_messages.append({"role": "user", "content": tool_results})
            continue  # go back to the top of the loop

        # Unexpected stop reason — surface it so we can debug
        raise RuntimeError(f"Unexpected stop_reason: {response.stop_reason!r}")

    # Iteration limit hit — return whatever text we have so far
    final_text = "[Agent hit iteration limit. Please try a simpler request.]"
    return final_text, new_messages, total_usage
