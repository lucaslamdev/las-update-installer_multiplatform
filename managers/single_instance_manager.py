"""SingleInstanceManager - ensures only one instance of the application runs.

Matches Java behavior:
- Lock file name: "java.util.concurrent.locks.Lock.lock"
- Uses OS-level file locks (fcntl/msvcrt)
- Writes future timestamp (currentTimeMillis + 10000) into lock file
- Lock dir: LOCALAPPDATA/mv/las/temp on Windows, ~/.config/mv/las/temp on Linux
"""

from __future__ import annotations
import atexit
import logging
import os
import platform
import struct
import time
from typing import Optional

from config import LOCK_OFFSET_SECONDS
from utils.path_utils import get_tmp_directory_path

logger = logging.getLogger(__name__)

# Java uses: java.util.concurrent.locks.Lock.getName() + ".lock"
LOCK_FILE_NAME = "java.util.concurrent.locks.Lock.lock"


class SingleInstanceManager:
    """Manages single-instance behavior using OS file locks.

    Java uses RandomAccessFile + FileChannel.tryLock() for atomic file locking.
    Python uses msvcrt.locking (Windows) or fcntl.flock (Linux).
    """

    def __init__(self):
        self._lock_path: Optional[str] = None
        self._lock_fd = None
        self._locked = False
        self._another_instance = False
        self._setup()

    def _setup(self):
        """Attempt to acquire the lock on startup (matches Java constructor)."""
        lock_dir = get_tmp_directory_path()
        self._lock_path = os.path.join(lock_dir, LOCK_FILE_NAME)

        try:
            # Try to acquire exclusive file lock
            fd = os.open(self._lock_path, os.O_RDWR | os.O_CREAT, 0o644)

            locked = False
            if platform.system() == "Windows":
                try:
                    import msvcrt
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    locked = True
                except OSError:
                    pass
            else:
                try:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    locked = True
                except OSError:
                    pass

            if locked:
                # Write future timestamp (currentTimeMillis + 10000) as Java does
                future_time = int(time.time() * 1000) + (LOCK_OFFSET_SECONDS * 1000)
                os.lseek(fd, 0, os.SEEK_SET)
                os.truncate(fd, 0)
                os.write(fd, str(future_time).encode("utf-8"))
                self._lock_fd = fd
                self._locked = True
                logger.info("First instance - lock acquired")
                atexit.register(self.unlock_file)
            else:
                # Another instance is running - read the timestamp
                os.close(fd)
                self._another_instance = True
                logger.info("Another instance is running")

        except Exception as e:
            logger.warning(f"Lock file error: {e}")
            self._another_instance = False

    def is_another_instance_running(self) -> bool:
        """Returns True if another instance is already running."""
        return self._another_instance

    def unlock_file(self):
        """Release the file lock and delete the lock file."""
        if self._locked:
            try:
                if self._lock_fd is not None:
                    if platform.system() == "Windows":
                        import msvcrt
                        os.lseek(self._lock_fd, 0, os.SEEK_SET)
                        msvcrt.locking(self._lock_fd, msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                    os.close(self._lock_fd)
                    self._lock_fd = None

                if self._lock_path and os.path.exists(self._lock_path):
                    os.remove(self._lock_path)

                self._locked = False
                logger.info("Lock file released")
            except OSError as e:
                logger.warning(f"Error releasing lock file: {e}")
