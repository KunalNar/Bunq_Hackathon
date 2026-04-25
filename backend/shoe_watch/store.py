"""In-memory store for active ShoeWatch records."""

from __future__ import annotations

import threading
from typing import Optional

from backend.shoe_watch.models import ShoeWatch, WatchStatus

_lock = threading.Lock()
_watches: dict[str, ShoeWatch] = {}


def add_watch(watch: ShoeWatch) -> str:
    with _lock:
        _watches[watch.watch_id] = watch
    return watch.watch_id


def get_watch(watch_id: str) -> Optional[ShoeWatch]:
    return _watches.get(watch_id)


def list_watches() -> list[ShoeWatch]:
    with _lock:
        return list(_watches.values())


def cancel_watch(watch_id: str) -> bool:
    with _lock:
        watch = _watches.get(watch_id)
        if not watch or watch.status not in (WatchStatus.active, WatchStatus.triggered):
            return False
        watch.status = WatchStatus.cancelled
        return True


def update_status(watch_id: str, status: WatchStatus) -> None:
    with _lock:
        watch = _watches.get(watch_id)
        if watch:
            watch.status = status
