# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Start demo (mock mode — no sandbox needed)
./run.sh

# Start against real bunq sandbox
./run.sh --live

# Seed sandbox + start
./run.sh --seed

# Run eval harness (15 scripted test cases, mock mode)
./run.sh --test
# or directly:
python tests/test_agent.py
python -m pytest tests/test_agent.py -v

# Install dependencies manually
pip install -e .

# Reset mid-demo (stops server, clears state, re-seeds, restarts)
python scripts/reset_demo.py
python scripts/reset_demo.py --skip-seed
```

## Architecture

The project is a FastAPI server (`src/app.py`) that connects a Claude tool-use agent to the bunq banking API. The core flow:

```
Browser UI (web/index.html)
  → POST /chat | /voice | /receipt
    → src/agent/loop.py  (the agent loop — most important file)
      → Claude API (with tools from src/agent/tools.py)
        → src/agent/handlers.py  (mock or real bunq SDK calls)
          → fixtures/transactions.json (mock) or bunq sandbox (live)
```

### Key design decisions

**Dual-mode (mock/live)**: `MOCK_MODE` env var controls whether tool handlers use `fixtures/transactions.json` or the real bunq SDK. Every handler has both a `_mock_*` and `_real_*` implementation dispatched by `execute_tool()`. Mock mode is the default — demo-safe even without wifi.

**Agent loop (`src/agent/loop.py`)**: A plain `while` loop, not a framework. Each iteration calls Claude, checks `stop_reason`, executes tool calls (feeding results back as `tool_result` messages), and breaks on `end_turn`. Max 10 iterations. Keep it readable.

**Tool definitions (`src/agent/tools.py`) and handlers (`src/agent/handlers.py`) must stay in sync.** When adding a tool, update both files and the `_MOCK_HANDLERS`/`_REAL_HANDLERS` dicts.

**System prompt (`src/agent/prompts.py`)**: Contains safety rules (confirm before payments >€50, never auto-initiate payments), output format rules, and user context. Treat it like code — comment every rule.

**Model selection**: Use `FAST_MODEL = claude-haiku-4-5` for simple lookups/categorisation; `SMART_MODEL = claude-sonnet-4-6` for reasoning and vision. Configured in `src/config.py`.

### File map

| File | Purpose |
|------|---------|
| `src/agent/loop.py` | Core tool-use cycle — start here |
| `src/agent/tools.py` | Anthropic tool schemas (JSON) |
| `src/agent/handlers.py` | Tool implementations: mock + real bunq SDK |
| `src/agent/prompts.py` | System prompt + prompt templates |
| `src/vision/receipt_parser.py` | Claude vision → validated ReceiptData |
| `src/speech/asr.py` | Whisper ASR (OpenAI API or local faster-whisper) |
| `src/speech/tts.py` | OpenAI TTS or macOS `say` fallback |
| `src/app.py` | FastAPI: `/chat`, `/voice`, `/receipt`, `/state`, `/reset` |
| `web/index.html` | Single-file UI (no build step) |
| `fixtures/transactions.json` | 20 Dutch student transactions for mock mode |
| `scripts/seed_sandbox.py` | Creates sandbox users + transactions |
| `scripts/reset_demo.py` | Full demo reset in <30s |
| `tests/test_agent.py` | 15 scripted eval cases |

## Speech options

- **ASR**: Default = OpenAI Whisper API. Set `USE_LOCAL_WHISPER=true` + `pip install faster-whisper` for offline.
- **TTS**: Default = OpenAI TTS (voice configurable via `TTS_VOICE` env). Set `USE_MACOS_TTS=true` for offline macOS fallback.

## Extending

To add a new tool:
1. Add schema to `src/agent/tools.py` (description is what the model reads to decide when to use it)
2. Add `_mock_<name>` and `_real_<name>` functions to `src/agent/handlers.py`
3. Register both in `_MOCK_HANDLERS` and `_REAL_HANDLERS` dicts
4. Add test cases to `tests/test_agent.py`
