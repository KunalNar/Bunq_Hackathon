"""
handlers.py — Tool implementation layer (mock + real).

Every tool defined in tools.py has a corresponding handler here.
Each handler exists twice:
  1. _mock_*  — uses fixture data from fixtures/transactions.json
  2. _real_*  — calls the actual bunq SDK

The top-level `execute_tool` dispatcher routes to the right one
based on the `mock_mode` flag. This dual-mode design means you can
demo offline and switch to live bunq sandbox with a single env var.

To add a new tool:
  1. Add the schema to tools.py
  2. Add _mock_<name> and _real_<name> here
  3. Add a case in execute_tool()
"""

import base64
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config import FIXTURES_DIR, MOCK_MODE, SANDBOX_STATE_FILE, TRANSACTIONS_FILE

logger = logging.getLogger(__name__)

# ── Fixture helpers ────────────────────────────────────────────────────────────

def _load_fixtures() -> dict:
    """Load transactions.json once and cache it."""
    if not hasattr(_load_fixtures, "_cache"):
        with open(TRANSACTIONS_FILE) as f:
            _load_fixtures._cache = json.load(f)
    return _load_fixtures._cache


# ── Mock handlers ──────────────────────────────────────────────────────────────

def _mock_get_balance(_args: dict) -> dict:
    data = _load_fixtures()
    acct = data["account"]
    return {
        "account_name": acct["name"],
        "iban": acct["iban"],
        "balance_eur": acct["balance_eur"],
        "currency": acct["currency"],
    }


def _mock_list_transactions(args: dict) -> dict:
    data = _load_fixtures()
    transactions = data["transactions"]
    limit = min(args.get("limit", 10), 50)
    cat = args.get("category_filter")
    if cat:
        transactions = [t for t in transactions if t.get("category") == cat]
    return {"transactions": transactions[:limit], "total_returned": min(limit, len(transactions))}


def _mock_lookup_contact(args: dict) -> dict:
    data = _load_fixtures()
    contacts = data.get("contacts", [])
    query = args["name"].lower()
    matches = [
        c for c in contacts
        if query in c["name"].lower() or query in c["full_name"].lower()
    ]
    if not matches:
        return {"matches": [], "note": f"No contact found for '{args['name']}'."}
    return {"matches": matches}


def _mock_create_payment(args: dict) -> dict:
    return {
        "status": "SUCCESS",
        "payment_id": "mock-pay-" + datetime.utcnow().strftime("%H%M%S"),
        "to_iban": args["to_iban"],
        "amount_eur": args["amount_eur"],
        "description": args["description"],
        "timestamp": datetime.utcnow().isoformat(),
        "note": "[MOCK] No real money was moved.",
    }


def _mock_create_request_inquiry(args: dict) -> dict:
    return {
        "status": "SENT",
        "request_id": "mock-req-" + datetime.utcnow().strftime("%H%M%S"),
        "to_email": args["to_email"],
        "amount_eur": args["amount_eur"],
        "description": args["description"],
        "payment_link": "https://bunq.me/mock/pay/" + args["to_email"].split("@")[0],
        "note": "[MOCK] No real request was created.",
    }


def _mock_categorize_transaction(args: dict) -> dict:
    return {
        "status": "UPDATED",
        "transaction_id": args["transaction_id"],
        "category": args["category"],
        "note": "[MOCK] Category stored in memory only.",
    }


def _mock_list_savings_goals(_args: dict) -> dict:
    return {
        "savings_goals": [
            {"name": "Holiday Fund", "balance_eur": 320.00, "target_eur": 1500.00, "remaining_eur": 1180.00},
            {"name": "New Laptop",   "balance_eur": 750.00, "target_eur": 1200.00, "remaining_eur": 450.00},
            {"name": "Emergency",    "balance_eur": 500.00, "target_eur": None,     "remaining_eur": None},
        ]
    }


def _mock_top_up_savings_goal(args: dict) -> dict:
    return {
        "status": "SUCCESS",
        "jar_name": args["jar_name"],
        "amount_eur": args["amount_eur"],
        "note": "[MOCK] No real money was moved.",
    }


def _mock_create_savings_goal(args: dict) -> dict:
    return {
        "status": "CREATED",
        "savings_account_id": "mock-savings-" + datetime.utcnow().strftime("%H%M%S"),
        "name": args["name"],
        "target_eur": args.get("target_eur"),
        "balance_eur": 0.00,
        "note": "[MOCK] No real sub-account was created.",
    }


