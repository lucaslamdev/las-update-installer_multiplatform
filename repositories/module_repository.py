"""Module repository - filesystem-based module storage.

Matches Java ModuleRepositoryImpl behavior:
- create() saves uploaded file without extension, then calls setExecutable(true)
- get() always returns a ModuleConfig (never None) via builderModuleConfig
- delete() uses recursive directory delete
- getAll() walks directory tree looking for *-install.properties files
"""

from __future__ import annotations
import logging
import os
import platform
import shutil
import stat
from typing import Optional

from models.module_config import ModuleConfig, get_mvupdate_home

logger = logging.getLogger(__name__)


class ModuleRepository:
    """Interface for module data access."""

    def create(self, release: str, input_stream) -> ModuleConfig:
        raise NotImplementedError

    def delete(self, release: str):
        raise NotImplementedError

    def get(self, release: str) -> Optional[ModuleConfig]:
        raise NotImplementedError

    def get_all(self) -> list[ModuleConfig]:
        raise NotImplementedError


class ModuleRepositoryImpl(ModuleRepository):
    """Filesystem-based module repository."""

    def __init__(self):
        self._home = get_mvupdate_home()

    def _builder_module_config(self, release: str) -> ModuleConfig:
        """Build a ModuleConfig from release name (matches Java builderModuleConfig)."""
        module_dir = os.path.join(self._home, release)
        install_props = os.path.join(module_dir, f"{release}-install.properties")
        if os.path.exists(install_props):
            return ModuleConfig.from_install_properties(release, install_props)
        return ModuleConfig(release_module=release)

    def create(self, release: str, input_stream) -> ModuleConfig:
        """Save the uploaded installer file and create a module config.

        Java behavior: Files.copy with REPLACE_EXISTING, then setExecutable(true).
        """
        module_dir = os.path.join(self._home, release)
        os.makedirs(module_dir, exist_ok=True)

        # Java does NOT use platform extension - uses raw release name
        installer_file = os.path.join(module_dir, release)

        # Write the uploaded file
        with open(installer_file, "wb") as f:
            if hasattr(input_stream, "read"):
                data = input_stream.read()
                if isinstance(data, str):
                    data = data.encode("utf-8")
                f.write(data)
            else:
                f.write(
                    input_stream
                    if isinstance(input_stream, bytes)
                    else input_stream.encode("utf-8")
                )

        # Java calls setExecutable(true) on the installer file
        try:
            os.chmod(installer_file, os.stat(installer_file).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except OSError:
            pass

        logger.info(f"Created module installer: {installer_file}")
        return self._builder_module_config(release)

    def delete(self, release: str) -> ModuleConfig:
        """Delete a module's directory. Returns ModuleConfig (matches Java)."""
        config = self._builder_module_config(release)
        module_dir = os.path.join(self._home, release)
        if os.path.isdir(module_dir):
            shutil.rmtree(module_dir, ignore_errors=True)
            logger.info(f"Deleted module directory: {module_dir}")
        return config

    def get(self, release: str) -> ModuleConfig:
        """Get a module config by release name.

        Java always returns a ModuleConfig (never null) via builderModuleConfig.
        """
        return self._builder_module_config(release)

    def get_all(self) -> list[ModuleConfig]:
        """List all installed modules.

        Java walks directory tree looking for *-install.properties files,
        then builds config for each, filtering where exist() is true.
        """
        modules = []
        if not os.path.isdir(self._home):
            return modules

        for entry in os.listdir(self._home):
            module_dir = os.path.join(self._home, entry)
            if os.path.isdir(module_dir):
                config = self._builder_module_config(entry)
                if config.exists():
                    modules.append(config)

        return modules
