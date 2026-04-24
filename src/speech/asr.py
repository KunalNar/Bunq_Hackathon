"""
asr.py — Automatic Speech Recognition (speech → text).

Default: OpenAI Whisper API (Option A) — simple, high quality, needs internet.

Offline fallback: set USE_LOCAL_WHISPER=true in .env and install faster-whisper.
  pip install faster-whisper
  # Downloads ~1GB model on first use.

Supported audio formats: wav, mp3, m4a, webm (anything Whisper accepts).

Usage:
    from src.speech.asr import transcribe
    text = transcribe("recording.wav")
"""

import os
from pathlib import Path

from src.config import OPENAI_API_KEY

_USE_LOCAL = os.environ.get("USE_LOCAL_WHISPER", "false").lower() in ("true", "1")
_LOCAL_MODEL_SIZE = os.environ.get("WHISPER_MODEL", "base")  # tiny/base/small/medium


def _has_usable_openai_key() -> bool:
    key = (OPENAI_API_KEY or "").strip()
    return key.startswith("sk-") and key not in {"sk-", "sk-..", "sk-..."} and len(key) > 20


def transcribe(audio_path: str | Path) -> str:
    """
    Transcribe an audio file to text.

    Args:
        audio_path: Path to an audio file (wav, mp3, m4a, webm).

    Returns:
        Transcribed text as a string. Returns "" on failure.
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    if _USE_LOCAL or not _has_usable_openai_key():
        return _transcribe_local(audio_path)
    return _transcribe_openai(audio_path)


def _transcribe_openai(audio_path: Path) -> str:
    """Option A: OpenAI Whisper API — requires OPENAI_API_KEY."""
    import openai

    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="text",
        )
    # response is a plain string in text mode
    return response.strip() if isinstance(response, str) else response.text.strip()


def _transcribe_local(audio_path: Path) -> str:
    """Option B: Local faster-whisper — offline, no API key needed."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ImportError(
            "faster-whisper not installed. Run: pip install faster-whisper\n"
            "Or set USE_LOCAL_WHISPER=false to use OpenAI API instead."
        )

    if not hasattr(_transcribe_local, "_model"):
        print(f"[asr] Loading local Whisper model '{_LOCAL_MODEL_SIZE}' (first run may take a minute)...")
        _transcribe_local._model = WhisperModel(_LOCAL_MODEL_SIZE, device="cpu")

    model = _transcribe_local._model
    segments, _info = model.transcribe(str(audio_path), beam_size=5)
    return " ".join(seg.text.strip() for seg in segments)
