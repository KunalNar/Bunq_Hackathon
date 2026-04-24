# GuardianAI

> An AI voice companion that protects bunq customers from fraud in the moment it happens — and helps them manage their money the rest of the time.

Built for the bunq hackathon.

---

## The Problem

Scams are faster than support lines. By the time a victim calls their bank, the money is gone and the damage is done. Elderly users, rushed users, and users under social-engineering pressure need an intervention that is *always on*, speaks back to them, and can actually *do things* — freeze the card, alert family, file the report — without a human agent in the loop.

## The Solution

GuardianAI is a voice-first, multimodal AI agent that users talk to the instant something feels wrong. It sees what they see (screenshots, photos of caller IDs, suspicious SMS), hears them out, and takes protective action across their bunq account and their personal support network. When there's no emergency, the same assistant quietly analyzes the user's spending and gives useful financial advice.

---

## Key Capabilities

### Fraud Intervention
- **Live voice conversation** with a calm, coaching tone.
- **Screen + photo analysis** via Claude multimodal to flag scam signals (spoofed sender, urgency language, non-bunq IBANs, crypto wallets, suspicious URLs).
- **One-tap card freeze** through the bunq API.
- **Payee blocking** to stop in-flight transfers.
- **Fraud report filing** direct to the bunq fraud endpoint.
- **Emergency contact alerts** by SMS and email — with a human-readable incident summary.
- **Incident logging** to AWS for later review and, if needed, for law enforcement.

### Passive Monitoring
- Background anomaly detection over transaction streams (large transfer, new IBAN, geo/time outliers, rapid sequence of debits).
- Proactive push to the user — "Did you just authorize a €2,400 transfer to an IBAN in another country?"

### Financial Wellness
- Transaction categorization over 90-day history.
- Subscription creep detection.
- Savings trajectory and budget coaching.
- Spoken weekly summary + optional auto-move to a bunq savings sub-account.

### Privacy & Consent
- End-to-end encryption at rest (AWS KMS) and in transit (TLS).
- Explicit consent prompt before any tool call that moves money or contacts a third party.
- One-click data deletion endpoint.
- Hard-coded refusal to ever ask for PINs, OTPs, or full card numbers.

---

## Tools & Technologies

### Core Intelligence
| Tool | Role |
| --- | --- |
| **Claude Opus 4.6** (`claude-opus-4-6`) | Main reasoning model for dialogue, tool-calling, and vision |
| **Claude Agent SDK** (Python) | Tool-calling loop, streaming, session management |
| **Claude Multimodal API** | Screenshot and photo scam detection |

### Voice Pipeline
| Tool | Role |
| --- | --- |
| **AWS Transcribe Streaming** | Real-time speech-to-text |
| **AWS Polly (Neural)** | Text-to-speech with natural voice |
| **WebSocket (API Gateway)** | Bidirectional audio streaming |

### Cloud & Data (AWS)
| Tool | Role |
| --- | --- |
| **AWS Lambda** | Serverless compute for agent, voice, monitoring |
| **Amazon S3** | Encrypted storage for media, screenshots, transaction exports |
| **Amazon DynamoDB** | User profiles, emergency contacts, incident log |
| **AWS KMS** | Key management for at-rest encryption |
| **AWS SNS** | Fan-out alerts to emergency contacts and the user |
| **AWS EventBridge** | Scheduled passive monitoring jobs |
| **AWS Cognito** | User authentication |
| **AWS SAM / CDK** | Infrastructure as code |

### Banking Integration
| Tool | Role |
| --- | --- |
| **bunq Public API (sandbox)** | List accounts, list transactions, freeze card, block payee, file fraud report, move to savings |
| **bunq OAuth** | User-consented access to their account |

### Alerts & External Comms
| Tool | Role |
| --- | --- |
| **Twilio SMS** | SMS to emergency contacts |
| **AWS SES** | Email to emergency contacts |
| *(stretch)* **Twilio Voice + ElevenLabs** | Voice call to contacts using a familiar cloned voice |

### Client
| Tool | Role |
| --- | --- |
| **Expo / React Native** | iOS + Android app |
| **react-native-webrtc** | Mic capture, screen capture |
| **Expo Camera** | Photo of suspicious content |
| **Recharts / Victory Native** | Spending charts in the advice view |

---

## Architecture

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│  Mobile/Web UI  │ ──────▶ │   Voice Gateway  │ ──────▶ │  Claude (Opus)  │
│  (React Native) │ ◀────── │ (Transcribe+Polly)│ ◀────── │  Agent Orchest. │
└────────┬────────┘         └──────────────────┘         └────────┬────────┘
         │                                                         │
         │ screen/photo                                             │ tool calls
         ▼                                                         ▼
