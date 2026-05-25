"""System utilities for OS detection."""

import platform


IS_OS_WINDOWS = platform.system() == "Windows"
IS_OS_LINUX = platform.system() == "Linux"
