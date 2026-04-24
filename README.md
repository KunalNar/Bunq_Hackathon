# Finn — bunq AI Financial Assistant

A multi-modal AI assistant that can **hear** (voice commands), **see** (receipt photos), and **act** (move money via bunq API).

## Quick Start

```bash
cp .env.example .env
# Fill in ANTHROPIC_API_KEY (required), OPENAI_API_KEY (for voice), BUNQ_API_KEY (for live mode)

./run.sh          # starts in mock mode — no API keys needed except Anthropic
```

Open **http://localhost:8000** in your browser.

## Modes

| Flag | Behaviour |
|------|-----------|
| `./run.sh` | Mock mode — uses fixture data, safe for demo without wifi |
| `./run.sh --live` | Connects to real bunq sandbox |
| `./run.sh --seed` | Seeds sandbox with transactions, then starts |
| `./run.sh --test` | Runs eval harness (15 test cases) and exits |

## What it does

- **Chat**: Ask Finn about your balance, spending, or financial goals
- **Voice**: Hold the mic button, speak a command, hear the response
- **Receipt**: Upload a receipt photo → auto-parsed → offer to split or categorise
- **Live account panel**: Balance and recent transactions, auto-refreshed

## Stack

- **Agent**: Claude claude-sonnet-4-6 + Anthropic tool-use API
- **Banking**: bunq sandbox SDK
- **Speech**: OpenAI Whisper (ASR) + OpenAI TTS
- **Vision**: Claude claude-sonnet-4-6 vision for receipt parsing
- **Server**: FastAPI + uvicorn
- **UI**: Single-file vanilla HTML/JS

## 90-second demo script

1. **(0–15s)** "Students stress about money. Meet Finn."
2. **(15–45s)** **HEAR** — say "What's my balance and how much did I spend on food?" → watch tool calls flash on screen
3. **(45–75s)** **SEE** — upload a receipt → parse → "Split this 3 ways and request from my housemates"
4. **(75–90s)** **ACT** — "Create a holiday savings goal for €500" → confirm → done

## Customisation

- `src/agent/prompts.py` — change Finn's personality and safety rules
- `src/agent/tools.py` + `src/agent/handlers.py` — add new capabilities
- `fixtures/transactions.json` — change the demo account data
- `web/index.html` — adjust the UI layout
