"""Data models for the shoe price-watch feature."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class WatchStatus(str, Enum):
    active = "active"
    triggered = "triggered"   # price matched; grace window open
    cancelled = "cancelled"   # user cancelled (either active or during grace)
    completed = "completed"   # purchase executed


class ShoeWatch(BaseModel):
    watch_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    shoe_name: str
    threshold_eur: float
    max_price_eur: float
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: WatchStatus = WatchStatus.active


class PriceResult(BaseModel):
    retailer: str
    url: str
    price_eur: float | None
    in_stock: bool
    scraped_at: datetime = Field(default_factory=datetime.utcnow)


class PurchaseResult(BaseModel):
    order_id: str = Field(
        default_factory=lambda: "ORD-" + str(uuid.uuid4())[:8].upper()
    )
    retailer: str
    shoe_name: str
    amount_eur: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: str = "SUCCESS"
    note: str = "[MOCK] No real purchase was made."
