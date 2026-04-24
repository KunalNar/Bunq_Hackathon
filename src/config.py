"""
config.py — Central configuration for the bunq hackathon assistant.

Loads environment variables from .env and exposes typed constants used
everywhere else. Import this module first; it calls load_dotenv() at import
time so all other modules can read os.environ safely.

Usage:
    from src.config import ANTHROPIC_API_KEY, MOCK_MODE, SMART_MODEL
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (two levels up from this file: src/ → project/)
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

# ── API keys ───────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
BUNQ_API_KEY: str = os.environ.get("BUNQ_API_KEY", "")

# ── bunq settings ──────────────────────────────────────────────────────────────
BUNQ_ENVIRONMENT: str = os.environ.get("BUNQ_ENVIRONMENT", "SANDBOX")
BUNQ_DEVICE_DESCRIPTION: str = os.environ.get(
    "BUNQ_DEVICE_DESCRIPTION", "bunq-hackathon-demo"
)

# ── Demo behaviour ─────────────────────────────────────────────────────────────
# MOCK_MODE=True → use fixtures/transactions.json (no sandbox needed, demo-safe)
# MOCK_MODE=False → hit real bunq sandbox API
MOCK_MODE: bool = os.environ.get("MOCK_MODE", "true").lower() in ("true", "1", "yes")

PORT: int = int(os.environ.get("PORT", "8000"))

# ── Model selection ────────────────────────────────────────────────────────────
# Use FAST_MODEL for simple lookups / categorisation to keep costs low.
# Use SMART_MODEL for complex reasoning, multi-step planning, and vision.
FAST_MODEL: str = "claude-haiku-4-5"
SMART_MODEL: str = "claude-sonnet-4-6"

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
FIXTURES_DIR = PROJECT_ROOT / "fixtures"
RECEIPTS_DIR = FIXTURES_DIR / "receipts"
TRANSACTIONS_FILE = FIXTURES_DIR / "transactions.json"
SANDBOX_STATE_FILE = PROJECT_ROOT / "sandbox_state.json"

# ── Validation (fail fast at startup) ─────────────────────────────────────────
def validate() -> None:
    """Raise if required keys are missing for the chosen mode."""
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is not set in .env")
    if not MOCK_MODE and not BUNQ_API_KEY:
        raise ValueError("BUNQ_API_KEY is required when MOCK_MODE=false")
