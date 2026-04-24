# Claude Code Prompt — bunq Hackathon 7.0 Demo Scaffold

> **How to use this:** Copy the prompt below into Claude Code. Read through each `[CUSTOMIZE]` tag and replace with your team's choices. The prompt is designed to be run as-is for a working demo, then iteratively customized.

---

## The Prompt

```
You are helping me build a demo for the bunq Hackathon 7.0 (April 24-25, 2026).

## WHAT WE'RE BUILDING

A multi-modal AI financial assistant that can HEAR (voice commands), SEE (receipt photos), and ACT (move money via bunq API). The demo target is a 90-second live presentation to judges.

[CUSTOMIZE: Replace this user story with your team's chosen idea]
User story: "As a Dutch student living on €1,400/month in Delft, I want an AI assistant that listens to me, reads my receipts, and proactively manages my bunq account so I never miss rent."

## PROJECT STRUCTURE

Create the following project structure. Explain what each file does as you create it:

```
project/
├── .env.example              # template for API keys
├── pyproject.toml            # dependencies
├── README.md                 # judge-readable, under 1 screen
├── fixtures/
│   ├── receipts/             # sample receipt images for testing
│   └── transactions.json     # mock bunq transactions for offline mode
├── src/
│   ├── __init__.py
│   ├── config.py             # env loading, constants
│   ├── bunq_client.py        # thin wrapper around bunq sandbox SDK
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── loop.py           # THE core agent loop (tool-use cycle)
│   │   ├── tools.py          # tool definitions (JSON schemas)
│   │   ├── handlers.py       # tool implementations (call bunq, parse receipts, etc.)
│   │   └── prompts.py        # system prompt and prompt templates
│   ├── speech/
│   │   ├── __init__.py
│   │   ├── asr.py            # speech-to-text (Whisper)
│   │   └── tts.py            # text-to-speech (OpenAI TTS / ElevenLabs)
│   ├── vision/
│   │   ├── __init__.py
│   │   └── receipt_parser.py # receipt image → structured JSON
│   └── app.py                # FastAPI server tying everything together
├── web/
│   └── index.html            # single-file demo UI (mic, camera, chat, balances)
├── scripts/
│   ├── seed_sandbox.py       # create sandbox users, fund via Sugar Daddy
│   └── reset_demo.py         # nuke and re-seed for clean demo state
├── tests/
│   └── test_agent.py         # eval harness: scripted commands → expected tool calls
└── run.sh                    # one command to start everything
```

## STEP-BY-STEP BUILD ORDER

Build each step completely before moving to the next. After each step, explain:
1. What was built and why
2. How it connects to the other pieces
3. What to customize for different hackathon ideas

### STEP 1: Config and Dependencies

Create pyproject.toml with these dependencies:
- anthropic (Claude API)
- openai (Whisper ASR + TTS)
- bunq-sdk (banking API)
- fastapi + uvicorn (demo server)
- python-dotenv (env management)
- pydantic (data validation)
- Pillow (image handling)
- httpx (async HTTP)

Create config.py that:
- Loads .env using python-dotenv
- Exposes ANTHROPIC_API_KEY, BUNQ_API_KEY, OPENAI_API_KEY
- Has a MOCK_MODE flag (True = use fixtures, False = hit real sandbox)
- Has model selection constants (FAST_MODEL = "claude-haiku-4-5", SMART_MODEL = "claude-sonnet-4-6")

[CUSTOMIZE: Add any extra dependencies your idea needs]

### STEP 2: The Agent Loop (THIS IS THE CORE — spend the most time here)

Build src/agent/loop.py implementing the tool-use cycle. This is the heart of the entire project.

The loop works like this:
```
User input → Claude (with tools) → tool_use? → execute tool → feed result back → repeat until text response
```

Implementation requirements:
- The loop function takes a conversation history (list of messages) and returns the final text response
- It handles multiple sequential tool calls in one turn
- It has a max_iterations safety limit (default 10) to prevent infinite loops
- It logs every tool call to stdout for debugging (tool name, arguments, result)
- It catches tool execution errors gracefully and returns error info to the model so it can recover
- It tracks token usage for cost awareness

Write this as a clean, well-commented ~60-line function. This is the thing the team needs to understand cold.

### STEP 3: Tool Definitions

Create src/agent/tools.py with these tools defined as Anthropic tool schemas:

[CUSTOMIZE: These are starter tools — swap/add based on your idea]

1. **get_balance** — Returns current balance of primary account
   - No parameters
   - Why: Every financial demo needs this as the baseline check

2. **list_transactions** — Returns recent transactions with merchant, amount, category
   - Parameters: limit (int, default 10), category_filter (optional string)
   - Why: Lets the agent reason about spending patterns

3. **create_payment** — Transfers money between accounts
   - Parameters: to_iban (string), amount_eur (number), description (string)
   - Why: This is the "act" in hear-see-act — the agent moves real money

4. **create_request_inquiry** — Requests money from someone (bill splitting)
   - Parameters: to_email (string), amount_eur (number), description (string)
   - Why: Great for the receipt-splitting demo moment

5. **categorize_transaction** — Labels a transaction with a spending category
   - Parameters: transaction_id (string), category (enum: food, transport, rent, entertainment, utilities, other)
   - Why: Turns raw bank data into something the agent can reason about

6. **create_savings_goal** — Creates a sub-account with a target
   - Parameters: name (string), target_eur (number)
   - Why: Shows the agent can take proactive financial actions

7. **parse_receipt** — Extracts structured data from a receipt image (base64)
   - Parameters: image_base64 (string)
   - Why: This is the "see" modality — connects vision to banking actions

8. **log_action** — Writes an audit log entry (for demo transparency)
   - Parameters: action_description (string)
   - Why: Judges love seeing that the agent tracks what it does

For each tool, write:
- A clear description (the model reads this to decide when to use the tool)
- A tight JSON schema (only required fields are truly required)
- A docstring explaining when the model should/shouldn't use it

### STEP 4: Tool Handlers (Mock + Real)

Create src/agent/handlers.py implementing each tool twice:

1. **Mock mode** (default): Returns realistic fake data from fixtures/transactions.json
   - Pre-seed with 20+ realistic Dutch student transactions
   - Include: Albert Heijn, Thuisbezorgd, NS, Xenos, Bol.com, rent to "Woonstichting", etc.
   - Amounts in EUR, dates in last 30 days

2. **Real mode**: Calls the bunq sandbox SDK
   - Wrap each bunq call in try/except
   - Return structured dicts, never raw SDK objects
   - On failure, return {"error": "...", "details": "..."} so the agent can explain

Include a dispatcher function:
```python
def execute_tool(name: str, args: dict, mock_mode: bool = True) -> dict:
    """Route a tool call to mock or real implementation."""