def _mock_parse_receipt(args: dict) -> dict:
    """Return realistic dummy receipt data. In production, this calls Claude vision."""
    return {
        "merchant": "Albert Heijn",
        "total": 34.80,
        "currency": "EUR",
        "date": "2026-04-14",
        "line_items": [
            {"name": "Pasta penne 500g", "price": 1.99, "qty": 2},
            {"name": "Tomatensaus", "price": 1.49, "qty": 3},
            {"name": "Kipfilet 400g", "price": 5.99, "qty": 1},
            {"name": "Geraspte kaas 200g", "price": 2.29, "qty": 1},
            {"name": "Melk 1L", "price": 1.15, "qty": 2},
            {"name": "Brood volkoren", "price": 2.39, "qty": 1},
            {"name": "Sinaasappelsap 1L", "price": 2.79, "qty": 2},
        ],
        "category_guess": "food",
        "note": "[MOCK] Real receipts call Claude vision API.",
    }


def _mock_log_action(args: dict) -> dict:
    log_path = Path("audit_log.jsonl")
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": args["action_description"],
        "mock": True,
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return {"status": "LOGGED", "entry": entry}


# ── Real handlers (bunq SDK) ───────────────────────────────────────────────────

def _get_bunq_context():
    """Lazily initialise bunq SDK context. Raises if not configured."""
    try:
        from bunq.sdk.context.api_context import ApiContext
        from bunq.sdk.context.bunq_context import BunqContext

        if not hasattr(_get_bunq_context, "_initialized"):
            state_file = str(SANDBOX_STATE_FILE)
            ctx = ApiContext.restore(state_file)
            ctx.ensure_session_active()
            ctx.save(state_file)
            BunqContext.load_api_context(ctx)
            _get_bunq_context._initialized = True

        return True
    except Exception as exc:
        raise RuntimeError(f"bunq SDK not initialised. Run scripts/seed_sandbox.py first. ({exc})")


def _get_primary_account():
    from bunq.sdk.model.generated.endpoint import MonetaryAccountBankApiObject

    accounts = MonetaryAccountBankApiObject.list().value
    if not accounts:
        return None
    return accounts[0]


def _get_bunq_user_display_name():
    from bunq.sdk.model.generated.endpoint import UserApiObject

    users = UserApiObject.list().value
    if not users:
        return None

    user = users[0].get_referenced_object()
    display_name = getattr(user, "display_name", None)
    if display_name:
        return display_name

    public_nick_name = getattr(user, "public_nick_name", None)
    if public_nick_name:
        return public_nick_name

    parts = [
        getattr(user, "first_name", None),
        getattr(user, "middle_name", None),
        getattr(user, "last_name", None),
    ]
    full_name = " ".join(part for part in parts if part)
    return full_name or None


def _get_counterparty_name(counterparty_alias, description: str | None = None) -> str:
    if not counterparty_alias:
        return description or "Unknown counterparty"

    label = getattr(counterparty_alias, "label_monetary_account", None)
    if label:
        display_name = getattr(label, "display_name", None)
        if display_name:
            return display_name

        label_user = getattr(label, "label_user", None)
        user_display_name = getattr(label_user, "display_name", None)
        if user_display_name:
            return user_display_name

        iban = getattr(label, "iban", None)
        if iban:
            return iban

    pointer = getattr(counterparty_alias, "pointer", None)
    if pointer:
        pointer_name = getattr(pointer, "name", None)
        if pointer_name:
            return pointer_name

        pointer_value = getattr(pointer, "value", None)
        if pointer_value:
            return pointer_value

    return description or "Unknown counterparty"


def _real_lookup_contact(args: dict) -> dict:
    """Scan the last 50 payments for counterparties matching the query name."""
    _get_bunq_context()
    from bunq.sdk.model.generated.endpoint import PaymentApiObject

    acct = _get_primary_account()
    if not acct:
        return {"matches": [], "note": "No accounts found."}

    payments = PaymentApiObject.list(monetary_account_id=acct.id_).value[:50]
    query = args["name"].lower()
    seen_ibans: set[str] = set()
    matches = []

    for p in payments:
        alias = p.counterparty_alias
        name = _get_counterparty_name(alias, p.description)
        if query not in name.lower():
            continue

        label = getattr(alias, "label_monetary_account", None)
        iban = getattr(label, "iban", None) if label else None
        if not iban:
            pointer = getattr(alias, "pointer", None)
            if pointer and getattr(pointer, "type_", None) == "IBAN":
                iban = getattr(pointer, "value", None)

        if not iban or iban in seen_ibans:
            continue
        seen_ibans.add(iban)

        label_user = getattr(label, "label_user", None) if label else None
        email_pointer = None
        if label_user:
            for ptr in getattr(label_user, "aliases", None) or []:
                if getattr(ptr, "type_", None) == "EMAIL":
                    email_pointer = getattr(ptr, "value", None)
                    break

        matches.append({
            "name": name,
            "full_name": name,
            "iban": iban,
            "email": email_pointer,
        })

    if not matches:
        return {"matches": [], "note": f"No contact found for '{args['name']}' in payment history."}
    return {"matches": matches}


