"""Enumeration for module installation status."""

from enum import Enum


class StatusInstall(Enum):
    STARTED = "STARTED"
    STOPED = "STOPED"
    UNKNOWN = "UNKNOWN"
