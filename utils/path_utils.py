"""Platform-specific path utilities."""

from __future__ import annotations
import os
import platform


def get_tmp_directory_path() -> str:
    """Get temp directory matching Java's SingleInstanceManager.getTmpDirectoryPath()."""
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA", "")
        if not base:
            base = os.path.join(os.path.expanduser("~"), "AppData", "Local")
        tmp_dir = os.path.join(base, "mv", "las", "temp")
    else:
        home = os.path.expanduser("~")
        tmp_dir = os.path.join(home, ".config", "mv", "las", "temp")
    os.makedirs(tmp_dir, exist_ok=True)
    return tmp_dir
