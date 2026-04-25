#!/bin/bash
# run.sh — One command to start the bunq AI assistant demo.
#
# Usage:
#   ./run.sh            # start in mock mode (safe, no sandbox needed)
#   ./run.sh --live     # start against real bunq sandbox
#   ./run.sh --seed     # re-seed sandbox then start
#   ./run.sh --test     # run eval harness then exit
#
# Requirements: Python 3.11+, pip

set -e

VENV_DIR="$(dirname "$0")/bunq_hackathon"
PORT=${PORT:-8000}
SEED=false
LIVE=false
RUN_TESTS=false

# ── Parse args ────────────────────────────────────────────────────────────────
for arg in "$@"; do
  case "$arg" in
    --seed) SEED=true ;;
    --live) LIVE=true ;;
    --test) RUN_TESTS=true ;;
    *) echo "Unknown flag: $arg" && exit 1 ;;
  esac
done

# ── Env check ─────────────────────────────────────────────────────────────────
if [ ! -f .env ]; then
  echo "⚠  No .env found. Copying .env.example → .env"
  cp .env.example .env
  echo "   Edit .env and add your API keys, then re-run."
  exit 1
fi

# Check ANTHROPIC_API_KEY is set
if ! grep -q "ANTHROPIC_API_KEY=sk-" .env 2>/dev/null; then
  echo "⚠  ANTHROPIC_API_KEY not set in .env. Please add it."
  exit 1
fi

# ── Virtual environment ────────────────────────────────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment at $VENV_DIR…"
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

# ── Install deps ───────────────────────────────────────────────────────────────
echo "Installing dependencies…"
INSTALL_EXTRAS=()
if grep -qi '^USE_LOCAL_WHISPER=true' .env 2>/dev/null; then
  INSTALL_EXTRAS+=("offline")
fi
if grep -qi '^USE_KOKORO_TTS=true' .env 2>/dev/null; then
  INSTALL_EXTRAS+=("kokoro")
fi

if [ ${#INSTALL_EXTRAS[@]} -gt 0 ]; then
  EXTRAS_CSV=$(IFS=,; echo "${INSTALL_EXTRAS[*]}")
  pip install -e ".[${EXTRAS_CSV}]" -q
else
  pip install -e . -q
fi

# ── Seed ──────────────────────────────────────────────────────────────────────
if [ "$SEED" = true ]; then
  echo ""
  echo "Seeding bunq sandbox…"
  python scripts/seed_sandbox.py
fi

# ── Tests ─────────────────────────────────────────────────────────────────────
if [ "$RUN_TESTS" = true ]; then
  echo ""
  echo "Running eval harness…"
  python tests/test_agent.py
  exit $?
fi

# ── Set mode ──────────────────────────────────────────────────────────────────
if [ "$LIVE" = true ]; then
  export MOCK_MODE=false
  echo ""
  echo "🔴 LIVE MODE — connecting to bunq sandbox"
else
  export MOCK_MODE=true
  echo ""
  echo "🟡 MOCK MODE — using fixture data (safe for demo)"
fi

# ── Build React UI ────────────────────────────────────────────────────────────
if [ -d "client" ] && command -v npm &>/dev/null; then
  echo "Building React UI…"
  (cd client && npm install -q && npm run build 2>&1 | tail -3)
fi

# ── Start server ──────────────────────────────────────────────────────────────
echo ""
echo "Starting Finn on http://localhost:$PORT"
echo "Press Ctrl+C to stop."
echo ""

uvicorn src.app:app --host 0.0.0.0 --port "$PORT" --reload
