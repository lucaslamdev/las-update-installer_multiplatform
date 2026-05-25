"""ServerConfig repository - persists server configuration to properties file.

Uses the same temp directory as Java: LOCALAPPDATA/mv/las/temp on Windows,
~/.config/mv/las/temp on Linux.
"""

from __future__ import annotations
import logging
import os
import platform
from typing import Optional

from models.server_config import ServerConfig

logger = logging.getLogger(__name__)


def _get_config_dir() -> str:
    """Get the config directory matching Java's SingleInstanceManager.getTmpDirectoryPath()."""
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA", "")
        if not base:
            base = os.path.join(os.path.expanduser("~"), "AppData", "Local")
        config_dir = os.path.join(base, "mv", "las", "temp")
    else:
        home = os.environ.get("user.home", os.path.expanduser("~"))
        config_dir = os.path.join(home, ".config", "mv", "las", "temp")
    os.makedirs(config_dir, exist_ok=True)
    return config_dir


class ServerConfigRepository:
    """Interface for server config data access."""

    def get_current_server_config(self) -> Optional[ServerConfig]:
        raise NotImplementedError

    def set_current_server_config(self, config: ServerConfig):
        raise NotImplementedError


class ServerConfigRepositoryProperties(ServerConfigRepository):
    """Persists ServerConfig to a properties file."""

    def __init__(self):
        self._file_path = os.path.join(_get_config_dir(), "serverConfig.properties")

    def get_current_server_config(self) -> Optional[ServerConfig]:
        if not os.path.exists(self._file_path):
            return None

        try:
            props = {}
            with open(self._file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        props[key.strip()] = value.strip()

            url = props.get("discovery.server.url", "")
            token = props.get("discovery.server.key", "")

            if not url:
                return None

            return ServerConfig(url=url, token=token)
        except Exception as e:
            logger.error(f"Failed to read server config: {e}")
            return None

    def set_current_server_config(self, config: ServerConfig):
        try:
            with open(self._file_path, "w", encoding="utf-8") as f:
                f.write(f"discovery.server.key={config.token}\n")
                f.write(f"discovery.server.url={config.url}\n")
            logger.info(f"Saved server config: url={config.url}")
        except Exception as e:
            logger.error(f"Failed to write server config: {e}")
