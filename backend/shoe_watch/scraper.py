"""
scraper.py — Fetches current shoe prices from Nike.com and Zalando.

Strategy: parse <script type="application/ld+json"> blocks for Schema.org
Product/Offer data. These are required for Google Shopping, so they survive
most anti-bot measures and don't need browser rendering.

If both real scrapers fail (blocked on stage, no internet), the stub fallback
returns deterministically drifting prices so the demo loop still triggers.

Usage:
    prices = await get_prices("Nike Air Max 90", threshold_eur=100.0)
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import time
from typing import Optional

import httpx

from backend.shoe_watch.models import PriceResult

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
}
_TIMEOUT = httpx.Timeout(10.0)

# Stub state: tracks call count per shoe so prices drift predictably on stage.
_stub_state: dict[str, dict] = {}


# ── JSON-LD helpers ────────────────────────────────────────────────────────────

def _extract_json_ld(html: str) -> list[dict]:
    """Return all parsed JSON-LD script blocks from the page HTML."""
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    out = []
    for raw in blocks:
        try:
            out.append(json.loads(raw.strip()))
        except json.JSONDecodeError:
            pass
    return out


def _price_from_json_ld(blocks: list[dict]) -> tuple[float | None, bool]:
    """
    Walk Schema.org JSON-LD blocks and return (price_eur, in_stock).
    Returns (None, False) if no usable offer is found.
    """
    for block in blocks:
        nodes: list = block if isinstance(block, list) else [block]
        if isinstance(block, dict):
            nodes += block.get("@graph", [])
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_type = node.get("@type", "")
            if "Product" not in node_type and "Offer" not in node_type:
                continue
            offers = node.get("offers", node)
            if isinstance(offers, dict):
                offers = [offers]
            for offer in offers if isinstance(offers, list) else []:
                price_raw = offer.get("price") or offer.get("lowPrice")
                if price_raw is None:
                    continue
                try:
                    price = float(str(price_raw).replace(",", "."))
                except (ValueError, TypeError):
                    continue
                if offer.get("priceCurrency", "EUR") != "EUR":
                    continue
                availability = str(offer.get("availability", ""))
                in_stock = "InStock" in availability
                return price, in_stock
    return None, False


# ── HTTP fetch ─────────────────────────────────────────────────────────────────

async def _fetch(url: str) -> Optional[str]:
    """GET a URL with polite headers, return HTML or None on any error."""
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.text
            logger.debug("fetch %s → HTTP %s", url, resp.status_code)
    except Exception as exc:
        logger.debug("fetch %s failed: %s", url, exc)
    return None


# ── Retailer scrapers ──────────────────────────────────────────────────────────

async def _scrape_nike(shoe_name: str) -> Optional[PriceResult]:
    """
    Search Nike NL, follow the first product link, extract JSON-LD price.
    """
    query = shoe_name.replace(" ", "+")
    search_html = await _fetch(f"https://www.nike.com/nl/search?q={query}")
    if not search_html:
        return None

    product_paths = re.findall(r'href="(/nl/t/[^"?#]+)"', search_html)
    if not product_paths:
        return None

    product_url = "https://www.nike.com" + product_paths[0]
    product_html = await _fetch(product_url)
    if not product_html:
        return None

    price, in_stock = _price_from_json_ld(_extract_json_ld(product_html))
    if price is None:
        return None
    return PriceResult(retailer="Nike", url=product_url, price_eur=price, in_stock=in_stock)


async def _scrape_zalando(shoe_name: str) -> Optional[PriceResult]:
    """
    Search Zalando NL, follow the first product link, extract JSON-LD price.
    """
    query = shoe_name.replace(" ", "+")
    search_html = await _fetch(
        f"https://www.zalando.nl/catalogus/?q={query}&cat=herenschoenen"
    )
    if not search_html:
        return None

    product_urls = re.findall(
        r'href="(https://www\.zalando\.nl/[a-z0-9]+-[a-z0-9]+\.html)"', search_html
    )
    if not product_urls:
        return None

    product_html = await _fetch(product_urls[0])
    if not product_html:
        return None

    price, in_stock = _price_from_json_ld(_extract_json_ld(product_html))
    if price is None:
        return None
    return PriceResult(
        retailer="Zalando", url=product_urls[0], price_eur=price, in_stock=in_stock
    )


# ── Stub fallback ──────────────────────────────────────────────────────────────

def _stub_prices(shoe_name: str, threshold_eur: float | None) -> list[PriceResult]:
    """
    Demo fallback: returns deterministically drifting prices so the
    demo loop triggers within 3–4 poll cycles (≈90–120 s at 30 s interval).

    Starts ~8 % above the watch threshold and drops ~3 % per call.
    """
    key = shoe_name.lower()
    if key not in _stub_state:
        base = (threshold_eur * 1.08) if threshold_eur else 109.0
        _stub_state[key] = {"base": base, "calls": 0}
    state = _stub_state[key]
    state["calls"] += 1

    drift_factor = max(1.0 - 0.03 * state["calls"], 0.75)
    mid = round(state["base"] * drift_factor, 2)

    return [
        PriceResult(
            retailer="Nike (demo)",
            url="https://www.nike.com/nl/search?q=" + shoe_name.replace(" ", "+"),
            price_eur=round(mid + random.uniform(-1.5, 1.5), 2),
            in_stock=True,
        ),
        PriceResult(
            retailer="Zalando (demo)",
            url="https://www.zalando.nl/catalogus/?q=" + shoe_name.replace(" ", "+"),
            price_eur=round(mid + random.uniform(-2.0, 2.0), 2),
            in_stock=True,
        ),
    ]


# ── Public API ─────────────────────────────────────────────────────────────────

async def get_prices(
    shoe_name: str,
    *,
    threshold_eur: float | None = None,
    use_stub: bool = False,
) -> list[PriceResult]:
    """
    Return current prices for shoe_name from Nike and Zalando.

    Falls back to stub prices if both real scrapers fail (anti-bot or
    no network). Stub prices drift downward so the demo triggers reliably.

    Args:
        shoe_name:     Canonical shoe name (e.g. "Nike Air Max 90").
        threshold_eur: Used only to seed the stub at a realistic start price.
        use_stub:      If True, skip real scrapers and return stub prices directly.
    """
    if use_stub:
        return _stub_prices(shoe_name, threshold_eur)

    results = await asyncio.gather(
        _scrape_nike(shoe_name),
        _scrape_zalando(shoe_name),
        return_exceptions=True,
    )
    prices = [r for r in results if isinstance(r, PriceResult)]
    if not prices:
        logger.info(
            "Real scrapers returned nothing for %r — falling back to stub", shoe_name
        )
        return _stub_prices(shoe_name, threshold_eur)
    return prices
