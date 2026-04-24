# 🧠 Hackathon Idea: AI Fraud Prevention Voice Bot

## Concept Overview

An AI-powered interactive voice and visual bot that protects users from fraud in real time — acting as a personal banking guardian that listens, sees, consults, and acts.

---

## Core Features

### 1. AI Voice Interaction
- User can talk to the bot about any problem or suspicious banking activity
- Natural language understanding via **Claude (Anthropic)** as the primary LLM
- Responds in voice and text for accessibility

### 2. Fraud Prevention & Detection
- Detects suspicious behaviour through conversation and screen/device analysis
- Gains access to the user's screen (with consent) to identify scam interfaces, phishing pages, or manipulated UIs
- Real-time risk scoring of transactions and interactions

### 3. User Consultation During Process
- Walks the user through suspicious scenarios step by step
- Explains risks in plain language before any action is taken
- Never acts unilaterally — always keeps the user informed and in control

### 4. Automated Alerts
- Auto-sends alerts to **emergency contacts** if fraud is confirmed or suspected
- Notifies **responsible banking platforms/firms** (e.g., bunq) directly via API
- Supports escalation flows (freeze card, flag account, report incident)

### 5. Multimodal Input
- **Voice**: User speaks to the bot
- **Photo/Vision**: User can share screenshots or point camera at suspicious content
- **Screen access**: Bot can observe device screen to detect threats in context

### 6. Financial Advice Engine
- Analyses user's historical transaction data stored on **AWS**
- Provides personalised financial advice (spending habits, savings tips, anomalies)
- Learns over time from user behaviour patterns

---

## Tech Stack

| Layer | Technology |
|---|---|
| Primary LLM | Claude (Anthropic) |
| Cloud / Data Storage | AWS (user banking data, transaction history) |
| Banking API | bunq API (via hackathon toolkit) |
| Voice | AWS Transcribe / Polly or equivalent |
| Vision / Screen | Claude Vision or AWS Rekognition |
| Alerts | bunq callbacks / webhooks + SMS/email |

---

## bunq API Integration Points

Using the [bunq Hackathon Toolkit](https://github.com/bunq/hackathon_toolkit):

- `06_list_transactions.py` — Pull transaction history for analysis
- `07_setup_callbacks.py` — Real-time payment notifications to trigger fraud alerts
- `03_make_payment.py` / `04_request_money.py` — Monitor and optionally block suspicious payment flows
- bunq sandbox for safe testing throughout development

---

## User Flow

```
User notices suspicious activity
        │
        ▼
Opens bot → speaks or shares screen/photo
        │
        ▼
Claude analyses context (voice + vision + transaction data)
        │
        ▼
Bot consults user → explains risk → asks for confirmation
        │
        ├──→ Fraud confirmed → alerts emergency contacts + bunq
        │
        └──→ False alarm → reassures user + logs event on AWS
```

---

## Why This Wins

- **Real problem**: Fraud and social engineering are the #1 banking threat for everyday users
- **Multimodal AI**: Combines voice, vision, and data — goes beyond chatbots
- **User-first**: Consults rather than acts unilaterally — builds trust
- **bunq native**: Deep API integration for callbacks, transaction monitoring, and alerts
- **Scalable**: AWS backbone means it can grow with real user data
