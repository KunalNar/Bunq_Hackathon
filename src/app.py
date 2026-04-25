"""
app.py — FastAPI server tying together agent, speech, and vision.

Endpoints:
  GET  /           → serves web/index.html
  GET  /state      → current balance + last 5 transactions (UI polls this)
  POST /chat       → text message → agent response
  POST /voice      → audio upload → transcribe → agent → TTS response
  POST /receipt    → image upload → parse → optional agent categorise/split
  POST /reset      → clear conversation history (for demo reset)
  WS   /ws         → streaming agent responses (stretch goal)

Run with:
  uvicorn src.app:app --reload --port 8000

All endpoints accept ?mock=true/false to override the MOCK_MODE env var.
"""

import base64
import json
import logging
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.agent.handlers import execute_tool
from src.agent.loop import run_agent
from src.config import MOCK_MODE, validate

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger("app")

# Validate config at startup (will raise on missing keys)
validate()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-load heavy local models so the first user turn doesn't pay a cold start.

    - Kokoro TTS: loads the pipeline + runs a one-shot warm synthesis.
    - faster-whisper ASR: loads the model + runs a tiny dummy decode.
    Both are best-effort: if either fails, the server still starts and the
    relevant endpoint will surface the error per-request.
    """
    if os.environ.get("USE_KOKORO_TTS", "false").lower() in ("true", "1", "yes"):
        try:
            from src.speech.tts import init_kokoro, speak
            init_kokoro()
            speak("ready")  # warm synthesis path on this device
            logger.info("[startup] Kokoro warmed up")
        except Exception:
            logger.exception("[startup] Kokoro init failed; TTS will retry per-request")

    if os.environ.get("USE_LOCAL_WHISPER", "false").lower() in ("true", "1", "yes"):
        try:
            import wave, struct
            from src.speech.asr import transcribe
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp = f.name
            with wave.open(tmp, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
                w.writeframes(struct.pack("<" + "h" * 8000, *([0] * 8000)))  # 0.5s silence
            transcribe(tmp)
            os.unlink(tmp)
            logger.info("[startup] Whisper warmed up")
        except Exception:
            logger.exception("[startup] Whisper warmup failed; will load on first /voice")

    yield


app = FastAPI(title="bunq Hackathon Assistant", version="0.1.0", lifespan=lifespan)

# ── Conversation history (in-memory, one global session for the demo) ──────────
# In production you'd scope this per user/session.
_conversation: list[dict] = []

WEB_DIR = Path(__file__).parent.parent / "web"
DIST_DIR = WEB_DIR / "dist"

# Serve React build assets if the dist folder exists
if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _mock_flag(mock: Optional[str]) -> bool:
    """Parse the ?mock= query param, falling back to MOCK_MODE env var."""
    if mock is None:
        return MOCK_MODE
    return mock.lower() in ("true", "1", "yes")


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the React build if available, otherwise the legacy single-file UI."""
    dist_index = DIST_DIR / "index.html"
    if dist_index.exists():
        return HTMLResponse(dist_index.read_text())
    index = WEB_DIR / "index.html"
    if not index.exists():
        return HTMLResponse("<h1>UI not found. Run from project root.</h1>", status_code=404)
    return HTMLResponse(index.read_text())


@app.get("/avatar.png")
async def serve_avatar():
    """Serve the avatar image for the React app."""
    from fastapi.responses import FileResponse
    avatar = Path(__file__).parent.parent / "public" / "assets" / "avatar.png"
    if avatar.exists():
        return FileResponse(str(avatar))
    return HTMLResponse("not found", status_code=404)


@app.get("/state")
async def get_state(mock: Optional[str] = Query(None)):
    """
    Returns current account balance and last 5 transactions.
    The UI polls this every 5 seconds to keep the panel live.
    """
    is_mock = _mock_flag(mock)
    balance = execute_tool("get_balance", {}, mock_mode=is_mock)
    txns = execute_tool("list_transactions", {"limit": 5}, mock_mode=is_mock)
    return {
        "mock_mode": is_mock,
        "account": balance,
        "recent_transactions": txns["transactions"],
    }


class ChatRequest(BaseModel):
    message: str


@app.post("/chat")
async def chat(req: ChatRequest, mock: Optional[str] = Query(None)):
    """
    Accept a text message, run the agent, return the response and tool calls.
    The conversation history is maintained in-memory across calls.
    """
    global _conversation
    is_mock = _mock_flag(mock)
    logger.info(f"[chat] user: {req.message!r} (mock={is_mock})")

    _conversation.append({"role": "user", "content": req.message})
    final_text, new_messages, usage = run_agent(
        _conversation,
        mock_mode=is_mock,
    )
    _conversation.extend(new_messages)

    # Extract tool calls from new_messages for the UI to display
    tool_calls = []
    for msg in new_messages:
        if msg["role"] == "assistant" and isinstance(msg["content"], list):
            for block in msg["content"]:
                if hasattr(block, "type") and block.type == "tool_use":
                    tool_calls.append({"name": block.name, "args": block.input})

    logger.info(f"[chat] response: {final_text[:100]!r}  tools_used={len(tool_calls)}")
    return {
        "response": final_text,
        "tool_calls": tool_calls,
        "usage": usage,
        "mock_mode": is_mock,
    }


