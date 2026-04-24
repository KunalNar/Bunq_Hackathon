# From Training Models to Building with AI APIs — A Crash Course for the bunq Hackathon

**You:** DSAIT master student, comfortable with PyTorch, training loops, experiments, papers. Not comfortable with: API keys, "prompts", "tool calls", agent frameworks.
**Goal:** In 8 days, become the person who can sit down with a freshly-assigned team on Apr 24 and say "I'll own the agent loop" without bluffing.

Read this top-to-bottom once. Then work through the exercises (Part 7). Each exercise is designed to isolate one concept and should take 20–60 minutes.

---

## Part 1 — The mental model shift

When you train a model, you own the weights. You control the optimization, the loss, the data, the architecture. Your pain points are GPU memory, convergence, and generalization.

When you **build with an AI API**, you do not own the weights. You rent a forward pass. Your pain points are prompts, tool schemas, latency, rate limits, cost, and non-determinism. You treat the model as a very capable but stateless function:

> `output_text = model(input_text, images, audio, tools_available)`

That is it. Every trick in this guide is about making that function do useful work reliably.

What transfers from your research background:
- Rigorous evaluation mindset (you'll need it — the model is non-deterministic).
- Good experimental hygiene (versioned prompts, logged outputs).
- Comfort reading JSON schemas and debugging nested structures.

What is different:
- **No training.** You will not fine-tune anything for this hackathon. You'll prompt, compose, and wrap.
- **The "loss" is vibes.** You assert behavior in test cases and eyeball outputs. There's no scalar to minimize.
- **The system is distributed by default.** Your app calls an HTTP API over the internet. Latency, timeouts, and retries are real concerns.
- **Cost is a hyperparameter.** Every call costs real money. You learn to cache, batch, and pick cheaper models when possible.

Mental picture for the hackathon:

```
   user voice  ─▶ ASR ─▶ text ─┐
   user photo ─▶ vision model ─┤
                               │
                               ▼
                         ┌──────────┐      ┌─────────────┐
                         │   LLM    │◀────▶│ your tools  │ ← bunq sandbox calls
                         │  (brain) │      │ (functions) │
                         └──────────┘      └─────────────┘
                               │
                               ▼
                    text/actions ─▶ TTS / UI
```

The **LLM is the brain**. Your code is the **body** that lets it hear, see, and act.

---

## Part 2 — Your first API call, properly understood

The Anthropic and OpenAI APIs both follow the same pattern. You send a list of messages, you get a response. Models are stateless — you resend the full conversation every turn.

### Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install anthropic openai python-dotenv
```

Create a `.env` file:

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

Load it with `dotenv` — **never** hard-code keys.

### The minimal call

```python
import os
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()
client = Anthropic()

resp = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    system="You are a concise financial assistant for Dutch students.",
    messages=[
        {"role": "user", "content": "I spent €12 on lunch. What category is this?"},
    ],
)

print(resp.content[0].text)
```

Things to notice:
- `system` is a separate parameter, not a message. It's your "persona / rules" prompt.
- `messages` is the running conversation. For a multi-turn chat, you keep appending `{"role": "assistant", "content": ...}` and new `{"role": "user", ...}` entries.
- `max_tokens` bounds the response. Set it; otherwise a runaway response will cost you.
- `temperature` defaults to 1.0. For structured tasks (categorization, JSON extraction), use `0` — you want determinism.

### Key parameters, in one table

| Param | What it does | Hackathon default |
|---|---|---|
| `model` | Which model to call | `claude-sonnet-4-6` for reasoning, `claude-haiku-4-5` for fast/cheap |
| `max_tokens` | Hard cap on response length | 1024 for chat, 256 for classification |
| `temperature` | Randomness (0 = deterministic) | 0 for structured tasks, 0.7 for creative |
| `system` | Instructions that apply to all turns | Describe role, tone, hard rules |
| `messages` | The conversation so far | Always ends with a `user` turn |
| `stop_sequences` | Strings that halt generation | Usually unused |

### Prompting: the part that replaces model tuning

You will iterate on prompts the way you iterate on loss functions. Good habits:

- **Write the system prompt like a job description**, not like a conversation. "You are X. You have access to Y. You must Z. You never W."
- **Show, don't tell.** If you want a specific output shape, include 1–3 examples in the prompt. This is "few-shot" and it works.
- **Pin the output format.** "Respond with JSON matching this schema: {...}. Do not include prose."
- **Keep a changelog.** Every time you change the prompt, note what moved. You will forget.

---

## Part 3 — Multi-modal: images and audio

### Images in (vision)

Claude and GPT-4o both accept images as base64 or URLs. For a receipt, base64 is what you'll use (it's a local file).

```python
import base64
from pathlib import Path

