# Master Claude Code Prompt — GuardianAI Voice Bot

## Project Name
**GuardianAI** — A voice-first AI banking companion with an on-screen avatar. Users talk to their bank the way they'd talk to a trusted friend.

## Mission
Build a demo of a radically simplified banking interface. Instead of menus, tabs, and forms, the user talks to an animated avatar. The avatar listens, understands, and acts: "send €40 to Lars", "what did I spend on groceries this month?", "split this dinner between me, Anna, and Tom" (with a photo of the bill). The avatar responds by voice and shows lightweight visual confirmations (amounts, names, split results) on the same screen.

The demo closes with a short fraud-intervention moment to show the avatar can also protect the user — but banking-by-avatar is the headline, not fraud.

---

## Target User & Context
- Primary: bunq customers who want effortless banking — no menu hunting, no forms. Especially useful for elderly users, users with accessibility needs, and busy people on the go.
- Context: Hackathon prototype. The demo is the product. Judges must leave remembering *"the bank I talked to."*
- Scope rule: **build the demo, not the platform.** Mock anything that isn't needed for the on-stage story.

---

## Core User Flows

### Flow 1 — Send Money by Voice
1. User opens the app. Avatar greets them by name.
2. User: *"Send €40 to Lars for pizza."*
3. Avatar parses intent → shows a confirmation card on screen (recipient, amount, note).
4. Avatar asks out loud: *"Sending €40 to Lars with the note 'pizza'. Confirm?"*
5. User: *"Yes."*
6. Avatar executes the transfer (mocked or sandbox bunq call), shows a success animation, and says *"Done. €40 to Lars."*

### Flow 2 — Split a Bill from a Photo
1. User: *"Split this bill between me, Anna, and Tom."*
2. Avatar: *"Show me the bill."* → camera opens.
3. User snaps a photo of the restaurant receipt.
4. Claude Vision reads the total, itemizes if visible, handles tip/tax.
5. Avatar shows the split on screen and says: *"Total is €84. That's €28 each. Want me to request €28 from Anna and €28 from Tom?"*
6. User: *"Yes."*
7. Avatar sends payment requests, confirms on screen and by voice.

### Flow 3 — Check Balance & Spending
1. User: *"How am I doing this month?"* or *"What's my balance?"*
2. Avatar pulls transactions (mocked dataset), summarizes by category, and speaks a concise answer.
3. A simple chart appears on screen alongside the avatar's summary.
4. Follow-up questions allowed: *"How much on eating out?"* → avatar answers without re-asking the question.

### Flow 4 — Fraud Moment (Demo Finale)
1. Mid-demo, an SMS notification appears on the user's phone: *"bunq: urgent, verify your account at [suspicious-link]"*.
2. User holds the phone up to the camera and asks the avatar: *"Is this real?"*
3. Claude Vision flags spoofed sender, urgency language, non-bunq URL.
4. Avatar: *"This is a scam. Do not click the link. I've logged it for you."*
5. (Optional) Avatar offers to freeze the card as a precaution — user confirms — one real bunq sandbox call fires.

This flow is 30 seconds of the demo. It shows the avatar can protect, not just transact.

---

## Architecture Overview

```
┌───────────────────────────────┐
│   Web Client (single page)    │
│   ┌─────────────────────────┐ │
│   │  Avatar (3D/2D render)  │ │     voice in/out
│   │  Confirmation UI        │ │  ←────────────────→  Browser Mic + Speakers
│   │  Camera for bill photo  │ │
│   └─────────┬───────────────┘ │
└─────────────┼─────────────────┘
              │ WebSocket / HTTP
              ▼
┌───────────────────────────────┐      ┌──────────────────────┐
│    Backend (Python)           │ ───▶ │  Claude Opus 4.6     │
│    - STT (faster-whisper)     │      │  (voice intent +     │
│    - TTS (ElevenLabs)         │ ◀─── │   vision + tools)    │
│    - Tool router              │      └──────────────────────┘
└──────────┬────────────────────┘
           │
           ▼
┌───────────────────────────────┐         ┌──────────────────────┐
│   Mocked Banking Layer        │         │   AWS S3             │
│   - In-memory accounts        │ ──────▶ │   - Bill photos      │
│   - Seeded 90 days of txns    │         │   - Fraud screenshots│
│   - One real bunq sandbox     │         │   - Audio archive    │
│     call for card freeze      │         └──────────────────────┘
└───────────────────────────────┘
```

