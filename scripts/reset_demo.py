"""
reset_demo.py — Full demo reset: clears state, re-seeds sandbox, restarts server.

Should complete in under 30 seconds. Use this mid-demo if things go wrong.

Usage:
    python scripts/reset_demo.py [--skip-seed]

    --skip-seed  Skip the sandbox re-seed (useful if sandbox is already set up)
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def kill_server(port: int = 8000) -> None:
    """Kill any process listening on the given port."""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f"tcp:{port}"], capture_output=True, text=True
        )
        pids = result.stdout.strip().split()
        for pid in pids:
            if pid:
                os.kill(int(pid), signal.SIGTERM)
                print(f"  Killed PID {pid} on port {port}")
        if pids:
            time.sleep(1)
    except Exception as e:
        print(f"  ⚠  Could not kill server: {e}")


def clear_conversation() -> None:
    """Delete conversation history file if it exists (for future persistent history)."""
    history_file = Path(__file__).parent.parent / "conversation_history.json"
    if history_file.exists():
        history_file.unlink()
        print("  Cleared conversation history")
    # Also clear the in-memory state by hitting /reset endpoint if server is up
    try:
        import httpx
        httpx.post("http://localhost:8000/reset", timeout=2)
        print("  Reset API called")
    except Exception:
        pass  # server isn't running yet, that's fine


def clear_audit_log() -> None:
    """Remove the audit log for a clean demo."""
    log_file = Path(__file__).parent.parent / "audit_log.jsonl"
    if log_file.exists():
        log_file.unlink()
        print("  Cleared audit log")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset demo state")
    parser.add_argument("--skip-seed", action="store_true", help="Skip sandbox re-seed")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    print("=== Demo Reset ===\n")
    print("1. Stopping server…")
    kill_server(args.port)

    print("2. Clearing state…")
    clear_conversation()
    clear_audit_log()

    if not args.skip_seed:
        print("3. Re-seeding sandbox…")
        result = subprocess.run(
            [sys.executable, "scripts/seed_sandbox.py"],
            cwd=Path(__file__).parent.parent,
        )
        if result.returncode != 0:
            print("  ⚠  Seed failed. Continuing with existing sandbox state.")

    print("4. Starting server…")
    subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.app:app", "--port", str(args.port)],
        cwd=Path(__file__).parent.parent,
    )
    time.sleep(2)

    print(f"\n✅ Reset complete! Demo ready at http://localhost:{args.port}")


if __name__ == "__main__":
    main()
