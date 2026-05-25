"""ServerConfig repository - persists server configuration to properties file.

Uses the same temp directory as Java: LOCALAPPDATA/mv/las/temp on Windows,
~/.config/mv/las/temp on Linux.
"""

from __future__ import annotations
import logging
import os
from typing import Optional

from models.server_config import ServerConfig
from utils.path_utils import get_tmp_directory_path

logger = logging.getLogger(__name__)


class ServerConfigRepository:
    """Interface for server config data access."""

    def get_current_server_config(self) -> Optional[ServerConfig]:
        raise NotImplementedError

    def set_current_server_config(self, config: ServerConfig):
        raise NotImplementedError


class ServerConfigRepositoryProperties(ServerConfigRepository):
    """Persists ServerConfig to a properties file."""

    def __init__(self):
        self._file_path = os.path.join(get_tmp_directory_path(), "serverConfig.properties")

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
