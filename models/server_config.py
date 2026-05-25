"""ServerConfig model for server connection configuration."""

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class ServerConfig:
    """Holds the server URL and authentication token."""
    url: str
    token: str
