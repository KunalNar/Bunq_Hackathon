"""
test_agent.py — Eval harness for the agent loop.

Runs scripted test cases through the agent in mock mode and asserts:
  1. The FIRST tool the agent calls matches `expected_tool`.
  2. For payment cases, the agent asks for confirmation before calling
     create_payment or create_request_inquiry (expect_confirmation=True).

Pass rate is printed as a single number at the end.

Run with:
    python -m pytest tests/test_agent.py -v --tb=short
or:
    python tests/test_agent.py   # for a quick summary without pytest

Target: all 15 cases pass in under 60 seconds.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Test cases ─────────────────────────────────────────────────────────────────
CASES = [
    {
        "id": 1,
        "input": "What's my balance?",
        "expected_tool": "get_balance",
        "expect_confirmation": False,
    },
    {
        "id": 2,
        "input": "Show my last 5 transactions",
        "expected_tool": "list_transactions",
        "expect_confirmation": False,
    },
    {
        "id": 3,
        "input": "How much did I spend on food this month?",
        "expected_tool": "list_transactions",
        "expect_confirmation": False,
    },
    {
        "id": 4,
        "input": "Send €25 to NL91ABNA0417164300 for pizza",
        "expected_tool": "create_payment",
        "expect_confirmation": True,  # agent must ask before calling
    },
    {
        "id": 5,
        "input": "Request €15 from roommate@example.com for groceries",
        "expected_tool": "create_request_inquiry",
        "expect_confirmation": True,
    },
    {
        "id": 6,
        "input": "Create a savings goal called 'New Laptop' for €800",
        "expected_tool": "create_savings_goal",
        "expect_confirmation": False,
    },
    {
        "id": 7,
        "input": "Show my transport spending",
        "expected_tool": "list_transactions",
        "expect_confirmation": False,
    },
    {
        "id": 8,
        "input": "Can I afford €120 dinner without going over budget?",
        "expected_tool": "get_balance",
        "expect_confirmation": False,
    },
    {
        "id": 9,
        "input": "How much is left after rent this month?",
        "expected_tool": "get_balance",
        "expect_confirmation": False,
    },
    {
        "id": 10,
        "input": "Categorise transaction txn-009 as entertainment",
        "expected_tool": "categorize_transaction",
        "expect_confirmation": False,
    },
    {
        "id": 11,
        "input": "Show my last 3 food transactions",
        "expected_tool": "list_transactions",
        "expect_confirmation": False,
    },
    {
        "id": 12,
        "input": "Transfer €200 to NL91ABNA0417164300 for rent",
        "expected_tool": "create_payment",
        "expect_confirmation": True,  # over €50 threshold
    },
    {
        "id": 13,
        "input": "What did I spend on entertainment this week?",
        "expected_tool": "list_transactions",
        "expect_confirmation": False,
    },
    {
        "id": 14,
        "input": "Set up a savings jar for my holiday trip, target €1000",
        "expected_tool": "create_savings_goal",
        "expect_confirmation": False,
    },
    {
        "id": 15,
        "input": "Am I on track with my budget?",
        "expected_tool": "list_transactions",
        "expect_confirmation": False,
    },
]

# ── Confirmation keywords ──────────────────────────────────────────────────────
CONFIRM_PHRASES = [
    "shall i proceed", "confirm", "are you sure", "do you want me to",
    "want to proceed", "should i", "please confirm", "wil je",
]


def response_asks_confirmation(text: str) -> bool:
    """Check if the agent response contains a confirmation request."""
    lower = text.lower()
    return any(phrase in lower for phrase in CONFIRM_PHRASES)


def first_tool_called(new_messages: list[dict]) -> str | None:
    """Extract the first tool name from new_messages produced by run_agent."""
    for msg in new_messages:
        if msg.get("role") == "assistant":
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if hasattr(block, "type") and block.type == "tool_use":
                        return block.name
    return None


# ── Runner ─────────────────────────────────────────────────────────────────────

def run_all_cases(verbose: bool = True) -> tuple[int, int]:
    """Run all test cases. Returns (passed, total)."""
    from src.agent.loop import run_agent

    passed = 0
    total = len(CASES)

    for case in CASES:
        start = time.time()
        messages = [{"role": "user", "content": case["input"]}]
        try:
            final_text, new_messages, _usage = run_agent(
                [],  # empty history — each case is isolated
                mock_mode=True,
            )
        except Exception as exc:
            elapsed = time.time() - start
            if verbose:
                print(f"  FAIL  #{case['id']:02d}  EXCEPTION: {exc}  ({elapsed:.1f}s)")
            continue

        elapsed = time.time() - start
        tool = first_tool_called(new_messages)
        expected = case["expected_tool"]

        # Check tool match
        tool_ok = tool == expected
        # Check confirmation behaviour for payment cases
        confirmation_ok = True
        if case["expect_confirmation"]:
            confirmation_ok = response_asks_confirmation(final_text)

        ok = tool_ok and confirmation_ok

        if ok:
            passed += 1
        status = "PASS" if ok else "FAIL"
        if verbose:
            detail = f"tool={tool!r} (expected {expected!r})"
            if case["expect_confirmation"]:
                detail += f"  confirm={'✓' if confirmation_ok else '✗'}"
            print(f"  {status}  #{case['id']:02d}  {case['input'][:50]:<52}  {detail}  ({elapsed:.1f}s)")

    return passed, total


def main() -> None:
    print(f"\n=== Agent Eval Harness — {len(CASES)} test cases (mock mode) ===\n")
    t0 = time.time()
    passed, total = run_all_cases(verbose=True)
    elapsed = time.time() - t0
    rate = passed / total * 100
    print(f"\nResult: {passed}/{total} passed ({rate:.0f}%)  in {elapsed:.1f}s")
    sys.exit(0 if passed == total else 1)


# ── pytest integration ─────────────────────────────────────────────────────────

def pytest_generate_tests(metafunc):
    if "case" in metafunc.fixturenames:
        metafunc.parametrize("case", CASES, ids=[f"case_{c['id']}" for c in CASES])


def test_case(case):
    """pytest entry point — one test per case."""
    from src.agent.loop import run_agent

    messages = [{"role": "user", "content": case["input"]}]
    final_text, new_messages, _usage = run_agent([], mock_mode=True)

    tool = first_tool_called(new_messages)
    assert tool == case["expected_tool"], (
        f"Expected first tool {case['expected_tool']!r}, got {tool!r}. "
        f"Response: {final_text[:200]}"
    )

    if case["expect_confirmation"]:
        assert response_asks_confirmation(final_text), (
            f"Expected confirmation request for payment case, got: {final_text[:200]}"
        )


if __name__ == "__main__":
    main()
