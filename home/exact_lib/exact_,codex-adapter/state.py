"""Bounded in-memory storage for opaque Codex reasoning items."""

from __future__ import annotations

import threading
from collections import OrderedDict
from copy import deepcopy
from typing import Any


class OpaqueReasoningStore:
    """Associate encrypted reasoning with the tool call that follows it."""

    def __init__(self, limit: int = 256) -> None:
        self._limit = limit
        self._items: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def put(self, call_id: str, item: dict[str, Any]) -> None:
        with self._lock:
            self._items[call_id] = deepcopy(item)
            self._items.move_to_end(call_id)
            while len(self._items) > self._limit:
                self._items.popitem(last=False)

    def get(self, call_id: str) -> dict[str, Any] | None:
        with self._lock:
            item = self._items.get(call_id)
            if item is None:
                return None
            self._items.move_to_end(call_id)
            return deepcopy(item)
