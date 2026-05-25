"""MvupdateKey repository - in-memory storage with TTL for authentication keys.

Java behavior: contains() re-adds the key to refresh the TTL timer.
"""

from __future__ import annotations
import logging
from typing import Optional

from config import MVUPDATE_KEY_TTL
from models.mvupdate_key import MvupdateKey
from utils.passive_expiring_map import PassiveExpiringMap

logger = logging.getLogger(__name__)


class MvupdateKeyRepository:
    """Interface for mvupdate key data access."""

    def add_instance(self, key: MvupdateKey):
        raise NotImplementedError

    def remove_instance(self, key_id: str):
        raise NotImplementedError

    def get_by_id(self, key_id: str) -> Optional[MvupdateKey]:
        raise NotImplementedError

    def contains(self, key_id: str) -> bool:
        raise NotImplementedError


class MvupdateKeyRepositoryImpl(MvupdateKeyRepository):
    """In-memory mvupdate key repository with 8-hour TTL.

    Singleton: all instances share the same underlying map.
    Java behavior: contains() re-adds the key to refresh the TTL timer,
    keeping the key alive while it's actively being checked.
    """

    _shared_map: Optional[PassiveExpiringMap] = None

    def __init__(self):
        if MvupdateKeyRepositoryImpl._shared_map is None:
            MvupdateKeyRepositoryImpl._shared_map = PassiveExpiringMap(ttl=MVUPDATE_KEY_TTL)
        self._map = MvupdateKeyRepositoryImpl._shared_map

    def add_instance(self, key: MvupdateKey):
        logger.info(f"Adding mvupdate key: {key.id}")
        self._map.put(key.id, key)

    def remove_instance(self, key_id: str):
        self._map.remove(key_id)

    def get_by_id(self, key_id: str) -> Optional[MvupdateKey]:
        return self._map.get(key_id)

    def contains(self, key_id: str) -> bool:
        """Check if key exists AND refresh its TTL (matches Java behavior)."""
        key = self._map.get(key_id)
        if key is not None:
            # Re-add to refresh TTL (matches Java: addInstance(key) on contains)
            self._map.put(key_id, key)
            return True
        return False