┌─────────────────┐                                    ┌─────────────────────┐
│ Claude Vision   │                                    │  Tool Layer         │
│ (scam detection)│                                    │  - bunq API         │
└─────────────────┘                                    │  - AWS (S3/Dynamo)  │
                                                       │  - SNS / Twilio     │
                                                       └─────────────────────┘
```

---

## Agent Tools (the actions Claude can take)

These are the concrete tools exposed to the Claude agent via the Agent SDK. Each is a Python function with a descriptive docstring that Claude reads to decide when to call it.

### Banking (bunq)
- `list_recent_transactions(user_id, days=30)` — fetch recent activity for the user.
- `get_account_summary(user_id)` — balances across all sub-accounts.
- `freeze_card(user_id, card_id, reason)` — immediately block a card.
- `block_payee(user_id, iban, reason)` — prevent any payment to an IBAN.
- `report_fraud(user_id, incident_id, summary)` — file a formal report with bunq.
- `move_to_savings(user_id, amount, from_account, to_account)` — sweep money for safety or budgeting.

### Alerts
- `notify_emergency_contact(user_id, contact_id, message, channel="sms")` — reach a pre-registered contact.
- `notify_all_emergency_contacts(user_id, message)` — broadcast.
- `push_alert_to_user(user_id, message)` — device push for passive monitoring findings.

### Storage
- `log_incident(user_id, incident)` — write the full incident record to DynamoDB + S3.
- `fetch_user_profile(user_id)` — preferences, contacts, consent flags.
- `fetch_incident_history(user_id)` — prior incidents for context.

### Vision
- `analyze_screenshot(image_url)` — Claude multimodal call, returns risk score + red flags.
- `analyze_photo(image_url)` — for caller-ID shots, letters, packaging.

### Analysis
- `categorize_transactions(user_id, range)` — returns category breakdown.
- `detect_anomalies(user_id, range)` — statistical + LLM-judged outliers.
- `generate_financial_summary(user_id, range)` — spoken-format summary + chart JSON.

---

## Getting Started

### Prerequisites
- AWS account with admin access (for SAM deploy)
- bunq sandbox API key — [create one here](https://doc.bunq.com/)
- Anthropic API key — [console.anthropic.com](https://console.anthropic.com/)
- Twilio account (trial is fine)
- Node 20+, Python 3.11+, Expo CLI

### Setup
```bash
git clone <this repo>
cd bunq_hackathon
cp .env.example .env
# Fill in .env with your keys

# Backend
cd backend
pip install -r requirements.txt
sam build && sam deploy --guided

# Frontend
cd ../frontend/app
npm install
npx expo start
```

### Seed demo data
```bash
python scripts/seed_sandbox_data.py
```

### Run the demo flow
1. Open the app on your phone.
2. Tap **Talk to Guardian**.
3. Say: *"Someone is pressuring me to transfer money to a safe account."*
4. Take a screenshot of a sample scam SMS when prompted.
5. Watch Guardian freeze the card, alert your demo contact, and log the incident.

---

## File Structure

```
bunq_hackathon/
├── CLAUDE.md                    # Master prompt for Claude Code
├── README.md                    # This file
├── .env.example
├── infra/                       # AWS SAM / CDK templates
├── backend/
│   ├── agent/                   # Claude agent + tools + prompts
│   ├── voice/                   # STT + TTS
│   ├── handlers/                # Lambda entrypoints
│   └── integrations/            # bunq, AWS, Twilio clients
├── frontend/app/                # Expo React Native app
└── scripts/                     # Seeders + local runners
```

---

## Demo Script (3-minute pitch)

1. **Hook**: "Last year, Dutch consumers lost €80M to bank-helpdesk scams. Most victims called their bank too late."
2. **Scene 1 — active scam**: Live voice call to GuardianAI, screenshot upload, card freeze, emergency contact SMS arrives on stage.
3. **Scene 2 — advice**: "How's my spending?" → Guardian talks through categories, flags a rogue subscription.
4. **Close**: "GuardianAI is an always-on, always-consenting AI advocate for every bunq customer."

---

## Roadmap Beyond the Hackathon

- On-device wake word and offline mode for low-connectivity regions.
- Federated incident intelligence — anonymized scam signals shared across bunq customers.
- Multi-language support (Dutch, German, Spanish, French).
- Voice cloning of trusted family members for high-authority alert calls.
- Plug-in architecture for other European banks via PSD2.

---

## Team & Credits

Built during the bunq hackathon.
LLM: Claude (Anthropic). Cloud: AWS. Banking: bunq.

---

## License

MIT (for the hackathon prototype).
