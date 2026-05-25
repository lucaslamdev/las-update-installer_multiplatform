"""Windows protocol handler registration for mvupdate:// URI schema.

Registers the mvupdate:// custom URI scheme in the Windows registry so that
browsers can launch this application when a mvupdate: link is clicked.
Equivalent to what install4j does automatically for Java apps.
"""

import logging
import os
import sys

logger = logging.getLogger(__name__)


def register_mvupdate_protocol():
    """Register the mvupdate:// protocol handler in the Windows registry."""
    if sys.platform != "win32":
        logger.info("Protocol registration skipped (not Windows)")
        return

    try:
        import winreg
    except ImportError:
        logger.warning("winreg not available, cannot register protocol")
        return

    # Get the python executable and script path
    python_exe = sys.executable
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app.py"))

    # Build the command: python app.py with the URI passed as argument
    # Windows passes the URI as %1
    command = f'"{python_exe}" "{script_path}" "%1"'

    protocol_key_name = "mvupdate"

    try:
        # Create/open the protocol key
        key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, protocol_key_name)
        winreg.SetValue(key, "", winreg.REG_SZ, 'URL:mvupdate Protocol')
        winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")

        # Set up the shell open command
        shell_key = winreg.CreateKey(key, r"shell\open\command")
        winreg.SetValue(shell_key, "", winreg.REG_SZ, command)

        winreg.CloseKey(shell_key)
        winreg.CloseKey(key)

        logger.info(f"Registered mvupdate:// protocol -> {command}")
    except PermissionError:
        logger.warning("Permission denied registering mvupdate:// protocol (run as administrator)")
    except Exception as e:
        logger.warning(f"Failed to register mvupdate:// protocol: {e}")


def unregister_mvupdate_protocol():
    """Remove the mvupdate:// protocol handler from the Windows registry."""
    if sys.platform != "win32":
        return

    try:
        import winreg
    except ImportError:
        return

    try:
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, r"mvupdate\shell\open\command")
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, r"mvupdate\shell\open")
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, r"mvupdate\shell")
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, "mvupdate")
        logger.info("Unregistered mvupdate:// protocol")
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.warning(f"Failed to unregister mvupdate:// protocol: {e}")
