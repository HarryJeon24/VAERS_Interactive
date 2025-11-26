# backend/services/cache.py
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Callable, Dict, Optional, Tuple


def _now() -> float:
    return time.time()


def stable_hash(obj: Any) -> str:
    """
    Hash arbitrary JSON-serializable objects in a stable way.
    Useful for caching request args / filter dicts.
    """
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return sha256(payload).hexdigest()


@dataclass
class CacheEntry:
    expires_at: float
    value: Any


class TTLCache:
    """
    Simple in-memory TTL cache.
    - Thread-safe via a single lock (fine for dev; for prod use Redis/Memorystore).
    - Supports get/set and get_or_set (compute on miss).
    """

    def __init__(self, default_ttl_seconds: int = 30, max_items: int = 256):
        self.default_ttl = int(default_ttl_seconds)
        self.max_items = int(max_items)
        self._lock = threading.Lock()
        self._store: Dict[str, CacheEntry] = {}

    def _evict_expired_locked(self) -> None:
        t = _now()
        expired = [k for k, v in self._store.items() if v.expires_at <= t]
        for k in expired:
            self._store.pop(k, None)

    def _evict_overflow_locked(self) -> None:
        """
        If we exceed max_items, evict earliest-expiring items first.
        """
        if len(self._store) <= self.max_items:
            return
        items: list[Tuple[str, CacheEntry]] = sorted(self._store.items(), key=lambda kv: kv[1].expires_at)
        over = len(items) - self.max_items
        for i in range(over):
            self._store.pop(items[i][0], None)

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            self._evict_expired_locked()
            ent = self._store.get(key)
            if not ent:
                return None
            if ent.expires_at <= _now():
                self._store.pop(key, None)
                return None
            return ent.value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        ttl = self.default_ttl if ttl_seconds is None else int(ttl_seconds)
        with self._lock:
            self._evict_expired_locked()
            self._store[key] = CacheEntry(expires_at=_now() + ttl, value=value)
            self._evict_overflow_locked()

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def size(self) -> int:
        with self._lock:
            self._evict_expired_locked()
            return len(self._store)

    def get_or_set(
        self,
        key: str,
        compute: Callable[[], Any],
        ttl_seconds: Optional[int] = None,
    ) -> Any:
        existing = self.get(key)
        if existing is not None:
            return existing
        value = compute()
        self.set(key, value, ttl_seconds=ttl_seconds)
        return value


# Global cache instance for dev (shared in-process)
CACHE = TTLCache(default_ttl_seconds=45, max_items=256)


def main() -> None:
    """
    Test:
      python backend/services/cache.py
    """
    cache = TTLCache(default_ttl_seconds=1, max_items=2)

    key = stable_hash({"endpoint": "signals", "year": 2018, "min_count": 5})
    print("[TEST] key =", key)

    print("[TEST] get before set:", cache.get(key))
    cache.set(key, {"hello": "world"})
    print("[TEST] get after set:", cache.get(key))
    print("[TEST] size:", cache.size())

    time.sleep(1.1)
    print("[TEST] after expiry:", cache.get(key))
    print("[TEST] size after expiry:", cache.size())

    # overflow eviction
    cache.set("k1", 1, ttl_seconds=10)
    cache.set("k2", 2, ttl_seconds=10)
    cache.set("k3", 3, ttl_seconds=10)
    print("[TEST] size after overflow (max=2):", cache.size())
    print("[TEST] has k1?", cache.get("k1") is not None, "has k2?", cache.get("k2") is not None, "has k3?", cache.get("k3") is not None)

    # get_or_set
    def compute():
        return {"computed_at": _now()}

    v1 = cache.get_or_set("compute_key", compute, ttl_seconds=5)
    v2 = cache.get_or_set("compute_key", compute, ttl_seconds=5)
    print("[TEST] get_or_set stable:", v1 == v2, v1)

    print("[OK] cache self-test complete.")


if __name__ == "__main__":
    main()
