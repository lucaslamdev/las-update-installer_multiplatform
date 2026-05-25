"""Discovery manager - business logic for service instance discovery."""

from __future__ import annotations
import logging
import threading
from typing import Optional

from models import InstanceInfoExistsException, InstanceInfoNotFoundException
from models.instance_info import InstanceInfo
from repositories.discovery_repository import DiscoveryRepository, DiscoveryRepositoryImpl

logger = logging.getLogger(__name__)


class DiscoveryManager:
    """Interface for discovery business logic."""

    def registry(self, info: InstanceInfo):
        raise NotImplementedError

    def unregistry(self, release: str, instance_id: str):
        raise NotImplementedError

    def update(self, info: InstanceInfo):
        raise NotImplementedError

    def find_first_by_release(self, release: str) -> Optional[InstanceInfo]:
        raise NotImplementedError


class DiscoveryManagerImpl(DiscoveryManager):
    """Discovery business logic implementation."""

    _instance: Optional[DiscoveryManagerImpl] = None

    def __init__(self, repository: Optional[DiscoveryRepository] = None):
        self._repository = repository or DiscoveryRepositoryImpl()
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> DiscoveryManagerImpl:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def registry(self, info: InstanceInfo):
        with self._lock:
            if self._repository.contains(info.release, info.instance_id):
                raise InstanceInfoExistsException(
                    f"Instance already registered: {info.release}-{info.instance_id}"
                )
            self._repository.registry(info)
            logger.info(f"Registered instance: {info.release}-{info.instance_id}")

    def unregistry(self, release: str, instance_id: str):
        with self._lock:
            self._repository.unregistry(release, instance_id)
            logger.info(f"Unregistered instance: {release}-{instance_id}")

    def update(self, info: InstanceInfo):
        with self._lock:
            if not self._repository.contains(info.release, info.instance_id):
                raise InstanceInfoNotFoundException(
                    f"Instance not found: {info.release}-{info.instance_id}"
                )
            self._repository.update(info)
            logger.info(f"Updated instance: {info.release}-{info.instance_id}")

    def find_first_by_release(self, release: str) -> Optional[InstanceInfo]:
        return self._repository.find_first_by_release(release)
