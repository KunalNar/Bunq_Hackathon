"""
purchase.py — Mock shoe purchase that debits the in-memory ledger.

The actual retailer checkout is mocked — integrating with Nike/Zalando
payment APIs is out of scope for the hackathon demo. What makes it feel real:
  - Debits the user's mock bunq balance.
  - Prepends a transaction to fixtures/transactions.json so it appears in the UI.
  - Returns a plausible retailer order confirmation number.
  - Writes an audit log entry.

Call buy_shoe() after the 30-second grace window expires without cancellation.
"""

from __future__ import annotations

import json
import logging
import random
import string
from datetime import datetime
from pathlib import Path

from backend.shoe_watch.models import PriceResult, PurchaseResult

logger = logging.getLogger(__name__)

_ORDER_PREFIXES = {
    "Nike": "NK",
    "Nike (demo)": "NK",
    "Zalando": "ZL",
    "Zalando (demo)": "ZL",
}


def _order_id(retailer: str) -> str:
    prefix = _ORDER_PREFIXES.get(retailer, "ORD")
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f"{prefix}-{suffix}"


def _debit_ledger(shoe_name: str, amount_eur: float, retailer: str) -> None:
    """Prepend a debit transaction to fixtures/transactions.json."""
    from src.config import TRANSACTIONS_FILE

    try:
        with open(TRANSACTIONS_FILE) as f:
            data = json.load(f)
        txn = {
            "id": "shoe-" + "".join(random.choices(string.digits, k=6)),
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "merchant": retailer,
            "amount_eur": -round(amount_eur, 2),
            "description": f"Auto-purchase: {shoe_name}",
            "category": "other",
        }
        data["transactions"].insert(0, txn)
        data["account"]["balance_eur"] = round(
            data["account"]["balance_eur"] - amount_eur, 2
        )
        with open(TRANSACTIONS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as exc:
        logger.warning("Could not debit mock ledger: %s", exc)


def _audit(order_id: str, shoe_name: str, amount_eur: float, retailer: str) -> None:
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": (
            f"[SHOE-WATCH] Auto-purchased {shoe_name} from {retailer} "
            f"for €{amount_eur:.2f}. Order {order_id}."
        ),
        "mock": True,
    }
    with open(Path("audit_log.jsonl"), "a") as f:
        f.write(json.dumps(entry) + "\n")


def buy_shoe(shoe_name: str, match: PriceResult) -> PurchaseResult:
    """
    Execute a mock shoe purchase.

    Debits the mock bunq ledger, logs the purchase, and returns a realistic
    PurchaseResult. No real payment API is called.

    Args:
        shoe_name: Canonical shoe name (confirmed by the user before the watch started).
        match:     The PriceResult whose price triggered the threshold.

    Returns:
        PurchaseResult with order_id, retailer, amount_eur, status="SUCCESS".
    """
    oid = _order_id(match.retailer)
    amount = round(match.price_eur, 2)
    _debit_ledger(shoe_name, amount, match.retailer)
    _audit(oid, shoe_name, amount, match.retailer)
    logger.info(
        "Mock purchase: %s from %s for €%.2f → %s", shoe_name, match.retailer, amount, oid
    )
    return PurchaseResult(
        order_id=oid,
        retailer=match.retailer,
        shoe_name=shoe_name,
        amount_eur=amount,
    )
