"""Discovery repository - in-memory storage with TTL for service instances."""

from __future__ import annotations
import logging
import threading
from typing import Optional

from config import DISCOVERY_TTL
from models.instance_info import InstanceInfo
from utils.passive_expiring_map import PassiveExpiringMap

logger = logging.getLogger(__name__)


class DiscoveryRepository:
    """Interface for discovery data access."""

    def registry(self, info: InstanceInfo):
        raise NotImplementedError

    def unregistry(self, release: str, instance_id: str):
        raise NotImplementedError

    def remove(self, release: str, instance_id: str) -> Optional[InstanceInfo]:
        raise NotImplementedError

    def update(self, info: InstanceInfo):
        raise NotImplementedError

    def contains(self, release: str, instance_id: str) -> bool:
        raise NotImplementedError

    def find_first_by_release(self, release: str) -> Optional[InstanceInfo]:
        raise NotImplementedError


class DiscoveryRepositoryImpl(DiscoveryRepository):
    """In-memory discovery repository with 30-second TTL."""

    def __init__(self):
        self._map = PassiveExpiringMap(ttl=DISCOVERY_TTL)
        self._lock = threading.Lock()

    def _key(self, release: str, instance_id: str) -> str:
        return f"{release}-{instance_id}"

    def registry(self, info: InstanceInfo):
        with self._lock:
            key = self._key(info.release, info.instance_id)
            logger.info(f"Registering instance: {key}")
            self._map.put(key, info)

    def unregistry(self, release: str, instance_id: str):
        with self._lock:
            key = self._key(release, instance_id)
            logger.info(f"Unregistering instance: {key}")
            self._map.remove(key)

    def remove(self, release: str, instance_id: str) -> Optional[InstanceInfo]:
        with self._lock:
            key = self._key(release, instance_id)
            return self._map.remove(key)

    def update(self, info: InstanceInfo):
        with self._lock:
            key = self._key(info.release, info.instance_id)
            self._map.put(key, info)

    def contains(self, release: str, instance_id: str) -> bool:
        return self._map.contains(self._key(release, instance_id))

    def find_first_by_release(self, release: str) -> Optional[InstanceInfo]:
        with self._lock:
            for key, value in self._map.items():
                if isinstance(value, InstanceInfo) and value.release == release:
                    return value
            return None