def _real_get_balance(_args: dict) -> dict:
    _get_bunq_context()

    acct = _get_primary_account()
    if not acct:
        return {"error": "No accounts found"}
    account_name = _get_bunq_user_display_name() or acct.display_name or acct.description
    return {
        "account_name": account_name,
        "iban": next(
            (a.value for a in acct.alias if a.type_ == "IBAN"), "unknown"
        ),
        "balance_eur": float(acct.balance.value),
        "currency": acct.balance.currency,
    }

def _real_list_transactions(args: dict) -> dict:
    _get_bunq_context()
    from bunq.sdk.model.generated.endpoint import PaymentApiObject

    acct = _get_primary_account()
    if not acct:
        return {"transactions": [], "total_returned": 0}
    account_id = acct.id_
    limit = min(args.get("limit", 10), 50)
    payments = PaymentApiObject.list(monetary_account_id=account_id).value[:limit]
    txns = []
    for p in payments:
        txns.append({
            "id": str(p.id_),
            "date": str(p.created)[:10],
            "merchant": _get_counterparty_name(p.counterparty_alias, p.description),
            "amount_eur": float(p.amount.value),
            "description": p.description,
            "category": "other",
        })
    cat = args.get("category_filter")
    if cat:
        txns = [t for t in txns if t["category"] == cat]
    return {"transactions": txns, "total_returned": len(txns)}


def _real_create_payment(args: dict) -> dict:
    _get_bunq_context()
    from bunq.sdk.model.generated.endpoint import PaymentApiObject
    from bunq.sdk.model.generated.object_ import AmountObject, PointerObject

    acct = _get_primary_account()
    if not acct:
        return {"status": "ERROR", "error": "No accounts found"}
    payment_id = PaymentApiObject.create(
        amount=AmountObject(str(args["amount_eur"]), "EUR"),
        counterparty_alias=PointerObject("IBAN", args["to_iban"]),
        description=args["description"],
        monetary_account_id=acct.id_,
    ).value
    return {
        "status": "SUCCESS",
        "payment_id": str(payment_id),
        "to_iban": args["to_iban"],
        "amount_eur": args["amount_eur"],
        "description": args["description"],
    }


def _real_create_request_inquiry(args: dict) -> dict:
    _get_bunq_context()
    from bunq.sdk.model.generated.endpoint import RequestInquiryApiObject
    from bunq.sdk.model.generated.object_ import AmountObject, PointerObject

    acct = _get_primary_account()
    if not acct:
        return {"status": "ERROR", "error": "No accounts found"}
    req_id = RequestInquiryApiObject.create(
        amount_inquired=AmountObject(str(args["amount_eur"]), "EUR"),
        counterparty_alias=PointerObject("EMAIL", args["to_email"]),
        description=args["description"],
        allow_bunqme=True,
        monetary_account_id=acct.id_,
    ).value
    return {
        "status": "SENT",
        "request_id": str(req_id),
        "to_email": args["to_email"],
        "amount_eur": args["amount_eur"],
    }


def _real_categorize_transaction(args: dict) -> dict:
    # bunq doesn't have a first-class categorisation API; store locally
    return _mock_categorize_transaction(args)


def _real_list_savings_goals(_args: dict) -> dict:
    _get_bunq_context()
    from bunq.sdk.model.generated.endpoint import MonetaryAccountSavingsApiObject

    accounts = MonetaryAccountSavingsApiObject.list().value
    goals = []
    for acct in accounts:
        if getattr(acct, "status", None) != "ACTIVE":
            continue
        balance = float(acct.balance.value) if acct.balance else 0.0
        target = None
        if acct.savings_goal:
            target = float(acct.savings_goal.value)
        goals.append({
            "name": acct.description,
            "balance_eur": balance,
            "target_eur": target,
            "remaining_eur": round(target - balance, 2) if target is not None else None,
        })
    return {"savings_goals": goals}


