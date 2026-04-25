"""
scheduler.py — Background asyncio task per ShoeWatch.

Each watch runs one _poll_loop task that:
  1. Calls get_prices() every POLL_INTERVAL seconds.
  2. Finds the cheapest in-stock price at or below the user's threshold.
  3. Marks the watch as "triggered" and opens a 30-second grace window.
     The avatar should narrate: "Found it at €X — buying in 30 seconds.
     Say cancel to stop."
  4. If a cancel_pending_buy() call arrives before the timeout, the buy is
     aborted and the watch is marked "cancelled".
  5. Otherwise the buy fires and the watch is marked "completed".

Integration with FastAPI:
  - Call start_watch() from a tool handler (runs inside the event loop).
  - Call stop_all() from the FastAPI lifespan shutdown hook.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from backend.shoe_watch.models import PriceResult, ShoeWatch, WatchStatus
from backend.shoe_watch.purchase import buy_shoe
from backend.shoe_watch.scraper import get_prices
from backend.shoe_watch.store import get_watch, update_status

logger = logging.getLogger(__name__)

POLL_INTERVAL = 30   # seconds between price checks
GRACE_SECONDS = 30   # seconds to wait for a cancel before auto-buy fires

# watch_id → asyncio.Task
_tasks: dict[str, asyncio.Task] = {}
# watch_id → asyncio.Event  (set to abort the pending buy during grace window)
_cancel_events: dict[str, asyncio.Event] = {}
# watch_id → the PriceResult that triggered the grace window
_pending_matches: dict[str, PriceResult] = {}


async def _poll_loop(watch: ShoeWatch, use_stub: bool) -> None:
    logger.info(
        "[shoe-watch] Poll started: %r threshold=€%.2f stub=%s",
        watch.shoe_name, watch.threshold_eur, use_stub,
    )
    while True:
        fresh = get_watch(watch.watch_id)
        if not fresh or fresh.status != WatchStatus.active:
            logger.info("[shoe-watch] Watch %s inactive — stopping", watch.watch_id)
            return

        prices = await get_prices(
            watch.shoe_name, threshold_eur=watch.threshold_eur, use_stub=use_stub
        )

        # Find the cheapest in-stock price at or below threshold
        match = next(
            (
                p for p in sorted(prices, key=lambda p: p.price_eur or 9999)
                if p.price_eur is not None
                and p.price_eur <= watch.threshold_eur
                and p.price_eur <= watch.max_price_eur
                and p.in_stock
            ),
            None,
        )

        if match:
            logger.info(
                "[shoe-watch] Threshold met: %r €%.2f at %s",
                watch.shoe_name, match.price_eur, match.retailer,
            )
            update_status(watch.watch_id, WatchStatus.triggered)
            _pending_matches[watch.watch_id] = match
            _cancel_events[watch.watch_id] = asyncio.Event()

            try:
                await asyncio.wait_for(
                    _cancel_events[watch.watch_id].wait(),
                    timeout=GRACE_SECONDS,
                )
                # Cancel event set — user said "cancel" in time
                logger.info("[shoe-watch] Buy cancelled by user: %s", watch.watch_id)
                update_status(watch.watch_id, WatchStatus.cancelled)
            except asyncio.TimeoutError:
                # Grace window expired — execute the purchase
                result = buy_shoe(watch.shoe_name, match)
                logger.info("[shoe-watch] Auto-buy complete: %s", result.order_id)
                update_status(watch.watch_id, WatchStatus.completed)
            finally:
                _cancel_events.pop(watch.watch_id, None)
                _pending_matches.pop(watch.watch_id, None)
            return

        await asyncio.sleep(POLL_INTERVAL)


def start_watch(watch: ShoeWatch, *, use_stub: bool = False) -> None:
    """
    Launch the background poll loop for this watch.

    Must be called from within a running asyncio event loop (e.g. from a
    FastAPI route handler or lifespan context). In mock_mode, use_stub=True
    so the demo triggers within a few poll cycles regardless of network.

    Args:
        watch:    The ShoeWatch (must already be saved in the store).
        use_stub: True → stub prices (demo); False → real scrapers with stub fallback.
    """
    if watch.watch_id in _tasks:
        return
    try:
        task = asyncio.create_task(_poll_loop(watch, use_stub))
    except RuntimeError:
        # No running event loop (e.g., called from a sync test)
        logger.warning("[shoe-watch] No event loop — background task not started.")
        return
    _tasks[watch.watch_id] = task
    task.add_done_callback(lambda _t: _tasks.pop(watch.watch_id, None))


def cancel_pending_buy(watch_id: str) -> bool:
    """
    Abort a purchase waiting in the grace window.

    Returns True if the cancel signal was sent, False if no buy was pending.
    The poll loop will catch the event and mark the watch as "cancelled".
    """
    event = _cancel_events.get(watch_id)
    if event:
        event.set()
        return True
    return False


def get_pending_match(watch_id: str) -> Optional[PriceResult]:
    """Return the triggering PriceResult if a buy is waiting in the grace window."""
    return _pending_matches.get(watch_id)


async def stop_all() -> None:
    """Cancel all running poll tasks. Call during FastAPI shutdown."""
    for task in list(_tasks.values()):
        task.cancel()
    if _tasks:
        await asyncio.gather(*_tasks.values(), return_exceptions=True)
    _tasks.clear()
