"""Module model representing an installable software module."""

from __future__ import annotations
import json
import logging
from typing import Optional

import requests

from models.enums import StatusInstall
from models.instance_info import InstanceInfo
from models.module_config import ModuleConfig
from utils.install4j_utils import Install4jUtils

logger = logging.getLogger(__name__)


class Module:
    """Represents a software module that can be installed, started, and stopped."""

    def __init__(self, install4j_utils: Install4jUtils, module_config: ModuleConfig):
        self._install4j_utils = install4j_utils
        self._module_config = module_config

    @property
    def module_config(self) -> ModuleConfig:
        return self._module_config

    def exists(self) -> bool:
        return self._module_config.exists()

    def get_release_module(self) -> str:
        return self._module_config.release_module

    def get_token(self) -> Optional[str]:
        """Get the instance ID (token) from discovery."""
        from managers.discovery_manager import DiscoveryManagerImpl
        dm = DiscoveryManagerImpl.get_instance()
        info = dm.find_first_by_release(self._module_config.release_module)
        return info.instance_id if info else None

    def get_status(self) -> StatusInstall:
        """Get the current status of this module."""
        if not self.exists():
            return StatusInstall.UNKNOWN

        if self._is_started():
            return StatusInstall.STARTED
        return StatusInstall.STOPED

    def _is_started(self) -> bool:
        """Check if the module has a registered discovery instance."""
        from managers.discovery_manager import DiscoveryManagerImpl
        dm = DiscoveryManagerImpl.get_instance()
        return dm.find_first_by_release(self._module_config.release_module) is not None

    def is_started(self) -> bool:
        return self._is_started()

    def get_internal_url(self, path: Optional[str] = None) -> Optional[str]:
        """Build the internal URL for this module."""
        from managers.discovery_manager import DiscoveryManagerImpl
        dm = DiscoveryManagerImpl.get_instance()
        info = dm.find_first_by_release(self._module_config.release_module)
        if info is not None:
            if path is not None:
                return f"{info.url}/{path}"
            return info.url
        return None

    def get_url(self) -> Optional[str]:
        """Get the module URL if started, None otherwise."""
        if self.get_status() == StatusInstall.STARTED:
            return self.get_internal_url(None)
        return None

    def start(self):
        """Start this module via install4j."""
        self._install4j_utils.start(self._module_config)

    def stop(self):
        """Stop this module by sending a shutdown request."""
        url = self.get_internal_url("shutdown")
        if url:
            try:
                requests.post(url, timeout=5)
            except requests.RequestException as e:
                logger.warning(f"Error stopping module {self._module_config.release_module}: {e}")

    def install(self):
        """Install this module via install4j."""
        self._install4j_utils.install(self._module_config)

    def uninstall(self):
        """Uninstall this module via install4j."""
        self._install4j_utils.uninstall(self._module_config)
