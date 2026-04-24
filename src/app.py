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
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from src.agent.handlers import execute_tool
from src.agent.loop import run_agent
from src.config import MOCK_MODE, validate

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger("app")

# Validate config at startup (will raise on missing keys)
validate()

app = FastAPI(title="bunq Hackathon Assistant", version="0.1.0")

# ── Conversation history (in-memory, one global session for the demo) ──────────
# In production you'd scope this per user/session.
_conversation: list[dict] = []

WEB_DIR = Path(__file__).parent.parent / "web"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _mock_flag(mock: Optional[str]) -> bool:
    """Parse the ?mock= query param, falling back to MOCK_MODE env var."""
    if mock is None:
        return MOCK_MODE
    return mock.lower() in ("true", "1", "yes")


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the single-file demo UI."""
    index = WEB_DIR / "index.html"
    if not index.exists():
        return HTMLResponse("<h1>UI not found. Run from project root.</h1>", status_code=404)
    return HTMLResponse(index.read_text())


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

    if is_mock:
        # Use mock handler (returns canned receipt data)
        parsed = execute_tool("parse_receipt", {"image_base64": img_b64}, mock_mode=True)
    else:
        # Real vision call
        from src.vision.receipt_parser import parse_receipt_image
        receipt_data = parse_receipt_image(image_base64=img_b64)
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