img_b64 = base64.b64encode(Path("receipt.jpg").read_bytes()).decode()

resp = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[{
        "role": "user",
        "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
            {"type": "text", "text": "Extract merchant, total, currency, and date as JSON."},
        ],
    }],
)
```

What modern vision models can do out of the box:
- Read printed and handwritten text (receipts, signs, whiteboards).
- Extract structured data (tables, forms, invoices).
- Describe scenes, count objects, identify layouts.

What they still struggle with:
- Very small text in low-res photos.
- Non-Latin scripts when quality is poor.
- Spatial reasoning ("which is to the left of what") past a certain complexity.

### Audio in (speech-to-text, "ASR")

The standard tool is **Whisper** (open-source, also on OpenAI's API) or streaming services like Deepgram and AssemblyAI.

Two flavors:

1. **File-based (simpler):** record → save wav → send to API → get transcript. Latency: 1–3s for a short clip. Use this at the hackathon — it's reliable.
2. **Streaming (harder, cooler):** WebSocket → partial transcripts as the user talks. Skip unless you already know WebSockets.

File-based with OpenAI:

```python
from openai import OpenAI
oai = OpenAI()

with open("command.wav", "rb") as f:
    transcript = oai.audio.transcriptions.create(
        model="whisper-1",
        file=f,
    )
print(transcript.text)
```

Running Whisper locally (no API call) is also fine on a Mac with `pip install openai-whisper` or faster with `faster-whisper`. Useful if conference wifi dies.

### Audio out (text-to-speech, "TTS")

Options, roughly best-to-worst for a demo:
- **ElevenLabs** — best voice quality, paid, fast API.
- **OpenAI TTS** (`tts-1` / `tts-1-hd`) — good quality, cheap, one line of code.
- **macOS `say` command** — free, sounds like 2005, runs offline.

Demo-quality TTS adds a huge amount of polish. It's worth the €5 in credits for the hackathon.

---

## Part 4 — Tool use (aka "function calling") — the most important concept for this hackathon

This is the concept that turns a chatbot into an **agent** that can move money. Spend real time here.

### The idea

You give the model a list of *tools it can call*. Each tool is a function in your code, described with a JSON schema (name, description, parameters). When the model decides it needs to call one, it doesn't execute code — it emits a structured request. *Your code* runs the function and hands the result back. The model continues from there.

### The loop

```
1. You: "Move €50 from checking to savings."
2. Your code → model (with tools=[create_payment, get_balance, ...])
3. Model → "I want to call create_payment(from='NL01...', to='NL02...', amount=50)"
4. Your code executes create_payment via bunq API
5. Your code → model with the tool result ("ok, transaction_id=abc")
6. Model → "Done. Your new savings balance is €1,234."
7. You: see the confirmation
```

This loop may go several rounds: the model might first call `get_balance` to check, then call `create_payment`. That's fine — you just keep looping until the model produces a final answer with no tool call.

### Minimal implementation

```python
import json
from anthropic import Anthropic
client = Anthropic()

# 1. Define tools — JSON Schema for the inputs.
tools = [
    {
        "name": "get_balance",
        "description": "Return the current balance of the user's primary account in EUR.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "create_payment",
        "description": "Transfer money from one of the user's accounts to another.",
        "input_schema": {
            "type": "object",
            "properties": {
                "from_iban": {"type": "string"},
                "to_iban": {"type": "string"},
                "amount_eur": {"type": "number"},
                "description": {"type": "string"},
            },
            "required": ["from_iban", "to_iban", "amount_eur"],
        },
    },
]