```

This dual-mode design means you can demo without the sandbox and switch to live when ready.

### STEP 5: System Prompt

Create src/agent/prompts.py with the system prompt. This is your "model tuning" — iterate on it like a loss function.

[CUSTOMIZE: This is the biggest thing to change for your specific idea]

The system prompt should include:
- **Role**: "You are a financial assistant for Dutch students using bunq..."
- **Personality**: Friendly but precise with money. Brief responses. Uses EUR.
- **Safety rules**:
  - "ALWAYS confirm before any payment over €50"
  - "NEVER initiate a payment without explicit user confirmation of amount and recipient"
  - "If the user's request is ambiguous about amount or recipient, ask ONE clarifying question"
- **Output rules**:
  - "When reporting balances, always include the account name and currency"
  - "When categorizing, use exactly one of: food, transport, rent, entertainment, utilities, other"
  - "After completing any money-moving action, call log_action with a summary"
- **Context**: "The user is a student in Delft with a monthly budget of approximately €1,400"

### STEP 6: Receipt Parser (Vision)

Create src/vision/receipt_parser.py that:
- Takes a receipt image (file path or base64)
- Sends it to Claude with a vision prompt
- Returns a Pydantic-validated dict: {merchant, total, currency, date, line_items, category_guess}
- Uses temperature=0 for determinism
- Retries up to 2 times if Pydantic validation fails

The vision prompt should be specific:
"Extract the following from this receipt image as JSON. If a field is unreadable, use null. Do not guess amounts — if unclear, set total to null."

This parser is called by the parse_receipt tool handler.

### STEP 7: Speech (ASR + TTS)

Create src/speech/asr.py:
- Function: transcribe(audio_path: str) -> str
- Uses OpenAI Whisper API (simpler) or local whisper (offline fallback)
- Handles wav and mp3 formats

[CUSTOMIZE: Pick your ASR — options below]
Option A: OpenAI Whisper API (simplest, needs internet)
Option B: Local faster-whisper (offline, needs ~1GB model download)
Option C: Deepgram (streaming, WebSocket — only if you know WebSockets)

Create src/speech/tts.py:
- Function: speak(text: str) -> bytes (audio)
- Returns audio bytes that the frontend can play

[CUSTOMIZE: Pick your TTS]
Option A: OpenAI TTS API (good quality, cheap)
Option B: ElevenLabs (best quality, costs more)
Option C: macOS `say` command (free, sounds robotic, works offline)

### STEP 8: FastAPI Server

Create src/app.py that:
- Serves the web UI on GET /
- Has POST /chat — accepts {message: string}, returns {response: string, tool_calls: list}
- Has POST /voice — accepts audio file upload, transcribes, runs agent, returns {transcript, response, audio_b64}
- Has POST /receipt — accepts image upload, parses receipt, optionally runs agent to categorize/split
- Has GET /state — returns current account balance and recent transactions (for the UI to poll)
- Has POST /reset — calls the seed script to reset demo state
- Uses WebSocket /ws for streaming responses (stretch goal — skip if short on time)

Each endpoint should:
- Log the request
- Handle errors with clear JSON error responses
- Support both mock and real mode via query param ?mock=true

### STEP 9: Demo UI

Create web/index.html as a SINGLE self-contained HTML file (inline CSS + JS, no build step).

[CUSTOMIZE: Adjust the layout for your demo story]

The UI should have 4 panels:
1. **Chat panel** (left): Shows conversation with the agent. User messages on right, agent on left. Show tool calls as collapsible grey cards between messages.
2. **Account panel** (top-right): Current balance, account name, last 5 transactions. Auto-refreshes every 5s.
3. **Voice panel** (bottom-right): Big mic button. Hold to record, release to send. Shows transcript. Plays TTS response.
4. **Camera panel** (bottom): Snap button to take a receipt photo. Shows preview. "Process" button sends to /receipt.

Design notes:
- Use a clean, modern design. bunq's brand colors are green (#00DC84) and dark (#1A1A2E).
- Mobile-friendly — judges might see it on a projected screen.
- Show a "MOCK MODE" badge when running against fixtures, "LIVE" when connected to sandbox.
- Every tool call the agent makes should briefly flash on screen so judges see the agent "thinking."

### STEP 10: Seed and Reset Scripts

Create scripts/seed_sandbox.py:
- Initializes bunq sandbox session
- Creates 2-3 sandbox users (main account, savings, housemate)
- Funds each via Sugar Daddy (€500 each)
- Creates 20+ realistic transactions on the main account
- Saves the sandbox state info to a JSON file

Create scripts/reset_demo.py:
- Kills any running server
- Clears conversation history
- Re-runs the seed script
- Restarts the server
- Should complete in under 30 seconds (critical for mid-demo recovery)

### STEP 11: Eval Harness

Create tests/test_agent.py with 15 scripted test cases:

```python
CASES = [
    {"input": "What's my balance?", "expected_tool": "get_balance"},
    {"input": "Show my last 5 transactions", "expected_tool": "list_transactions"},
    {"input": "Send €25 to my housemate for dinner", "expected_tool": "create_payment", "expect_confirmation": True},
    {"input": "How much did I spend on food this week?", "expected_tool": "list_transactions"},
    # ... add more
]
```

The test runner:
- Feeds each case to the agent in isolation (fresh conversation)
- Asserts the FIRST tool call matches expected_tool
- For payment cases, asserts the agent asks for confirmation before executing
- Reports pass rate as a single number
- Runs in under 60 seconds total

### STEP 12: run.sh

Create run.sh that:
```bash
#!/bin/bash
# Usage: ./run.sh [--mock] [--seed]
# --mock: run against fixtures (no bunq sandbox needed)
# --seed: re-seed sandbox before starting
```

Steps:
1. Check .env exists and has required keys
2. Activate venv or create one
3. Install deps if needed
4. If --seed, run seed_sandbox.py
5. Start FastAPI server
6. Print the URL and "READY" message
7. Open browser to the UI

## IMPORTANT IMPLEMENTATION NOTES

1. **Every file should have a module docstring** explaining what it does and how it fits the architecture. A teammate joining at 2am should be able to read the docstring and understand.

2. **The mock mode is not optional** — it's your demo insurance policy. Conference wifi WILL fail. The sandbox WILL 500 at the worst moment. Mock mode should be indistinguishable from live for the judges.

3. **The agent loop in loop.py is the single most important file.** Keep it simple. No framework. A while loop, a model call, a tool dispatch. If a new teammate can't read it in 2 minutes, simplify it.

4. **System prompt changes should be treated like code changes.** Put the prompt in prompts.py, not inline. Add comments explaining why each rule exists. Version it.

5. **Cost awareness:** Use claude-haiku-4-5 for categorization and simple tasks, claude-sonnet-4-6 for complex reasoning and vision. This keeps costs under €10 for the whole hackathon.

6. **The demo script matters more than the code.** The 90-second story is:
   - 15s: "Students stress about money. Meet [name], our AI assistant."
   - 30s: HEAR — speak a command, watch the agent execute it live
   - 30s: SEE — snap a receipt, watch it get parsed and split
   - 15s: ACT — trigger a proactive intervention (e.g., "you're about to overspend")

Build the code to serve this script, not the other way around.

## AFTER YOU'RE DONE

Once all files are created:
1. Run the eval harness and report the pass rate
2. Start the server in mock mode and confirm all endpoints work
3. List any [CUSTOMIZE] items that still need team decisions
4. Suggest 3 "wow factor" additions the team could add during the hackathon (e.g., proactive alerts, spending predictions, voice personality)
```

---

## Quick Customization Guide

| If your idea is... | Change these parts |
|---|---|
| **Budget Bouncer** (outlier detection) | Add `detect_outlier` tool, add a background polling loop that checks transactions every 30s, system prompt focuses on proactive warnings |
| **Receipt Radar** (receipt + split) | Beef up receipt parser, add `split_bill` tool that creates multiple request-inquiries, UI emphasizes camera |
| **Bonus Butler** (salary detection) | Add `detect_income` tool, add savings/invest workflow in tools, system prompt includes investment-like options |
| **Student Finance Coach** (proactive modeling) | Add `forecast_30_days` tool that projects cash flow, `create_budget` tool, system prompt is coaching-oriented |

## Tips for Running This Prompt

- **First run:** Paste the whole prompt into Claude Code. It will build everything step by step. Takes about 10-15 minutes.
- **Iterate:** After the first build, use follow-up prompts like "Improve the system prompt to be more conversational" or "Add a spending forecast tool."
- **During hackathon:** The scaffold is ready. Tell Claude Code "We're building [specific idea]. Modify the tools and system prompt for [user story]." It will know what to change because the architecture is clean.
- **If stuck:** "Explain how the agent loop in loop.py works, line by line" — Claude Code can walk your teammates through it.
