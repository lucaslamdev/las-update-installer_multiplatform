"""Install4j utilities for managing module installations.

Executes install4j-packaged installers/uninstallers as OS processes.
Matches Java GenericInstall4jUtils behavior exactly.
"""

from __future__ import annotations
import logging
import os
import platform
import subprocess
from typing import Optional

from models import InstallException
from models.module_config import ModuleConfig
from utils.debug_mode import DebugMode

logger = logging.getLogger(__name__)


class Install4jUtils:
    """Interface for install4j operations."""

    def install(self, config: ModuleConfig):
        raise NotImplementedError

    def uninstall(self, config: ModuleConfig):
        raise NotImplementedError

    def start(self, config: ModuleConfig, extra_args: Optional[list[str]] = None):
        raise NotImplementedError


class GenericInstall4jUtils(Install4jUtils):
    """Executes install4j installer/uninstaller executables as OS processes.

    Java behavior:
    - install: runs installer with -q -dir "<installDir>", waits for completion
    - uninstall: runs uninstaller with -q, waits for completion
    - start: runs executable with -J-Ddiscovery.server.url/token JVM args, detached
    - Checks exit codes, throws InstallException on failure
    """

    def install(self, config: ModuleConfig):
        """Run the module installer with -q -dir arguments, waits for completion."""
        installer = config.module_installer_file
        install_dir = config.module_installer_dir

        if not installer or not os.path.exists(installer):
            raise InstallException(f"Installer not found: {installer}")

        logger.info(f"Installing module: {config.release_module} from {installer}")
        DebugMode.log_install4j(
            "install", config.release_module, installer, ["-q", "-dir", install_dir], wait=True
        )
        self._execute_process(
            installer, install_dir,
            wait=True,
            args=["-q", "-dir", install_dir],
        )

    def uninstall(self, config: ModuleConfig):
        """Run the module uninstaller with -q argument, waits for completion."""
        uninstaller = config.module_uninstaller_file
        install_dir = config.module_installer_dir

        if not uninstaller or not os.path.exists(uninstaller):
            raise InstallException(f"Uninstaller not found: {uninstaller}")

        logger.info(f"Uninstalling module: {config.release_module} using {uninstaller}")
        DebugMode.log_install4j(
            "uninstall", config.release_module, uninstaller, ["-q"], wait=True
        )
        self._execute_process(
            uninstaller, install_dir,
            wait=True,
            args=["-q"],
        )

    def start(self, config: ModuleConfig, extra_args: Optional[list[str]] = None):
        """Start the module executable with discovery JVM args, detached."""
        executable = config.module_executable_file
        install_dir = config.module_installer_dir

        if not executable or not os.path.exists(executable):
            raise InstallException(f"Executable not found: {executable}")

        # Build JVM args from server config
        args = []
        from repositories.server_config_repository import ServerConfigRepositoryProperties
        server_config_repo = ServerConfigRepositoryProperties()
        server_config = server_config_repo.get_current_server_config()
        if server_config:
            args.append(f"-J-Ddiscovery.server.url={server_config.url}")
            args.append(f"-J-Ddiscovery.server.token={server_config.token}")
        if extra_args:
            args.extend(extra_args)

        logger.info(f"Starting module: {config.release_module} - {executable}")
        DebugMode.log_install4j(
            "start", config.release_module, executable, args, wait=False
        )
        self._execute_process(
            executable, install_dir,
            wait=False,
            args=args,
        )

    def _execute_process(
        self,
        executable: str,
        working_dir: str,
        wait: bool,
        args: Optional[list[str]] = None,
    ):
        """Execute a command as a subprocess.

        Matches Java's executeProcess:
        - Sets working directory
        - Merges stderr into stdout (redirectErrorStream)
        - If wait=True, waits for exit and checks code
        - Throws InstallException on failure
        """
        cmd_args = args or []
        is_windows = platform.system() == "Windows"
        command = [executable] + cmd_args

        stdout = subprocess.PIPE if wait else subprocess.DEVNULL
        stderr = subprocess.STDOUT if wait else subprocess.DEVNULL

        try:
            proc = subprocess.Popen(
                command,
                stdout=stdout,
                stderr=stderr,
                cwd=working_dir if os.path.isdir(working_dir) else None,
                creationflags=(
                    subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                    if is_windows else 0
                ) if not wait else 0,
                close_fds=not wait,
            )

            if wait:
                output = proc.communicate()[0]
                if proc.returncode != 0:
                    output_str = output.decode("utf-8", errors="replace") if output else ""
                    raise InstallException(
                        f"Process failed with exit code {proc.returncode}: {output_str}"
                    )
            else:
                # Detached process on non-blocking start
                if not is_windows:
                    pass  # Already detached via creationflags

        except InstallException:
            raise
        except Exception as e:
            logger.error(f"Failed to execute command {executable}: {e}")
            raise InstallException(f"Failed to execute command: {e}") from e