def _real_top_up_savings_goal(args: dict) -> dict:
    _get_bunq_context()
    from bunq.sdk.model.generated.endpoint import (
        MonetaryAccountBankApiObject,
        MonetaryAccountSavingsApiObject,
        PaymentApiObject,
    )
    from bunq.sdk.model.generated.object_ import AmountObject, PointerObject

    query = args["jar_name"].lower()
    savings_accounts = MonetaryAccountSavingsApiObject.list().value
    jar = next(
        (a for a in savings_accounts
         if query in (a.description or "").lower() and getattr(a, "status", None) == "ACTIVE"),
        None,
    )
    if not jar:
        return {"status": "ERROR", "error": f"No active savings jar found matching '{args['jar_name']}'."}

    jar_iban = next((a.value for a in (jar.alias or []) if a.type_ == "IBAN"), None)
    if not jar_iban:
        return {"status": "ERROR", "error": "Could not find IBAN for that savings jar."}

    main_accounts = MonetaryAccountBankApiObject.list().value
    if not main_accounts:
        return {"status": "ERROR", "error": "No main account found."}
    main_acct = main_accounts[0]

    amount_str = f"{float(args['amount_eur']):.2f}"
    try:
        payment_id = PaymentApiObject.create(
            amount=AmountObject(amount_str, "EUR"),
            counterparty_alias=PointerObject("IBAN", jar_iban, jar.description),
            description=f"Top up {jar.description}",
            monetary_account_id=main_acct.id_,
        ).value
    except Exception as exc:
        logger.error("bunq top_up_savings_goal failed: %s", exc)
        return {"status": "ERROR", "error": str(exc), "jar_iban": jar_iban}

    return {
        "status": "SUCCESS",
        "payment_id": str(payment_id),
        "jar_name": jar.description,
        "amount_eur": args["amount_eur"],
        "jar_iban": jar_iban,
    }


def _real_create_savings_goal(args: dict) -> dict:
    _get_bunq_context()
    from bunq.sdk.model.generated.endpoint import MonetaryAccountSavingsApiObject
    from bunq.sdk.model.generated.object_ import AmountObject

    target = args.get("target_eur")
    savings_id = MonetaryAccountSavingsApiObject.create(
        currency="EUR",
        description=args["name"],
        savings_goal=AmountObject(str(target), "EUR") if target else None,
    ).value
    return {
        "status": "CREATED",
        "savings_account_id": str(savings_id),
        "name": args["name"],
        "target_eur": target,
    }


def _real_parse_receipt(args: dict) -> dict:
    """Vision call always goes through Claude regardless of mock_mode."""
    import anthropic
    from src.config import ANTHROPIC_API_KEY, SMART_MODEL

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    image_b64 = args["image_base64"]
    response = client.messages.create(
        model=SMART_MODEL,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Extract the following from this receipt image as JSON with keys: "
                            "merchant (string), total (number or null), currency (string, default EUR), "
                            "date (YYYY-MM-DD or null), line_items (array of {name, price, qty}), "
                            "category_guess (one of: food, transport, entertainment, utilities, other). "
                            "If a field is unreadable use null. Do not guess amounts — if unclear set total to null. "
                            "Return ONLY the JSON object, no markdown."
                        ),
                    },
                ],
            }
        ],
    )
    raw = response.content[0].text.strip()
    return json.loads(raw)


def _real_log_action(args: dict) -> dict:
    return _mock_log_action(args)


# ── Dispatcher ─────────────────────────────────────────────────────────────────

_MOCK_HANDLERS: dict[str, Any] = {
    "get_balance": _mock_get_balance,
    "list_transactions": _mock_list_transactions,
    "lookup_contact": _mock_lookup_contact,
    "create_payment": _mock_create_payment,
    "create_request_inquiry": _mock_create_request_inquiry,
    "categorize_transaction": _mock_categorize_transaction,
    "list_savings_goals": _mock_list_savings_goals,
    "top_up_savings_goal": _mock_top_up_savings_goal,
    "create_savings_goal": _mock_create_savings_goal,
    "parse_receipt": _mock_parse_receipt,
    "log_action": _mock_log_action,
}

_REAL_HANDLERS: dict[str, Any] = {
    "get_balance": _real_get_balance,
    "list_transactions": _real_list_transactions,
    "lookup_contact": _real_lookup_contact,
    "create_payment": _real_create_payment,
    "create_request_inquiry": _real_create_request_inquiry,
    "categorize_transaction": _real_categorize_transaction,
    "list_savings_goals": _real_list_savings_goals,
    "top_up_savings_goal": _real_top_up_savings_goal,
    "create_savings_goal": _real_create_savings_goal,
    "parse_receipt": _real_parse_receipt,
    "log_action": _real_log_action,
}


def execute_tool(name: str, args: dict, *, mock_mode: bool = MOCK_MODE) -> dict:
    """
    Route a tool call to the correct mock or real implementation.

    Args:
        name:      Tool name (must match a key in tools.py).
        args:      Parsed arguments from the model's tool_use block.
        mock_mode: If True use fixture data; if False call bunq SDK.

    Returns:
        A dict that will be JSON-serialised and returned to the model.

    Raises:
        KeyError if the tool name is unknown.
    """
    handlers = _MOCK_HANDLERS if mock_mode else _REAL_HANDLERS
    if name not in handlers:
        raise KeyError(f"Unknown tool: {name!r}. Known tools: {list(handlers)}")
    return handlers[name](args)
