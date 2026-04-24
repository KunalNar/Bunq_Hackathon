"""
receipt_parser.py — Receipt image → structured JSON via Claude vision.

Takes a receipt image (file path or base64 string), sends it to Claude with
a strict extraction prompt, and returns a Pydantic-validated dict. Retries
up to 2 times if JSON parsing or validation fails (model occasionally wraps
output in markdown fences).

Architecture note: This module is called by the parse_receipt tool handler
in handlers.py. It is intentionally decoupled from the agent loop so it can
also be tested or called independently (e.g. from a script or batch job).

Usage:
    from src.vision.receipt_parser import parse_receipt_image
    result = parse_receipt_image(path="fixtures/receipts/ah_receipt.jpg")
    print(result.merchant, result.total)
"""

import base64
import json
import re
from pathlib import Path
from typing import Optional

import anthropic
from pydantic import BaseModel, field_validator

from src.config import ANTHROPIC_API_KEY, SMART_MODEL

# Use temperature=0 for deterministic extraction
_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

EXTRACTION_PROMPT = """Extract the following from this receipt image as a JSON object.
Keys required:
  merchant   - string: store or restaurant name
  total      - number or null: final total amount paid (including tax/tip)
  currency   - string: ISO currency code, default "EUR"
  date       - string or null: date in YYYY-MM-DD format
  line_items - array of {name: string, price: number, qty: number}
  category_guess - string: one of food, transport, entertainment, utilities, other

Rules:
- If a field is unreadable, use null.
- Do NOT guess amounts — if the total is unclear, set it to null.
- Return ONLY the raw JSON object. No markdown. No explanation."""


class LineItem(BaseModel):
    name: str
    price: Optional[float] = None
    qty: float = 1.0


class ReceiptData(BaseModel):
    merchant: Optional[str] = None
    total: Optional[float] = None
    currency: str = "EUR"
    date: Optional[str] = None
    line_items: list[LineItem] = []
    category_guess: str = "other"

    @field_validator("category_guess")
    @classmethod
    def validate_category(cls, v: str) -> str:
        valid = {"food", "transport", "entertainment", "utilities", "other"}
        return v if v in valid else "other"


def _image_to_base64(path: str | Path) -> str:
    """Read an image file and return base64-encoded bytes."""
    return base64.b64encode(Path(path).read_bytes()).decode()


def _strip_markdown(text: str) -> str:
    """Remove ```json ... ``` fences that the model sometimes adds."""
    return re.sub(r"```(?:json)?\s*([\s\S]*?)```", r"\1", text).strip()


def parse_receipt_image(
    *,
    path: str | Path | None = None,
    image_base64: str | None = None,
    media_type: str = "image/jpeg",
    max_retries: int = 2,
) -> ReceiptData:
    """
    Extract structured data from a receipt image.

    Provide exactly one of `path` or `image_base64`.

    Args:
        path:         File path to a JPEG/PNG receipt image.
        image_base64: Already-encoded base64 string.
        media_type:   MIME type of the image (default 'image/jpeg').
        max_retries:  How many times to retry on parse failure.

    Returns:
        ReceiptData pydantic model with extracted fields.

    Raises:
        ValueError if both or neither of path/image_base64 are provided.
        RuntimeError if all retries fail.
    """
    if path is None and image_base64 is None:
        raise ValueError("Provide either path or image_base64.")
    if path is not None and image_base64 is not None:
        raise ValueError("Provide only one of path or image_base64.")

    b64 = image_base64 if image_base64 else _image_to_base64(path)

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
                        {"type": "text", "text": EXTRACTION_PROMPT},
                    ],
                }
            ],
        )
        raw = response.content[0].text
        try:
            cleaned = _strip_markdown(raw)
            data = json.loads(cleaned)
            return ReceiptData(**data)
        except Exception as exc:
            last_error = exc
            if attempt < max_retries:
                continue

    raise RuntimeError(
        f"Receipt parsing failed after {max_retries + 1} attempts. "
        f"Last error: {last_error}"
    )
