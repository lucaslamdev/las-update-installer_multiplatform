"""Application configuration and constants."""

# Build info
BUILD_NAME = "las-update-installer"
BUILD_DESCRIPTION = "update module in las"
BUILD_VERSION = "2.2.6"

# Port range for the server
PORT_MIN = 32768
PORT_MAX = 32818

# Discovery TTL (seconds)
DISCOVERY_TTL = 30

# Mvupdate key TTL (seconds) - 8 hours
MVUPDATE_KEY_TTL = 8 * 60 * 60

# Heartbeat interval (seconds)
HEARTBEAT_INTERVAL = 10

# Module start/stop polling timeout (seconds)
MODULE_POLL_TIMEOUT = 30
MODULE_POLL_INTERVAL = 0.1

# Authentication header
AUTH_HEADER = "Authentication"
AUTH_TOKEN_PREFIX = "TOKEN"

# Lock file check offset (seconds)
LOCK_OFFSET_SECONDS = 10

# Temp file cleanup delay (seconds)
TEMP_FILE_CLEANUP_DELAY = 5

# Default local address
LOCALHOST = "127.0.0.1"
