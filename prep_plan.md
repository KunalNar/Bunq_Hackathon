# bunq Hackathon 7.0 — 8-Day Prep Plan

**Event:** April 24–25, 2026 (overnight) · bunq HQ, Amsterdam
**Theme:** Multi-modal AI that acts — hear, see, intervene
**Prize:** €5,000 · teams up to 4 · AWS + Anthropic mentors on site
**You:** DSAIT @ TU Delft · 8 days to prep (Apr 16 → Apr 24)

The goal of this document is **not** to build the project in advance (that's against the spirit). It is to make sure that at 09:00 on Apr 24, the only thing you're doing is *thinking*, not *installing things*, *begging the bunq sandbox for an API key*, or *debugging CUDA*.

---

## Guiding principles

1. **Pick a sharp user story, not a platform.** "Proactively stop Lisa from over-spending on weekends" beats "a general finance assistant."
2. **Ship the demo, not the system.** A judge's attention is 3–5 minutes. Every hour before the hackathon should reduce the time-to-wow on stage.
3. **All three modalities, one thin thread.** Hear → see → act. Don't split energy building three disjoint demos.
4. **Pre-bake everything that isn't the idea.** Auth, bunq connection, model loading, a voice intake, a receipt parser, a demo UI shell — all should be ready to plug in.
5. **Have an offline fallback for every network dependency.** Conference wifi dies. Sandboxes 500. Cache the bunq sandbox responses, mock them if needed.

---

## Workstream 1 — Team & logistics

- [ ] Confirm team (up to 4). DSAIT classmates are ideal — speech/NLP, CV, systems, product/design is a balanced split.
- [ ] Create a shared **Notion / Linear / Google Doc** and a **Discord/Slack** channel.
- [ ] Register on the official hackathon page and confirm team names match: <https://www.bunq.com/hackathon>
- [ ] Book Delft → Amsterdam transport. NS intercity Delft → Amsterdam Centraal is ~55 min; leave 2h buffer on Apr 24.
- [ ] Check the venue address and arrival instructions in the confirmation email. Plan a fallback if the first train is cancelled.
- [ ] Decide who brings what (monitors, HDMI, USB hub, power strip, extension cord).

## Workstream 2 — Idea shortlist (pick one by Apr 22)

Write one sentence for each, then kill all but one. Bias toward ideas where the **agent acts** (moves money, blocks a transaction, categorizes) rather than just talks.

- [ ] **"Budget Bouncer"** — Agent monitors a sandbox account, detects outlier spend live, pushes a voice warning + pauses the transaction (or moves €X to a savings sub-account).
- [ ] **"Receipt Radar"** — Voice command "I just paid for lunch" → camera snaps receipt → agent categorizes, splits with housemates via bunq Request Inquiry, books it against a budget.
- [ ] **"Bonus Butler"** — Detect an incoming salary/bonus (amount > rolling average), ask user via voice "invest / save / spend?", execute: move to a savings sub-account, schedule a payment, or top up a goal.
- [ ] **"Student Finance Coach"** — Proactively models your next 30 days from sandbox transactions and intervenes the moment a decision would break rent month-end.

## Workstream 3 — bunq sandbox setup (do this on Apr 17)

Everything you need to get to a working `POST /payment` on the sandbox:

- [ ] Create a developer account and generate a **sandbox API key**: <https://doc.bunq.com/tutorials/your-first-payment/creating-a-sandbox-user-and-getting-an-api-key>
- [ ] Base URL: `https://public-api.sandbox.bunq.com/v1/`
- [ ] Read the auth model: installation → device-server → session-server → endpoint calls. See <https://doc.bunq.com/basics/authentication/api-keys>
- [ ] Use an SDK instead of hand-rolling auth: Python SDK `bunq-sdk` or TS SDK.
- [ ] Open a session, top up with "Sugar Daddy" (up to €500/request) by sending a `request-inquiry` to `sugardaddy@bunq.com`.
- [ ] Spin up **at least 3 sandbox users** — one "spender", one "housemate", one "savings". Lets you demo transfers.
- [ ] Seed each account with ~20 realistic transactions (groceries, rent, coffee). Script this so you can reset mid-demo.
- [ ] Store sandbox fixtures to disk — if the sandbox is flaky on Apr 24, you switch to replay mode.

## Workstream 4 — Multi-modal stack decisions (do this by Apr 19)

### "Hear" — speech in

- [ ] Pick an ASR: **Whisper (large-v3 or distil-whisper)** runs locally on M-series Macs; alternatively **Deepgram / ElevenLabs / AssemblyAI** for streaming.
- [ ] Test wake-word latency if you want push-to-talk — skip wake-word for the hackathon, use a button.
- [ ] Decide TTS for agent replies: **ElevenLabs Flash** (natural, paid), **macOS `say`** (free, ugly), or **Coqui / Kokoro** for local.
- [ ] If doing streaming ASR, get WebSockets working end-to-end **before** the hackathon.

### "See" — vision in

- [ ] For receipts: **Claude Sonnet 4.6 vision** is excellent OOTB — no training needed. GPT-4o, Gemini 2.5 also work. Pick one and commit.
- [ ] Have 10–20 real receipt photos (crumpled, angled, Dutch/English) in a `fixtures/receipts/` folder. Test extraction on each.
- [ ] Define a strict JSON schema for the parse output (merchant, total, currency, date, line items, category_guess). Use structured output / tool schemas.

### "Act" — agent + tools

- [ ] Pick an agent framework: **Claude Agent SDK**, LangGraph, or a minimal custom loop. For a 24-hour hack, the smallest thing that works beats the fanciest.
- [ ] Define 5–8 tools up front — examples: `list_transactions`, `get_balance`, `create_payment`, `create_request_inquiry`, `categorize_transaction`, `create_savings_goal`, `freeze_card`, `notify_user`.
- [ ] Map each tool to a bunq endpoint and mock it so you can demo without the sandbox if needed.
- [ ] Write an eval harness: 15 scripted conversations where you assert the agent called the right tool with the right arguments.
- [ ] Anthropic mentors will be on site — your stack should show off what Claude does well (tool use, vision, long-context reasoning over transaction history).

## Workstream 5 — Scaffold (build this on Apr 20–21)

Target repo layout — build it empty, check it in, make sure it runs:

```
repo/
├── README.md                    # judge-readable, < 1 screen
├── .env.example                 # BUNQ_API_KEY, ANTHROPIC_API_KEY, ...
├── pyproject.toml               # or package.json if you go TS
├── fixtures/
│   ├── receipts/*.jpg
│   └── transactions.json        # replay mode
├── src/
│   ├── bunq/                    # thin SDK wrapper, context manager for session
│   ├── agent/                   # agent loop, tool definitions, prompts
│   ├── speech/                  # ASR + TTS wrappers
│   ├── vision/                  # receipt parser
│   └── app.py                   # FastAPI + WebSocket for the demo UI
├── web/                         # minimal frontend (Next/SvelteKit), mic + camera
└── scripts/
    ├── seed_sandbox.py          # create users, fund them, seed transactions
    └── reset_demo.py            # nukes and re-seeds — runnable in < 30s
```

- [ ] `make dev` brings everything up locally.
- [ ] "Hello world" agent call works end-to-end against sandbox.
- [ ] Demo UI shows mic input, camera capture, a transaction list, and a chat panel.

## Workstream 6 — Demo script (draft this on Apr 22)

Judges remember the 90-second story, not the architecture. Write the script *first*, then cut features that don't serve it.

- [ ] 15s intro — the one-line problem (money is stressful for students in Delft on €1400/mo).
- [ ] 30s **hear** — you speak a command, the agent executes it live against bunq sandbox, balances update on screen.
- [ ] 30s **see** — snap a receipt, the agent categorizes and splits with a housemate via `request-inquiry`.
- [ ] 30s **intervene** — trigger a risky transaction, agent interrupts with a voice warning and offers an alternative (move €50 to savings instead).
- [ ] 15s outro — the architecture in one slide, the evaluation number in another.
- [ ] Screen-record the whole demo on Apr 22 as a fallback to play if anything breaks on stage.

## Workstream 7 — Overnight survival kit

Pack on Apr 23:

- [ ] Laptop + **spare** charger (different wall socket, different USB-C cable).
- [ ] Portable monitor or ask your teammate to bring theirs — dev speed doubles.
- [ ] Wired mouse + keyboard (bluetooth dies).
- [ ] USB-C hub with HDMI for final demo, Ethernet for when wifi dies.
- [ ] Noise-cancelling headphones.
- [ ] Change of clothes, toothbrush, deodorant, slippers. You will feel human again at 04:00.
- [ ] Snacks you actually like (bunq provides food but you'll want something that's yours at 03:00).
- [ ] Caffeine plan: pace it. No coffee after 02:00 if you want to sleep at 06:00.
- [ ] A **sleep plan**. Two 90-min naps (midnight and 06:00) beats one 3h sleep. One person "on watch" per shift.
- [ ] Portable battery pack for phone — coordinating with team on Discord is easier when phone is alive.

## Workstream 8 — Risk register (keep updated)

- [ ] **Sandbox down** → switch to replay mode using recorded fixtures.
- [ ] **Wifi dies** → phone hotspot, Ethernet in hub.
- [ ] **Anthropic / OpenAI rate limit** → have a second API key from a teammate; cache answers for the demo path.
- [ ] **CUDA/Whisper won't load** → fall back to Deepgram HTTP / OpenAI ASR.
- [ ] **Team member no-shows** → demo script must be runnable by any single teammate.

---

## Day-by-day summary

| Day | Date | Focus |
|---|---|---|
| Thu | Apr 16 | Team confirmed, chat channel, shared doc, this plan reviewed |
| Fri | Apr 17 | bunq sandbox key, SDK imported, "hello world" payment in sandbox |
| Sat | Apr 18 | Idea shortlist → one idea. Write the 90s demo script (rough). |
| Sun | Apr 19 | Stack decisions locked. Whisper + vision + agent loop chosen. |
| Mon | Apr 20 | Scaffold repo, seed script, eval harness (skeleton) |
| Tue | Apr 21 | Each modality has a "hello world" — mic → ASR → stdout, image → JSON, agent → tool call |
| Wed | Apr 22 | Dry-run the 90s demo end-to-end against sandbox. Record it. |
| Thu | Apr 23 | Pack the survival kit. Rest. Go to bed at 22:00 sharp. |
| Fri | Apr 24 | Arrive 45 min early. Deep breath. Start building the *idea*, not the plumbing. |

---

## Key links

- Hackathon page: <https://www.bunq.com/hackathon>
- bunq API docs (main): <https://doc.bunq.com/>
- bunq API docs (beta): <https://beta.doc.bunq.com/>
- Sandbox basics: <https://beta.doc.bunq.com/basics/sandbox>
- First payment tutorial: <https://doc.bunq.com/tutorials/your-first-payment/creating-a-sandbox-user-and-getting-an-api-key>
- Authentication: <https://doc.bunq.com/basics/authentication/api-keys>
- Developers portal: <https://doc.bunq.com/getting-started/tools/developers-portal>
- Past Hackathon 6 projects (steal shape, not ideas): <https://bunq-hackathon.devpost.com/project-gallery>

Good luck. Ship the demo, sleep when you can, and don't argue with the sandbox at 04:00.