### Components
- **Client**: Single-page web app (React + Vite). Renders the avatar, handles mic capture, plays TTS audio, opens camera for bill photos, shows lightweight confirmation cards and charts.
- **Avatar**: Talking-head avatar with lip-sync. See "Avatar choice" below.
- **Backend**: Thin Python or Node server. Handles STT → Claude → TTS pipeline, routes tool calls, serves mocked banking data. No AWS Lambda/DynamoDB/SNS required for the demo.
- **Agent Core**: Claude Opus 4.6 via Anthropic API + Claude Agent SDK. Tool-calling loop drives all banking actions.
- **Vision**: Claude multimodal for bill OCR and scam-SMS analysis.
- **Banking**: Mocked in-memory ledger with seeded transactions (realistic merchant names, categories, amounts). One real bunq sandbox call wired for the fraud moment (card freeze) so judges see a real API hit.
- **Storage**: AWS S3 for user media — bill photos uploaded from the browser, the seeded fraud-SMS screenshot, and (optionally) archived audio clips for post-demo review. Claude Vision reads images by pre-signed S3 URL rather than shipping large base64 payloads through the websocket.

---

## Tech Stack (Definitive)

| Layer | Choice | Why |
| --- | --- | --- |
| LLM | Claude Opus 4.6 (`claude-opus-4-6`) | Reasoning + multimodal + tool use |
| Agent framework | Claude Agent SDK (Python) | Clean tool loop, streaming |
| Avatar | TBD — Ready Player Me + Three.js, OR D-ID / HeyGen video, OR Rive 2D | Visual impact with acceptable build cost |
| STT | `faster-whisper` running locally on the backend | No API key, runs offline on the demo laptop, reliable on stage |
| TTS | ElevenLabs (warm voice) | Natural voice, streamable |
| Client | React + Vite + Tailwind | Fast iteration, no native build |
| Backend | FastAPI (Python) | Pairs with Claude Agent SDK |
| Banking | Mocked ledger (JSON seed) + 1 real bunq sandbox call | Demo realism without integration debt |
| Storage | AWS S3 | Bill photos, fraud-SMS screenshots, optional audio clip archive |
| Auth | Hardcoded demo user | User verification is out of scope |

---

## Avatar Choice (decide before Phase 1)

Three viable options — pick one and commit:

1. **Ready Player Me + Three.js** — free 3D avatars, stylized, lip-sync via viseme mapping from audio. Highest wow factor, moderate build cost. Recommended default.
2. **D-ID / HeyGen streaming API** — photorealistic talking head, lip-sync handled by the service. Lowest build cost, recurring API cost, network dependency on stage.
3. **Rive 2D animated character** — stylized 2D character with mouth-shape keyframes driven by audio. Cute, robust, offline-friendly. Safest option.

Rule: if the avatar breaks or lags on stage, the demo is dead. Pick the option you can make *reliable* in the time you have. A perfectly-lip-synced 2D character beats a broken 3D one.

---

## Repository Layout