# 2. Your real functions — these actually call bunq sandbox.
def get_balance():
    return {"balance_eur": 1284.50}

def create_payment(from_iban, to_iban, amount_eur, description=""):
    return {"status": "ok", "tx_id": "abc123"}

TOOL_IMPLEMENTATIONS = {
    "get_balance": get_balance,
    "create_payment": create_payment,
}

# 3. The loop.
messages = [{"role": "user", "content": "Move 50 euros to my savings account."}]

while True:
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system="You are a bunq financial assistant. Use tools to take actions.",
        tools=tools,
        messages=messages,
    )

    # Append the assistant's turn (can contain text + tool_use blocks).
    messages.append({"role": "assistant", "content": resp.content})

    if resp.stop_reason != "tool_use":
        # Model is done — just text output.
        final_text = "".join(b.text for b in resp.content if b.type == "text")
        print(final_text)
        break

    # Otherwise execute every tool_use block and return tool_result.
    tool_results = []
    for block in resp.content:
        if block.type == "tool_use":
            fn = TOOL_IMPLEMENTATIONS[block.name]
            result = fn(**block.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result),
            })

    messages.append({"role": "user", "content": tool_results})
```

If you understand this 30-line loop, you understand 80% of what people mean by "AI agent." Frameworks like LangGraph and the Claude Agent SDK wrap this with niceties (state, retries, memory, tracing) but the core is the same.

### Designing good tools

This is a craft. A few rules:

- **Names are prompts.** `create_payment` is better than `cp`. `list_recent_transactions` is better than `list_tx`. The model reads them.
- **Descriptions are where you put the "how to use this."** "Use only when the user has explicitly confirmed the amount and recipient."
- **Keep schemas tight.** Every extra parameter is a chance for the model to hallucinate a value. Required fields only if truly required.
- **Fewer, sharper tools beat many fuzzy ones.** 5–8 well-named tools for this hackathon is plenty.
- **Return structured data**, not prose. JSON objects the model can reason over.
- **Include error shapes.** On failure, return `{"error": "insufficient_funds", "available_eur": 12.30}`. The model can recover. If you throw, it can't.

---

## Part 5 — Agents in practice

An "agent" is just the tool-use loop above, possibly with more structure: memory, retries, subagents, long-running plans. For a 24-hour hackathon you want the **simplest thing that works**.

### Should you use a framework?

| Option | Pros | Cons |
|---|---|---|
| Write the loop yourself (≈50 LoC) | Full control, zero install, easy to debug | You manage state manually |
| Claude Agent SDK | Minimal abstraction over the loop, good Anthropic ecosystem fit | Newer, fewer StackOverflow answers |
| LangGraph | Rich graph-based state machines, visualization | Steep learning curve in 8 days |
| smolagents (HuggingFace) | Tiny, readable | Less battle-tested |

My honest recommendation: **write the loop yourself first (Exercise 4 below).** Once you've built it by hand, you'll know what a framework is abstracting and whether it's worth adopting. Most hackathon wins I've seen used a 100-line custom loop.

### System-prompt patterns that earn points

For a financial agent, these earn trust from judges:

- A **confirmation step** before any money-moving action: "I'm about to move €50 from X to Y. Confirm?"
- A **budget / guardrail** rule: "Never initiate a payment over €200 without explicit user confirmation."
- A **refusal path** for unclear requests: "If the user's command is ambiguous about amount or recipient, ask one clarifying question."
- An **audit log** the agent writes to: "Before completing any action, call `log_action(description)`."

### Evaluation

Even over 24 hours, you should have an eval. The shape that works:

```python
CASES = [
    {
        "user": "Pay my rent 700 to NL12RABO0123456789.",
        "must_call": {"name": "create_payment", "args": {"amount_eur": 700}},
    },
    {
        "user": "Am I broke?",
        "must_call": {"name": "get_balance"},
    },
    # ... 15–20 of these
]
```

Run them all in CI or a script; assert the first tool call name matches. This catches regressions when you tweak the system prompt at 03:00.

---

## Part 6 — The bunq sandbox, concretely

### The concept

bunq is a Dutch neobank with a public API (300+ operations). You won't touch real money — you get a **sandbox**: fake users, fake money, same endpoints. Base URL: `https://public-api.sandbox.bunq.com/v1/`.

