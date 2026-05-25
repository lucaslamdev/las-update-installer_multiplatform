"""Hostname resolution utility with multiple strategy fallbacks."""

import logging
import os
import platform
import socket
from typing import Optional

logger = logging.getLogger(__name__)


def get_hostname() -> str:
    """Get the hostname using a chain of strategies.

    Strategy order:
    1. Terminal Services CLIENTNAME environment variable
    2. XenDesktop registry client name (Windows only)
    3. InetAddress localhost hostname
    """
    hostname = _try_terminal_service()
    if hostname:
        return hostname

    hostname = _try_xen_desktop()
    if hostname:
        return hostname

    return _try_inet_address()


def _try_terminal_service() -> Optional[str]:
    """Try to get hostname from Terminal Services CLIENTNAME env var."""
    return os.environ.get("CLIENTNAME")


def _try_xen_desktop() -> Optional[str]:
    """Try to get hostname from XenDesktop registry (Windows only)."""
    if platform.system() != "Windows":
        return None

    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Policies\Citrix\1\Evidence",
            0,
            winreg.KEY_READ,
        )
        value, _ = winreg.QueryValueEx(key, "Clientname")
        winreg.CloseKey(key)
        return value
    except (OSError, ImportError):
        return None


def _try_inet_address() -> str:
    """Fallback: get hostname via socket."""
    try:
        return socket.gethostname()
    except Exception:
        return "localhost"
