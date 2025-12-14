# backend/services/cache.py
from __future__ import annotations

import json
import os
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


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    sets: int = 0
    evicted_expired: int = 0
    evicted_overflow: int = 0


def _env_bool(name: str, default: bool = True) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip().lower()
    return v in ("1", "true", "t", "yes", "y", "on")


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None:
        return default
    try:
        return int(v)
    except Exception:
        return default


class TTLCache:
    """
    Simple in-memory TTL cache.

    - Thread-safe via a single lock.
    - Supports get/set and get_or_set (compute on miss).
    - get_or_set uses a per-key lock to avoid duplicate recomputation ("single flight").
    """

    def __init__(
        self,
        default_ttl_seconds: int = 30,
        max_items: int = 256,
        enabled: bool = True,
    ):
        self.default_ttl = int(default_ttl_seconds)
        self.max_items = int(max_items)
        self.enabled = bool(enabled)

        self._lock = threading.Lock()
        self._store: Dict[str, CacheEntry] = {}
        self._stats = CacheStats()

        # Per-key locks for get_or_set single-flight
        self._key_locks: Dict[str, threading.Lock] = {}
        self._key_locks_lock = threading.Lock()

    def stats(self) -> CacheStats:
        # return a copy so callers can’t mutate internal stats
        with self._lock:
            return CacheStats(**self._stats.__dict__)

    def _evict_expired_locked(self) -> None:
        t = _now()
        expired_keys = [k for k, v in self._store.items() if v.expires_at <= t]
        for k in expired_keys:
            self._store.pop(k, None)
        if expired_keys:
            self._stats.evicted_expired += len(expired_keys)

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
        if over > 0:
            self._stats.evicted_overflow += over

    def prune(self) -> None:
        """
        Manually prune expired/overflow entries.
        Useful if you want to call it on a timer in production.
        """
        if not self.enabled:
            return
        with self._lock:
            self._evict_expired_locked()
            self._evict_overflow_locked()

    def get(self, key: str) -> Optional[Any]:
        if not self.enabled:
            return None
        with self._lock:
            self._evict_expired_locked()
            ent = self._store.get(key)
            if not ent:
                self._stats.misses += 1
                return None
            if ent.expires_at <= _now():
                self._store.pop(key, None)
                self._stats.misses += 1
                return None
            self._stats.hits += 1
            return ent.value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        if not self.enabled:
            return
        ttl = self.default_ttl if ttl_seconds is None else int(ttl_seconds)
        with self._lock:
            self._evict_expired_locked()
            self._store[key] = CacheEntry(expires_at=_now() + ttl, value=value)
            self._stats.sets += 1
            self._evict_overflow_locked()

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def size(self) -> int:
        if not self.enabled:
            return 0
        with self._lock:
            self._evict_expired_locked()
            return len(self._store)

    def _get_key_lock(self, key: str) -> threading.Lock:
        """
        Get (or create) a per-key lock for get_or_set.
        """
        with self._key_locks_lock:
            lk = self._key_locks.get(key)
            if lk is None:
                lk = threading.Lock()
                self._key_locks[key] = lk
            return lk

    def get_or_set(
        self,
        key: str,
        compute: Callable[[], Any],
        ttl_seconds: Optional[int] = None,
    ) -> Any:
        """
        Return cached value if present; otherwise compute and cache it.

        Uses a per-key lock so that under concurrent requests,
        only one thread computes the value for a given key.
        """
        existing = self.get(key)
        if existing is not None:
            return existing

        # single-flight
        lk = self._get_key_lock(key)
        with lk:
            # check again after acquiring lock
            existing2 = self.get(key)
            if existing2 is not None:
                return existing2

            value = compute()
            self.set(key, value, ttl_seconds=ttl_seconds)
            return value


# Global cache instance for dev (shared in-process)
# You can override with env:
#   CACHE_ENABLED=0
#   CACHE_DEFAULT_TTL_SECONDS=300
#   CACHE_MAX_ITEMS=2048
CACHE = TTLCache(
    default_ttl_seconds=_env_int("CACHE_DEFAULT_TTL_SECONDS", 45),
    max_items=_env_int("CACHE_MAX_ITEMS", 2048),
    enabled=_env_bool("CACHE_ENABLED", True),
)


def main() -> None:
    """
    Test:
      python backend/services/cache.py
    """
    cache = TTLCache(default_ttl_seconds=1, max_items=2, enabled=True)

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
    print(
        "[TEST] has k1?",
        cache.get("k1") is not None,
        "has k2?",
        cache.get("k2") is not None,
        "has k3?",
        cache.get("k3") is not None,
    )

    # get_or_set single-flight sanity
    def compute():
        return {"computed_at": _now()}

    v1 = cache.get_or_set("compute_key", compute, ttl_seconds=5)
    v2 = cache.get_or_set("compute_key", compute, ttl_seconds=5)
    print("[TEST] get_or_set stable:", v1 == v2, v1)

    print("[TEST] stats:", cache.stats())
    print("[OK] cache self-test complete.")


if __name__ == "__main__":
    main()
