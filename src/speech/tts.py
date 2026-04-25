"""
tts.py — Text-to-Speech (text → audio bytes).

Supported providers:
  1. Kokoro-82M local inference
  2. OpenAI TTS API
  3. macOS `say` fallback

Usage:
    from src.speech.tts import init_kokoro, speak
    init_kokoro()  # optional warm-up if USE_KOKORO_TTS=true
    audio_bytes = speak("Your balance is €847.32.")
"""

import io
import os
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

from src.config import OPENAI_API_KEY

USE_KOKORO = os.environ.get("USE_KOKORO_TTS", "false").lower() in ("true", "1", "yes")
_USE_MACOS = os.environ.get("USE_MACOS_TTS", "false").lower() in ("true", "1")
_TTS_VOICE = os.environ.get("TTS_VOICE", "alloy")  # alloy/echo/fable/onyx/nova/shimmer
_TTS_SPEED = float(os.environ.get("TTS_SPEED", "1.0"))
_KOKORO_LANG_CODE = os.environ.get("KOKORO_LANG_CODE", "a").strip() or "a"
_KOKORO_REPO_ID = os.environ.get("KOKORO_REPO_ID", "hexgrad/Kokoro-82M").strip() or "hexgrad/Kokoro-82M"
_KOKORO_VOICE = os.environ.get("KOKORO_VOICE", "af_heart").strip() or "af_heart"
_KOKORO_SPEED = float(os.environ.get("KOKORO_SPEED", "1.0"))
_KOKORO_DEVICE = os.environ.get("KOKORO_DEVICE", "").strip() or None
_KOKORO_SAMPLE_RATE = 24000


def _resolve_kokoro_device(value: str | None) -> str | None:
    """Translate KOKORO_DEVICE to a torch-valid device string.

    'auto' / 'gpu' / '' → cuda if available, else mps on Apple Silicon, else cpu.
    Explicit 'cpu' / 'cuda' / 'mps' pass through unchanged.
    Returns None to let Kokoro pick its own default if torch import fails.
    """
    val = (value or "").lower()
    if val in ("", "auto", "gpu"):
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            mps = getattr(torch.backends, "mps", None)
            if mps and mps.is_available():
                return "mps"
            return "cpu"
        except Exception:
            return None
    return val


def _has_usable_openai_key() -> bool:
    key = (OPENAI_API_KEY or "").strip()
    return key.startswith("sk-") and key not in {"sk-", "sk-..", "sk-..."} and len(key) > 20


def _should_use_kokoro_tts() -> bool:
    return USE_KOKORO


def _should_use_macos_tts() -> bool:
    return _USE_MACOS or (
        sys.platform == "darwin"
        and not _should_use_kokoro_tts()
        and not _has_usable_openai_key()
    )


def audio_mime_type() -> str:
    return "audio/wav" if (_should_use_kokoro_tts() or _should_use_macos_tts()) else "audio/mpeg"


def init_kokoro(force_reload: bool = False):
    """
    Initialize and cache a local Kokoro pipeline.

    Raises:
        ImportError: If Kokoro dependencies are not installed.
        RuntimeError: If Kokoro fails to initialize.
    """
    if not force_reload and hasattr(init_kokoro, "_pipeline"):
        return init_kokoro._pipeline

    try:
        from kokoro import KPipeline
    except ImportError as exc:
        raise ImportError(
            "Kokoro TTS is not installed. Run: pip install -e '.[kokoro]'"
        ) from exc

    try:
        pipeline = KPipeline(
            lang_code=_KOKORO_LANG_CODE,
            repo_id=_KOKORO_REPO_ID,
            device=_resolve_kokoro_device(_KOKORO_DEVICE),
        )
    except Exception as exc:
        raise RuntimeError(
            f"Failed to initialize Kokoro pipeline: {exc}. "
            "On first run Kokoro downloads model files from Hugging Face."
        ) from exc

    init_kokoro._pipeline = pipeline
    return pipeline


def _float_audio_to_wav_bytes(audio: np.ndarray, sample_rate: int) -> bytes:
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)
    audio = np.clip(audio, -1.0, 1.0)
    pcm = (audio * 32767.0).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())
    return buf.getvalue()

# Urgent/alarmed mode: a graver voice + slightly slower pace reads as
# "this is serious, pay attention" without actually changing the model.
_TTS_URGENT_VOICE = os.environ.get("TTS_URGENT_VOICE", "onyx")
_TTS_URGENT_SPEED = float(os.environ.get("TTS_URGENT_SPEED", "0.92"))


def speak(text: str, *, urgent: bool = False) -> bytes:
    """
    Convert text to speech and return raw audio bytes.

    Args:
        text:   The text to speak. Kept under 4096 chars by OpenAI limits.
        urgent: When True, use the grave voice + slower speed for fraud alerts.

    Returns:
        WAV bytes for local providers, MP3 bytes for OpenAI.
    """
    text = text[:4096]  # hard limit for OpenAI TTS
    if _should_use_kokoro_tts():
        return _speak_kokoro(text)
    if _should_use_macos_tts():
        return _speak_macos(text)
    if not _has_usable_openai_key():
        raise RuntimeError("OPENAI_API_KEY is missing or invalid, and macOS TTS is unavailable.")
    return _speak_openai(text, urgent=urgent)


def _speak_kokoro(text: str) -> bytes:
    pipeline = init_kokoro()
    chunks: list[np.ndarray] = []
    silence = np.zeros(int(_KOKORO_SAMPLE_RATE * 0.04), dtype=np.float32)

    for result in pipeline(
        text,
        voice=_KOKORO_VOICE,
        speed=_KOKORO_SPEED,
        # Split per sentence so Kokoro pipelines the workload — slightly faster
        # in total than one giant pass, and leaves the door open for streaming
        # each chunk to the client (Phase 3) without re-touching this loop.
        split_pattern=r"(?<=[.!?])\s+",
    ):
        audio = result.audio if hasattr(result, "audio") else result[2]
        if audio is None:
            continue
        if hasattr(audio, "detach"):
            audio = audio.detach().cpu().numpy()
        chunk = np.asarray(audio, dtype=np.float32).reshape(-1)
        if chunk.size == 0:
            continue
        if chunks:
            chunks.append(silence)
        chunks.append(chunk)

    if not chunks:
        raise RuntimeError("Kokoro did not generate any audio.")

    return _float_audio_to_wav_bytes(np.concatenate(chunks), _KOKORO_SAMPLE_RATE)


def _speak_openai(text: str, *, urgent: bool = False) -> bytes:
    """Option A: OpenAI TTS API — requires OPENAI_API_KEY."""
    import openai

    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    voice = _TTS_URGENT_VOICE if urgent else _TTS_VOICE
    speed = _TTS_URGENT_SPEED if urgent else _TTS_SPEED
    response = client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
        speed=speed,
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