@app.post("/voice")
async def voice(
    audio: UploadFile = File(...),
    mock: Optional[str] = Query(None),
):
    """
    Accept an audio upload, transcribe with Whisper, run the agent,
    and return the response text + base64-encoded TTS audio.
    """
    from src.speech.asr import transcribe
    from src.speech.tts import audio_mime_type, speak

    is_mock = _mock_flag(mock)
    tmp_path = None

    try:
        # Save upload to temp file for Whisper
        suffix = Path(audio.filename or "audio.wav").suffix or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(await audio.read())
            tmp_path = tmp.name

        transcript = transcribe(tmp_path).strip()
        logger.info(f"[voice] transcript: {transcript!r}")
        if not transcript:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "No speech detected. Try speaking closer to the mic or for a bit longer.",
                    "mock_mode": is_mock,
                },
            )

        # Run agent with the transcript
        global _conversation
        _conversation.append({"role": "user", "content": transcript})
        final_text, new_messages, usage = run_agent(
            _conversation,
            mock_mode=is_mock,
        )
        _conversation.extend(new_messages)

        # Convert response to speech
        audio_bytes = speak(final_text)
        audio_b64 = base64.b64encode(audio_bytes).decode()

        return {
            "transcript": transcript,
            "response": final_text,
            "audio_b64": audio_b64,
            "audio_mime": audio_mime_type(),
            "mock_mode": is_mock,
            "usage": usage,
        }
    except Exception as exc:
        logger.exception("[voice] processing failed")
        return JSONResponse(
            status_code=500,
            content={
                "error": f"Voice processing failed: {exc}",
                "mock_mode": is_mock,
            },
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/receipt")
async def receipt(
    image: UploadFile = File(...),
    num_people: int = Form(1),
    mock: Optional[str] = Query(None),
    run_agent_flag: bool = Form(False),
):
    """
    Accept a receipt image, parse it with Claude vision, and optionally
    run the agent to categorise the expense or split the bill.
    """
    is_mock = _mock_flag(mock)
    img_bytes = await image.read()
    img_b64 = base64.b64encode(img_bytes).decode()
    media_type = image.content_type or "image/jpeg"

    # Always run vision on the real uploaded image — mocking vision would make
    # the UI feel broken (user uploads X, gets back Y). mock_mode below still
    # governs the downstream banking actions (split, request, categorize).
    from src.vision.receipt_parser import parse_receipt_image
    receipt_data = parse_receipt_image(image_base64=img_b64, media_type=media_type)
    parsed = receipt_data.model_dump()

    result = {"parsed_receipt": parsed, "mock_mode": is_mock}

    if run_agent_flag and parsed.get("total"):
        from src.agent.prompts import build_receipt_split_prompt
        prompt = build_receipt_split_prompt(parsed, num_people)
        global _conversation
        _conversation.append({"role": "user", "content": prompt})
        final_text, new_messages, usage = run_agent(
            _conversation,
            mock_mode=is_mock,
        )
        _conversation.extend(new_messages)
        result["agent_response"] = final_text
        result["usage"] = usage

    return result


@app.post("/analyze-message")
async def analyze_message(
    image: UploadFile = File(...),
    mock: Optional[str] = Query(None),
):
    """
    Run the fraud-detection pipeline on a screenshot of a suspicious message.

    Steps:
      1. Claude Vision extracts sender / text / URLs / red flags / verdict.
      2. If the verdict is alarming, the agent is invoked with a prompt that
         includes the analysis + Anthropic's web_search tool for brand
         verification; it returns a short spoken warning.
      3. The warning is TTS'd in "urgent" mode (graver voice, slightly slower).

    The `is_scam` flag in the response tells the UI to flip into red-alert mode.
    """
    from src.agent.prompts import build_fraud_analysis_prompt
    from src.agent.tools import WEB_SEARCH_TOOL
    from src.speech.tts import speak
    from src.vision.fraud_analyzer import analyze_suspicious_message

    is_mock = _mock_flag(mock)
    img_bytes = await image.read()
    img_b64 = base64.b64encode(img_bytes).decode()
    media_type = image.content_type or "image/jpeg"

    analysis = analyze_suspicious_message(image_base64=img_b64, media_type=media_type)
    logger.info(
        f"[analyze-message] verdict={analysis.verdict} "
        f"confidence={analysis.confidence:.2f} flags={analysis.red_flags}"
    )

    agent_text = ""
    audio_b64 = ""
    usage = {}
    if analysis.is_alarming:
        global _conversation
        prompt = build_fraud_analysis_prompt(analysis.model_dump())
        _conversation.append({"role": "user", "content": prompt})
        agent_text, new_messages, usage = run_agent(
            _conversation,
            mock_mode=is_mock,
            extra_tools=[WEB_SEARCH_TOOL],
        )
        _conversation.extend(new_messages)
        try:
            audio_bytes = speak(agent_text, urgent=True)
            audio_b64 = base64.b64encode(audio_bytes).decode()
        except Exception as exc:
            logger.warning(f"[analyze-message] TTS failed: {exc}")

    return {
        "is_scam": analysis.is_alarming,
        "analysis": analysis.model_dump(),
        "agent_response": agent_text,
        "audio_b64": audio_b64,
        "usage": usage,
        "mock_mode": is_mock,
    }


@app.post("/reset")
async def reset():
    """Clear the conversation history. Call before each demo run."""
    global _conversation
    _conversation = []
    logger.info("[reset] Conversation history cleared.")
    return {"status": "ok", "message": "Conversation reset. Ready for demo."}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for streaming agent responses (stretch goal).
    Currently echoes messages back; replace with streaming Claude calls
    if you have time during the hackathon.
    """
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            user_text = msg.get("message", "")
            # For now, fall back to synchronous chat
            global _conversation
            _conversation.append({"role": "user", "content": user_text})
            final_text, new_messages, _usage = run_agent(_conversation)
            _conversation.extend(new_messages)
            await websocket.send_json({"response": final_text})
    except WebSocketDisconnect:
        logger.info("[ws] Client disconnected")
