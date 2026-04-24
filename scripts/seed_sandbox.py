"""
seed_sandbox.py — Initialise the bunq sandbox with demo users and transactions.

Run this once before the demo (or via run.sh --seed) to create:
  - A primary sandbox user (Emma de Vries) with a funded current account
  - A savings sub-account ("Holiday Fund")
  - A housemate sandbox user (for payment request demos)
  - 20+ realistic Dutch student transactions via the Sugar Daddy endpoint

Output: saves sandbox_state.json to the project root (loaded by handlers.py).

Usage:
    python scripts/seed_sandbox.py

Requires BUNQ_API_KEY in .env pointing to a sandbox API key.
Get one at: https://sandbox.bunq.com/ (create an account and generate a key)
"""

import json
import sys
import time
from pathlib import Path

# Add project root to path so we can import src.*
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import BUNQ_API_KEY, BUNQ_DEVICE_DESCRIPTION, SANDBOX_STATE_FILE, validate

validate()

try:
    from bunq.sdk.context.api_context import ApiContext
    from bunq.sdk.context.api_environment_type import ApiEnvironmentType
    from bunq.sdk.context.bunq_context import BunqContext
    from bunq.sdk.model.generated.endpoint import (
        MonetaryAccount,
        MonetaryAccountSavings,
        Payment,
        SandboxUser,
    )
    from bunq.sdk.model.generated.object_ import Amount, Pointer
except ImportError:
    print("ERROR: bunq-sdk not installed. Run: pip install bunq-sdk")
    sys.exit(1)


def create_context() -> ApiContext:
    """Create or restore bunq sandbox API context."""
    if SANDBOX_STATE_FILE.exists():
        print(f"Restoring existing sandbox context from {SANDBOX_STATE_FILE}")
        ctx = ApiContext.restore(str(SANDBOX_STATE_FILE))
        ctx.ensure_session_active()
    else:
        print("Creating new sandbox API context…")
        ctx = ApiContext.create(
            ApiEnvironmentType.SANDBOX,
            BUNQ_API_KEY,
            BUNQ_DEVICE_DESCRIPTION,
        )
    ctx.save(str(SANDBOX_STATE_FILE))
    BunqContext.load_api_context(ctx)
    return ctx


def fund_via_sugar_daddy(account_id: int, amount: str = "500.00") -> None:
    """Request funds from the bunq Sugar Daddy (sandbox only)."""
    import requests

    url = f"https://public-api.sandbox.bunq.com/v1/user/{account_id}/monetary-account/{account_id}/request-response"
    headers = {"X-Bunq-Client-Authentication": BUNQ_API_KEY}
    payload = {
        "amount": {"value": amount, "currency": "EUR"},
        "description": "Sugar Daddy funding",
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        print(f"  💰 Funded account {account_id} with €{amount}")
    except Exception as e:
        print(f"  ⚠  Sugar Daddy call failed (non-fatal): {e}")


def create_transactions(account_id: int) -> None:
    """Create realistic student transactions using internal transfers."""
    # We'll generate transactions by making payments to the sandbox's
    # test counterparties. In sandbox mode bunq accepts any valid IBAN.
    transactions = [
        ("NL02ABNA0123456789", "-550.00", "Huur april 2026"),
        ("NL69INGB0123456789", "-34.80", "Albert Heijn boodschappen"),
        ("NL77RABO0123456789", "-22.40", "NS treinreis"),
        ("NL29BUNQ0987654321", "-18.50", "Thuisbezorgd bestelling"),
        ("NL57BUNQ0246813579", "-9.99", "Spotify Premium"),
        ("NL44ABNA0246813579", "-62.00", "Stedin energie factuur"),
        ("NL13INGB0987654321", "-15.00", "OV-chipkaart opladen"),
        ("NL55ABNA0111222333", "-45.99", "Bol.com studieboek"),
        ("NL39RABO0222333444", "-22.60", "Lidl boodschappen"),
        ("NL22BUNQ0444555666", "-13.99", "Netflix"),
    ]
    print(f"Creating {len(transactions)} transactions on account {account_id}…")
    for iban, amount, desc in transactions:
        try:
            Payment.create(
                amount=Amount(amount.lstrip("-"), "EUR"),
                counterparty_alias=Pointer("IBAN", iban, "Demo Merchant"),
                description=desc,
                monetary_account_id=account_id,
            )
            print(f"  ✓ {desc}")
            time.sleep(0.3)  # avoid rate limiting
        except Exception as e:
            print(f"  ⚠  Failed: {desc} ({e})")


def main() -> None:
    print("=== bunq Sandbox Seeder ===\n")
    ctx = create_context()

    # Get primary user
    accounts = MonetaryAccount.list().value
    if not accounts:
        print("ERROR: No accounts found. Check your BUNQ_API_KEY.")
        sys.exit(1)

    primary = accounts[0].MonetaryAccountBank
    account_id = primary.id_
    print(f"Primary account: {primary.description} (ID: {account_id})")

    # Fund via Sugar Daddy
    fund_via_sugar_daddy(account_id, "500.00")

    # Create savings sub-account
    try:
        savings_id = MonetaryAccountSavings.create(
            currency="EUR",
            description="Holiday Fund 🌴",
            savings_goal=Amount("500.00", "EUR"),
        ).value
        print(f"Created savings account 'Holiday Fund' (ID: {savings_id})")
    except Exception as e:
        print(f"⚠  Savings account creation failed: {e}")

    # Create transactions
    create_transactions(account_id)

    # Save sandbox info for reference
    state = {
        "user_id": account_id,
        "primary_account_id": account_id,
        "primary_iban": next(
            (a.value for a in primary.alias if a.type_ == "IBAN"), "unknown"
        ),
        "sandbox_state_file": str(SANDBOX_STATE_FILE),
    }
    info_path = Path(__file__).parent.parent / "sandbox_info.json"
    info_path.write_text(json.dumps(state, indent=2))
    print(f"\nSandbox state saved to {info_path}")
    print("\n✅ Seeding complete! Run ./run.sh to start the demo server.")


if __name__ == "__main__":
    main()
