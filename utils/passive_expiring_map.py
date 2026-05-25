"""PassiveExpiringMap - a dictionary with automatic key expiration.

Equivalent to the Java PassiveExpiringMap from Apache Commons Collections.
"""

import threading
import time
from typing import Any, Optional


class ConstantTimeToLiveExpirationPolicy:
    """Fixed time-to-live expiration policy."""

    def __init__(self, ttl: float):
        self._ttl = ttl

    def ttl(self) -> float:
        return self._ttl


class PassiveExpiringMap:
    """A thread-safe dictionary where entries expire after a configurable TTL.

    Expiration is checked passively on access (get/contains).
    """

    def __init__(self, ttl: float, policy: Optional[ConstantTimeToLiveExpirationPolicy] = None):
        self._policy = policy or ConstantTimeToLiveExpirationPolicy(ttl)
        self._map: dict[str, tuple[Any, float]] = {}
        self._lock = threading.Lock()

    def _is_expired(self, entry_time: float) -> bool:
        return (time.time() - entry_time) > self._policy.ttl()

    def _cleanup(self):
        """Remove expired entries."""
        now = time.time()
        expired_keys = [
            k for k, (v, t) in self._map.items()
            if (now - t) > self._policy.ttl()
        ]
        for k in expired_keys:
            del self._map[k]

    def put(self, key: str, value: Any):
        with self._lock:
            self._cleanup()
            self._map[key] = (value, time.time())

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._map.get(key)
            if entry is None:
                return None
            value, entry_time = entry
            if self._is_expired(entry_time):
                del self._map[key]
                return None
            # Refresh TTL on access
            self._map[key] = (value, time.time())
            return value

    def remove(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._map.pop(key, None)
            if entry is None:
                return None
            value, entry_time = entry
            if self._is_expired(entry_time):
                return None
            return value

    def contains(self, key: str) -> bool:
        return self.get(key) is not None

    def keys(self) -> list[str]:
        with self._lock:
            self._cleanup()
            return list(self._map.keys())

    def items(self) -> list[tuple[str, Any]]:
        with self._lock:
            self._cleanup()
            return [(k, v) for k, (v, _) in self._map.items()]

    def __len__(self) -> int:
        with self._lock:
            self._cleanup()
            return len(self._map)

    def __contains__(self, key: str) -> bool:
        return self.contains(key)
