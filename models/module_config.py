"""ModuleConfig model for module file paths and configuration."""

from __future__ import annotations
import os
import platform
from dataclasses import dataclass, field
from typing import Optional


def get_mvupdate_home() -> str:
    """Get the MVUPDATE_HOME directory path."""
    if platform.system() == "Windows":
        return os.path.join(os.environ.get("LOCALAPPDATA", ""), "mv", "las")
    else:
        return os.path.join(os.path.expanduser("~"), ".local", "share", "mv", "las")


@dataclass
class ModuleConfig:
    """Configuration for a module's installation paths."""
    release_module: str
    module_installer_file: str = ""
    module_installer_dir: str = ""
    module_install_file: str = ""
    module_executable_file: str = ""
    module_uninstaller_file: str = ""

    def __post_init__(self):
        if not self.module_installer_dir:
            self._resolve_paths()

    def _resolve_paths(self):
        """Resolve all file paths from the release module name."""
        home = get_mvupdate_home()
        self.module_installer_dir = os.path.join(home, self.release_module)
        self.module_install_file = os.path.join(self.module_installer_dir, f"{self.release_module}-install.properties")

        is_windows = platform.system() == "Windows"
        ext = ".exe" if is_windows else ".sh"
        self.module_installer_file = os.path.join(
            self.module_installer_dir, f"{self.release_module}-install{ext}"
        )

        if os.path.exists(self.module_install_file):
            self._load_install_properties()

    def _load_install_properties(self):
        """Load installation directory properties from the install properties file."""
        props = {}
        with open(self.module_install_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    props[key.strip()] = value.strip()

        installation_dir = props.get("installation.dir", "")
        execute_file = props.get("execute.file", "")
        uninstall_file = props.get("uninstall.file", "")

        if installation_dir:
            self.module_installer_dir = installation_dir
        if installation_dir and execute_file:
            self.module_executable_file = os.path.join(installation_dir, execute_file)
        if installation_dir and uninstall_file:
            self.module_uninstaller_file = os.path.join(installation_dir, uninstall_file)

    def exists(self) -> bool:
        """Check if the module executable file exists (matches Java: moduleExecutableFile != null && exists)."""
        return bool(self.module_executable_file) and os.path.isfile(self.module_executable_file)

    @classmethod
    def from_install_properties(cls, release_module: str, install_properties_path: str) -> ModuleConfig:
        """Create a ModuleConfig by reading an install properties file."""
        config = cls(release_module=release_module)
        config.module_install_file = install_properties_path
        config._load_install_properties()
        return config
