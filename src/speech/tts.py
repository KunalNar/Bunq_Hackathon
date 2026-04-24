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
import tempfile
from pathlib import Path

from src.config import OPENAI_API_KEY

_USE_MACOS = os.environ.get("USE_MACOS_TTS", "false").lower() in ("true", "1")
_TTS_VOICE = os.environ.get("TTS_VOICE", "alloy")  # alloy/echo/fable/onyx/nova/shimmer
_TTS_SPEED = float(os.environ.get("TTS_SPEED", "1.0"))


def speak(text: str) -> bytes:
    """
    Convert text to speech and return raw audio bytes (MP3).

    Args:
        text: The text to speak. Kept under 4096 chars by OpenAI limits.

    Returns:
        MP3 audio bytes that can be written to a file or streamed to a browser.
    """
    text = text[:4096]  # hard limit for OpenAI TTS
    if _USE_MACOS:
        return _speak_macos(text)
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
    Outputs AIFF; we convert to MP3 via afconvert (macOS built-in).
    """
    with tempfile.TemporaryDirectory() as tmp:
        aiff_path = Path(tmp) / "speech.aiff"
        mp3_path = Path(tmp) / "speech.mp3"

        subprocess.run(
            ["say", "-o", str(aiff_path), text],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["afconvert", "-f", "mp4f", "-d", "aac", str(aiff_path), str(mp3_path)],
            check=True,
            capture_output=True,
        )
        return mp3_path.read_bytes()