### The auth model (read this once, then let the SDK handle it)

bunq uses a three-step authentication dance. You will not hand-roll this; the SDK does it.

1. **Installation**: your client announces itself, gets a token.
2. **Device-server**: your device registers and is pinned to an IP.
3. **Session-server**: you exchange the above for a short-lived session token.

Only then can you call endpoints like `/payment`, `/request-inquiry`, `/monetary-account`.

### The steps to "hello, money moved"

1. Make a developer account at bunq's developer portal.
2. Generate a sandbox API key (you can have up to 5 sandbox users).
3. `pip install bunq-sdk`.
4. Initialize with your key — the SDK writes an "api context" file that contains all three tokens above.
5. Call Sugar Daddy to fund an account by sending a `request-inquiry` to `sugardaddy@bunq.com` for up to €500.
6. Make a payment from one of your sandbox accounts to another. That's the "hello world" for this hackathon.

You will spend most of this work **once**. From then on you call endpoints like any HTTP API.

### Endpoints you likely want

- `GET /user` — who am I
- `GET /user/{id}/monetary-account` — list accounts (checking, savings, sub-accounts)
- `GET /user/{id}/monetary-account/{id}/payment` — list payments (transactions)
- `POST /user/.../payment` — create a payment
- `POST /user/.../request-inquiry` — request money from someone (useful for splitting)
- `POST /user/.../monetary-account-savings` — create a sub-account (savings goal)

### Links

- Main docs: <https://doc.bunq.com/>
- Sandbox basics: <https://beta.doc.bunq.com/basics/sandbox>
- First payment walkthrough: <https://doc.bunq.com/tutorials/your-first-payment/creating-a-sandbox-user-and-getting-an-api-key>

---

## Part 7 — The exercises (do these between Apr 17 and Apr 22)

Each exercise is one concept. Don't skip ahead. Commit each to a git repo — you'll reuse the snippets.

### Exercise 1 — Hello, Claude (Apr 17, ~20 min)

Goal: get an API key, make your first call.

- Sign up for Anthropic console, add €5 credit.
- Install `anthropic`, put your key in `.env`.
- Run the minimal call from Part 2.
- **Stretch**: turn it into a 3-turn conversation where you resend the full `messages` list each turn.

**What you should feel afterwards:** "OK, this is just HTTP. The 'model' is a function that takes a list of messages and returns text."

### Exercise 2 — Structured output from a receipt image (Apr 18, ~45 min)

Goal: point Claude at a photo of a receipt, get back validated JSON.

- Take photos of 5 real receipts (lunch, groceries, a bar). Save as `receipts/*.jpg`.
- Write a function `parse_receipt(path: str) -> dict` that returns `{merchant, total, currency, date, line_items}`.
- Use `temperature=0`, a strict system prompt with the schema, and a low `max_tokens`.
- Validate the output with `pydantic` — if it fails the schema, retry up to 2 times.

**What you should feel afterwards:** "I can extract structured data from images reliably enough to build on."

### Exercise 3 — Voice in, voice out (Apr 19, ~45 min)

Goal: "I spent twelve euros on lunch" → spoken reply "Categorized as Food, €12".

- Record a 5-second wav with `sounddevice` or your Mac's built-in.
- Transcribe with Whisper (local or OpenAI API).
- Send the transcript to Claude with a categorization prompt.
- Play the response with OpenAI TTS or `say`.

**What you should feel afterwards:** "Multi-modal is mostly gluing pipes together."

