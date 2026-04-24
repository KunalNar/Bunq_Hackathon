"""
tts.py — Text-to-Speech (text → audio bytes).

Default: OpenAI TTS API (Option A) — good quality, cheap (~€0.015/1k chars).

Offline fallback: set USE_MACOS_TTS=true to use macOS `say` command (free,
offline, sounds robotic but works). No extra install needed on macOS.

Usage:
    from src.speech.tts import speak
    audio_bytes = speak("Your balance is €847.32.")
    # Play with pydub, sounddevice, or return to browser via API.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from src.config import OPENAI_API_KEY

_USE_MACOS = os.environ.get("USE_MACOS_TTS", "false").lower() in ("true", "1")
_TTS_VOICE = os.environ.get("TTS_VOICE", "alloy")  # alloy/echo/fable/onyx/nova/shimmer
_TTS_SPEED = float(os.environ.get("TTS_SPEED", "1.0"))


def _has_usable_openai_key() -> bool:
    key = (OPENAI_API_KEY or "").strip()
    return key.startswith("sk-") and key not in {"sk-", "sk-..", "sk-..."} and len(key) > 20


def _should_use_macos_tts() -> bool:
    return _USE_MACOS or (sys.platform == "darwin" and not _has_usable_openai_key())


def audio_mime_type() -> str:
    return "audio/wav" if _should_use_macos_tts() else "audio/mpeg"


def speak(text: str) -> bytes:
    """
    Convert text to speech and return raw audio bytes (MP3).

    Args:
        text: The text to speak. Kept under 4096 chars by OpenAI limits.

    Returns:
        MP3 audio bytes that can be written to a file or streamed to a browser.
    """
    text = text[:4096]  # hard limit for OpenAI TTS
    if _should_use_macos_tts():
        return _speak_macos(text)
    if not _has_usable_openai_key():
        raise RuntimeError("OPENAI_API_KEY is missing or invalid, and macOS TTS is unavailable.")
    return _speak_openai(text)


def _speak_openai(text: str) -> bytes:
    """Option A: OpenAI TTS API — requires OPENAI_API_KEY."""
    import openai

    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    response = client.audio.speech.create(
        model="tts-1",
        voice=_TTS_VOICE,
        input=text,
        speed=_TTS_SPEED,
    )
    return response.content


def _speak_macos(text: str) -> bytes:
    """
    Option C: macOS `say` command — free, offline, sounds robotic.
    Outputs AIFF; we convert to WAV via afconvert so the browser can play it reliably.
    """
    with tempfile.TemporaryDirectory() as tmp:
        aiff_path = Path(tmp) / "speech.aiff"
        wav_path = Path(tmp) / "speech.wav"

        subprocess.run(
            ["say", "-o", str(aiff_path), text],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["afconvert", str(aiff_path), "-f", "WAVE", "-d", "LEI16", "-o", str(wav_path)],
            check=True,
            capture_output=True,
        )
        return wav_path.read_bytes()