```
bunq_hackathon/
├── CLAUDE.md                    # This file
├── README.md
├── .env.example
├── client/                      # React + Vite web app
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── Avatar.tsx           # avatar renderer + lip-sync
│   │   │   ├── ConfirmationCard.tsx # shows transfer/split preview
│   │   │   ├── BillCapture.tsx      # camera for bill photos
│   │   │   ├── SpendingChart.tsx    # lightweight Recharts view
│   │   │   └── Mic.tsx              # push-to-talk + waveform
│   │   └── lib/
│   │       ├── voice.ts             # STT in browser, TTS playback
│   │       └── api.ts               # backend client
│   └── package.json
├── backend/
│   ├── main.py                  # FastAPI entry + websocket
│   ├── agent/
│   │   ├── guardian_agent.py    # Claude Agent SDK loop
│   │   ├── prompts.py           # system prompt below
│   │   └── tools/
│   │       ├── banking_tools.py # send_money, split_bill, list_transactions, get_balance
│   │       ├── vision_tools.py  # analyze_bill, analyze_suspicious_message
│   │       └── safety_tools.py  # freeze_card (real bunq sandbox), log_incident
│   ├── voice/
│   │   ├── stt.py               # faster-whisper (local, loaded on boot)
│   │   └── tts.py               # ElevenLabs
│   ├── storage/
│   │   └── s3.py                # boto3 client: upload media, pre-signed URLs
│   └── mock_bank/
│       ├── ledger.py            # in-memory accounts + contacts
│       └── seed.json            # demo transactions + contacts
└── scripts/
    └── run_local.sh
```

---

## Claude Agent — System Prompt (use verbatim in `backend/agent/prompts.py`)

```
You are GuardianAI, the voice of a bunq customer's bank. You appear as a friendly
on-screen avatar. The user talks to you; you talk back. You help them do their
banking by conversation instead of menus.

What you can do for the user:
- Send money to a contact by name, with an amount and an optional note.
- Split a bill: take a photo of a receipt, read the total, divide it between named
  people, and send payment requests.
- Answer questions about their balance, recent transactions, and spending by
  category.
- Flag suspicious messages or calls they show you, and (with consent) freeze their
  card if something looks wrong.

Behavior rules:
- Speak like a human. Short sentences. One thing at a time.
- Always confirm before moving money. Read back the recipient, amount, and note.
- Never ask for PINs, full card numbers, or 2FA codes. Remind the user that bunq
  will never ask for these either.
- When you see an image, describe what you observe first, then act on it.
- Before calling a tool, tell the user in one short sentence what you are about to
  do.
- If anything is ambiguous (which "Lars"? which amount?), ask — do not guess with
  the user's money.

You have tools to: send money, request money, split a bill, list transactions, get
balance, analyze an image, freeze a card, and log an incident. Use them.
```

---

## Implementation Phases (hackathon-sized)

### Phase 0 — Skeleton (30 min)
- Scaffold `client/` (Vite + React) and `backend/` (FastAPI). Hello-world round trip client ↔ server.

### Phase 1 — Voice loop with static avatar (2 hr)
- Mic capture → STT → Claude (plain chat) → TTS → playback. Avatar displayed as a static image first. Target end-to-end latency <2s per turn.

### Phase 2 — Avatar lip-sync (2 hr)
- Drive the chosen avatar (Ready Player Me / D-ID / Rive) from the TTS audio stream. Verify it looks decent on the demo laptop's screen at demo resolution.

### Phase 3 — Banking tools + confirmation UI (2 hr)
- Implement `send_money`, `get_balance`, `list_transactions` against the mocked ledger. Build the on-screen confirmation card. Wire the avatar to speak the confirmation, user says yes/no, action fires.

### Phase 4 — Bill split via photo (1.5 hr)
- Camera capture in browser → upload to S3 via pre-signed POST → backend hands the S3 URL to Claude Vision → Claude reads the total → split tool divides it → payment request tool (mocked) fires → avatar narrates the result.

### Phase 5 — Spending summary + chart (1 hr)
- `list_transactions` + Claude summarization. Render a small bar chart alongside the avatar. Avatar speaks the headline number.

### Phase 6 — Fraud finale (1 hr)
- Seed a spoofed-SMS screenshot. Avatar flags it via Claude Vision. Wire *one* real bunq sandbox call (card freeze) so judges see a real API request in DevTools.

### Phase 7 — Polish for demo (1 hr)
- Seed compelling contacts and transactions (Lars, Anna, Tom, realistic merchants). Record a screen capture as a backup video. Rehearse the 3-minute pitch.

---

## Demo Script (memorize this)