### Exercise 4 — Tool-using agent against a fake bank (Apr 20, ~90 min)

Goal: the 30-line loop from Part 4, against a Python dict that pretends to be a bank.

- Define 4 tools: `get_balance`, `list_transactions`, `create_payment`, `categorize_transaction`.
- Back them with an in-memory dict of accounts and transactions.
- Try these commands: "What's my balance?" / "Show my last 5 transactions." / "Move €50 to savings." / "Categorize my last transaction."
- Watch the message list grow over each turn. Print every tool call before executing.

**What you should feel afterwards:** "An agent is a loop. I own the loop. Nothing magical is happening."

### Exercise 5 — Wire to the real bunq sandbox (Apr 21, ~90 min)

Goal: replace the fake bank from Exercise 4 with the bunq sandbox.

- Set up sandbox account, generate API key, install `bunq-sdk`.
- Replace each tool's body with real bunq SDK calls.
- Seed your sandbox with 2–3 users and some Sugar Daddy money.
- Run the same commands. Watch sandbox balances change in the bunq dev portal.

**What you should feel afterwards:** "I could build the hackathon project right now. I'm going to let the team shape the idea, but the plumbing doesn't scare me."

### Exercise 6 — Evaluate it (Apr 22, ~45 min)

Goal: 15 scripted user commands, asserted tool calls.

- Write a `cases.yaml` or `cases.py` with user input and expected tool name.
- Write a test runner that feeds each case to your agent and checks the first tool call.
- Report a pass rate.

**What you should feel afterwards:** "I have the one thing most hackathon teams don't: a number to optimize."

---

## Part 8 — Day-of, when you're assigned a team

Because this is your first hackathon and your team forms on the day, here's what to do in the first 90 minutes:

1. **Introductions, 10 min.** Name, strengths, what each person has prepped. Mention you've done Exercises 1–6 — people will listen.
2. **Pick a user, not a feature, 20 min.** "Dutch students living on €1400/month" is a user. "Receipt categorization" is a feature.
3. **Pick one killer moment, 15 min.** The 15-second thing on stage that makes a judge say "oh." Everything else serves this moment.
4. **Divide by modality, 15 min.** Speech person, vision person, agent/tools person, frontend/demo person.
5. **Set a 6-hour checkpoint, 5 min.** "By 16:00 we have end-to-end hello-world: voice comes in, agent replies. Ugly is fine."
6. **Then build, 25 min.** Get everyone unblocked on their first task. Then stop meeting and start coding.

Things that go wrong on day one that you can prevent:

- **Scope creep.** The single best skill at a hackathon is killing features. Say no loudly.
- **Modality silos.** Each person builds their piece in isolation and they don't fit at hour 20. Force an integration checkpoint every 4 hours.
- **Unversioned prompts.** Someone tweaks the system prompt on main, everything regresses, no one knows why. Commit prompt changes like code.
- **No demo rehearsal.** Rehearse the 90-second demo at least twice before the final presentation. On stage, wifi will betray you.

---

## Part 9 — A reading shortlist (pick 2 of these, don't read them all)

- Anthropic's guide to tool use: <https://docs.claude.com/en/docs/agents-and-tools/tool-use/overview>
- Anthropic's "Building effective agents" (canonical): <https://www.anthropic.com/research/building-effective-agents>
- OpenAI's cookbook on function calling: <https://cookbook.openai.com/>
- The `bunq-sdk-python` README: <https://github.com/bunq/sdk_python>

---

## TL;DR of the TL;DR

- An API is a function: `messages in → messages out`. Everything else is packaging.
- **Tool use** is the concept that turns a chat model into an agent. Learn it cold.
- You can build the plumbing for this hackathon in ~200 lines of Python. The hard part is the idea and the demo.
- Do Exercises 1–6 this week. You'll arrive on Apr 24 with hands-on reps that most first-time hackathon attendees don't have.

You've got this. The research muscle you already have — rigor, evaluation, debugging — is the rarer half of this skillset. The API half is just practice.
