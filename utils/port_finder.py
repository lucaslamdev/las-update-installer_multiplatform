"""Port finder utility for finding available ports in a range."""

import socket
from typing import Optional

from config import PORT_MIN, PORT_MAX


def find_available_port(port_min: int = PORT_MIN, port_max: int = PORT_MAX) -> Optional[int]:
    """Find an available port in the given range."""
    for port in range(port_min, port_max + 1):
        if _is_port_available(port):
            return port
    return None


def _is_port_available(port: int) -> bool:
    """Check if a port is available for binding."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", port))
            return True
    except OSError:
        return False