1. **Intro** (10s): "Banking apps are full of menus. We replaced them with a person you can talk to." Open the app. Avatar says: *"Hi Kunal, what can I help with?"*
2. **Send money** (30s): User: *"Send €40 to Lars for pizza."* Avatar confirms. User says yes. Transfer succeeds on screen.
3. **Split a bill** (45s): User: *"Split this dinner between me, Anna, and Tom."* Holds up a real receipt to the webcam. Avatar reads the total, proposes €28 each, sends the requests.
4. **Spending** (20s): User: *"How much did I spend on eating out this month?"* Avatar: *"€214. That's about 15% more than last month."* Chart appears.
5. **Fraud finale** (30s): Phone buzzes. User shows the SMS to the camera. Avatar: *"That's a scam. Don't click. Want me to freeze your card, just in case?"* User: *"Yes."* Real bunq sandbox call fires, visible in DevTools.
6. **Close** (15s): "One interface. Your voice. Your bank." End.

Total: ~2.5 minutes, leaves 30s for the judges.

---

## Key Implementation Notes for Claude Code

- **Latency rules the demo.** First-audio-byte after user stops speaking: target <800ms. Use Claude streaming + streaming TTS. Start rendering avatar lip-sync as soon as audio bytes arrive, not after the full response.
- **Warm up `faster-whisper` at backend boot.** Load the model into memory on startup and run one dummy transcription so the first real user turn doesn't eat a 2–3s cold start. `base` is a good default; bump to `small` only if accuracy suffers. Prefer the `int8` compute type on CPU for snappier decoding.
- **Tool descriptions matter more than tool code.** Write each tool's docstring as if briefing a new hire: what it does, when to use it, what it returns.
- **Keep banking mocked except the fraud freeze.** One real API call is enough to prove it works. Everything else should be reliable in-memory data.
- **Seed the mock bank with realistic data**: contacts named Lars, Anna, Tom, Sophie; transactions at Albert Heijn, Jumbo, Uber, Spotify, Netflix, local cafés; balance around €3,200; a suspicious-looking SMS screenshot in `seed.json`.
- **Never ask for secrets.** Hard-code a refusal for the agent to request or repeat PINs, full card numbers, or OTPs — even in a "demo, it's fine" framing. Unit-test this.
- **Confirm before every money movement.** No silent transfers, even in the mock. The confirmation card + voice read-back is the product.
- **Graceful degradation.** If STT fails, show a typed input. If TTS fails, show avatar with subtitles. If Claude fails, show a retry button. The demo must never freeze silently.
- **Avatar fallback.** Keep a static image of the avatar ready. If the lip-sync renderer fails on stage, swap to static + subtitles and keep going.

---

## Environment Variables (`.env.example`)

```
ANTHROPIC_API_KEY=
ELEVENLABS_API_KEY=             # warm TTS voice
BUNQ_API_KEY=                   # only used for the fraud-finale card freeze
BUNQ_ENVIRONMENT=SANDBOX
DID_API_KEY=                    # only if using D-ID for the avatar
WHISPER_MODEL=base              # faster-whisper model size: tiny|base|small|medium
AWS_ACCESS_KEY_ID=              # S3 media storage
AWS_SECRET_ACCESS_KEY=
AWS_REGION=eu-west-1
S3_BUCKET=guardianai-media      # bill photos, fraud screenshots, audio archive
```

---

## Success Criteria for Judges
- Live voice conversation with an on-screen avatar — lip-sync visibly working.
- Send-money flow completes with a spoken confirmation and visual receipt.
- Bill-split flow: real photo of a receipt → avatar reads the total → split computed live.
- Spending summary with a chart, answered from real (seeded) transactions.
- Fraud finale: avatar flags a scam SMS and fires one real bunq sandbox call.
- Clean, reliable performance — no frozen avatar, no silence.

---

## Stretch Goals (if time permits)
- Multi-language: switch the avatar's language live (Dutch, German, Spanish) via Claude + matching TTS voice.
- Custom voice clone for the avatar so it sounds like the user's preferred family member.
- Accessibility mode: larger confirmation cards, slower speech, high-contrast UI.
- Offline wake word ("Hey Guardian") for hands-free start.

---

## When in doubt, build the demo, not the platform.
