"""
fraud_analyzer.py — Suspicious-message screenshot → structured fraud verdict via Claude vision.

Extracts sender, message text, URLs, and red flags from a screenshot (SMS, email,
or messaging app) and returns a verdict: scam / suspicious / probably_safe. Mirrors
the receipt_parser pattern: one Claude Vision call, strict JSON schema, retries.

The caller (typically src/app.py:/analyze-message) uses the verdict to decide
whether to escalate to the agent with web_search for brand verification, and
whether to flip the UI into red-alert mode.
"""

import base64
import json
import re
from pathlib import Path
from typing import Literal, Optional

import anthropic
from pydantic import BaseModel

from src.config import ANTHROPIC_API_KEY, SMART_MODEL

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

FRAUD_PROMPT = """You are a fraud-analysis assistant. The user has uploaded a screenshot
of a message (SMS, email, chat) that looked suspicious to them.

Examine the image and return a JSON object with these keys:
  extracted_text  - string: the full visible message body, as-is
  sender          - string or null: phone number, email, or app sender name
  urls            - array of strings: every URL or domain you can see
  red_flags       - array of strings: specific scam indicators you spotted
                    (e.g. "urgency language", "sender domain does not match bunq",
                    "shortened/obfuscated URL", "asks for PIN or OTP", "threatens account closure",
                    "generic greeting", "payment to unknown IBAN")
  verdict         - one of: "scam", "suspicious", "probably_safe"
  confidence      - number 0.0 to 1.0
  reasoning       - one short sentence explaining the verdict

Rules:
- Be conservative toward "scam". If ANY of the red flags above are present, the
  verdict should be at least "suspicious".
- Legitimate bunq never asks for PINs, OTPs, full card numbers, or sends links
  outside of bunq.com / bunq.me. Flag anything that claims to be bunq but uses
  another domain.
- Return ONLY the raw JSON object. No markdown fences. No explanation outside JSON."""


class FraudAnalysis(BaseModel):
    extracted_text: str = ""
    sender: Optional[str] = None
    urls: list[str] = []
    red_flags: list[str] = []
    verdict: Literal["scam", "suspicious", "probably_safe"] = "probably_safe"
    confidence: float = 0.0
    reasoning: str = ""

    @property
    def is_alarming(self) -> bool:
        """True when UI should flip to red-alert and TTS should go urgent."""
        return self.verdict in ("scam", "suspicious")


def _strip_markdown(text: str) -> str:
    return re.sub(r"```(?:json)?\s*([\s\S]*?)```", r"\1", text).strip()


def analyze_suspicious_message(
    *,
    path: str | Path | None = None,
    image_base64: str | None = None,
    media_type: str = "image/jpeg",
    max_retries: int = 2,
) -> FraudAnalysis:
    """
    Analyze a screenshot of a suspected fraudulent message.

    Provide exactly one of `path` or `image_base64`.

    Returns:
        FraudAnalysis with extracted content and a verdict.

    Raises:
        ValueError if inputs are inconsistent.
        RuntimeError if all retries fail to produce valid JSON.
    """
    if path is None and image_base64 is None:
        raise ValueError("Provide either path or image_base64.")
    if path is not None and image_base64 is not None:
        raise ValueError("Provide only one of path or image_base64.")

    b64 = image_base64 if image_base64 else base64.b64encode(Path(path).read_bytes()).decode()

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        response = _client.messages.create(
            model=SMART_MODEL,
            max_tokens=1024,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": FRAUD_PROMPT},
                    ],
                }
            ],
        )
        raw = response.content[0].text
        try:
            data = json.loads(_strip_markdown(raw))
            return FraudAnalysis(**data)
        except Exception as exc:
            last_error = exc
            if attempt < max_retries:
                continue

    raise RuntimeError(
        f"Fraud analysis failed after {max_retries + 1} attempts. Last error: {last_error}"
    )
