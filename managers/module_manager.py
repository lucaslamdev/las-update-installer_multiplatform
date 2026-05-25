"""Module manager - business logic for module lifecycle management."""

from __future__ import annotations
import logging
import threading
import time
from typing import Optional

from config import MODULE_POLL_TIMEOUT, MODULE_POLL_INTERVAL
from models import (
    ModuleExistsException,
    ModuleIllegalStateException,
    ModuleNotFoundException,
)
from models.enums import StatusInstall
from models.module import Module
from models.module_config import ModuleConfig
from repositories.module_repository import ModuleRepository, ModuleRepositoryImpl
from utils.install4j_utils import GenericInstall4jUtils, Install4jUtils
from utils.debug_mode import DebugMode

logger = logging.getLogger(__name__)


class ModuleManager:
    """Interface for module business logic."""

    def create(self, release: str, input_stream, upload_meta: Optional[dict] = None):
        raise NotImplementedError

    def start(self, release: str, args: Optional[list[str]] = None):
        raise NotImplementedError

    def stop(self, release: str):
        raise NotImplementedError

    def delete(self, release: str):
        raise NotImplementedError

    def check(self, release: str) -> Module:
        raise NotImplementedError

    def get_all(self) -> list[Module]:
        raise NotImplementedError


class ModuleManagerImpl(ModuleManager):
    """Module business logic implementation."""

    _instance: Optional[ModuleManagerImpl] = None

    def __init__(
        self,
        repository: Optional[ModuleRepository] = None,
        install4j_utils: Optional[Install4jUtils] = None,
    ):
        self._repository = repository or ModuleRepositoryImpl()
        self._install4j_utils = install4j_utils or GenericInstall4jUtils()
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> ModuleManagerImpl:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_module(self, release: str) -> Module:
        """Get a Module instance for the given release."""
        config = self._repository.get(release)
        module = Module(self._install4j_utils, config)
        if not module.exists():
            raise ModuleNotFoundException(f"Module not found: {release}")
        return module

    def create(self, release: str, input_stream, upload_meta: Optional[dict] = None):
        """Install a new module.

        Java: calls get() which throws ModuleNotFoundException if not found.
        If ModuleNotFoundException caught, falls through to internalCreate().
        If status != UNKNOWN, throws ModuleExistsException.
        """
        with self._lock:
            try:
                existing = self._get_module(release)
                if existing.get_status() != StatusInstall.UNKNOWN:
                    raise ModuleExistsException(f"Module already exists: {release}")
            except ModuleNotFoundException:
                pass  # Expected for new modules - fall through to create

            config = self._repository.create(release, input_stream, upload_meta=upload_meta)
            module = Module(self._install4j_utils, config)
            DebugMode.log_event(
                "module",
                "Installing module",
                release=release,
                installer=config.module_installer_file,
                install_dir=config.module_installer_dir,
            )
            module.install()
            logger.info(f"Module created and installed: {release}")

    def start(self, release: str, args: Optional[list[str]] = None):
        """Start a stopped module."""
        with self._lock:
            module = self._get_module(release)

            status = module.get_status()
            if status != StatusInstall.STOPED:
                raise ModuleIllegalStateException(
                    f"Module {release} is {status.value}, expected STOPED"
                )

            logger.info(f"Starting module: {release}")
            DebugMode.log_event("module", "Starting module", release=release, args=args)
            module.start(args)
            self._poll_until_status(module, StatusInstall.STARTED)
            logger.info(f"Module started: {release}")

    def stop(self, release: str):
        """Stop a running module."""
        with self._lock:
            module = self._get_module(release)

            status = module.get_status()
            if status != StatusInstall.STARTED:
                raise ModuleIllegalStateException(
                    f"Module {release} is {status.value}, expected STARTED"
                )

            DebugMode.log_event("module", "Stopping module", release=release)
            module.stop()
            self._poll_until_status(module, StatusInstall.STOPED)
            logger.info(f"Module stopped: {release}")

    def delete(self, release: str):
        """Uninstall and delete a module."""
        with self._lock:
            module = self._get_module(release)
            DebugMode.log_event("module", "Deleting module", release=release)
            module.uninstall()
            self._repository.delete(release)
            logger.info(f"Module deleted: {release}")

    def check(self, release: str) -> Module:
        """Get a module with current status."""
        return self._get_module(release)

    def get_all(self) -> list[Module]:
        """List all modules with status."""
        configs = self._repository.get_all()
        return [Module(self._install4j_utils, config) for config in configs]

    def _poll_until_status(self, module: Module, expected: StatusInstall):
        """Poll until the module reaches the expected status or times out."""
        elapsed = 0.0
        while elapsed < MODULE_POLL_TIMEOUT:
            if module.get_status() == expected:
                return
            time.sleep(MODULE_POLL_INTERVAL)
            elapsed += MODULE_POLL_INTERVAL
        logger.warning(
            f"Timeout waiting for module {module.get_release_module()} "
            f"to reach status {expected.value}"
        )
