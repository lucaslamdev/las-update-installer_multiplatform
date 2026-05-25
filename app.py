"""LAS Update Installer - Main application entry point.

Equivalent to br.com.mv.mvupdate.App (Java)

This is a module management server that:
- Installs, starts, stops, and deletes software modules
- Registers instances with a discovery server
- Enforces single-instance behavior
- Handles URI schema connections
"""

import logging
import socket
import sys
import threading
import time
import uuid
from typing import Optional

from config import BUILD_NAME, BUILD_VERSION, PORT_MIN, PORT_MAX, LOCALHOST, AUTH_TOKEN_PREFIX
from environment import EnvironmentConfiguration, ApplicationEnvPropertySource
from utils.log_utils import product_logger
from managers.single_instance_manager import SingleInstanceManager
from models.mvupdate_key import MvupdateKey
from models.server_config import ServerConfig
from models.uri_schema import UriSchemaConnect
from repositories.mvupdate_key_repository import MvupdateKeyRepositoryImpl
from repositories.server_config_repository import ServerConfigRepositoryProperties
from server.app_server import AppServer
from server.handlers import register_handlers
from utils.port_finder import find_available_port
from utils.protocol_registry import register_mvupdate_protocol
from utils.debug_mode import DebugMode, init_debug_from_argv

logger = logging.getLogger(__name__)


class LasUpdateInstaller(AppServer):
    """Main application server for the LAS Update Installer."""

    def __init__(self, port: int, enable_shutdown: bool = True):
        super().__init__(port, enable_shutdown)
        register_handlers(self)


class MVUpdateClient:
    """Client for connecting to a running update server (matches Java MVUpdateClient)."""

    def __init__(self, server_config: ServerConfig):
        self._server_config = server_config

    def connect(self, key: MvupdateKey):
        """Connect to the server with the given key."""
        import requests
        url = f"{self._server_config.url}/connect"
        headers = {
            "Content-Type": "application/json",
            "Authentication": f"{AUTH_TOKEN_PREFIX}{self._server_config.token}",
        }
        body = key.to_dict()
        started = time.time()
        response = None
        try:
            response = requests.post(url, json=body, headers=headers, timeout=10)
            DebugMode.log_http_outbound(
                method="POST",
                url=url,
                request_headers=headers,
                request_body=body,
                status_code=response.status_code,
                response_body=response.text,
                duration_ms=(time.time() - started) * 1000,
            )
            response.raise_for_status()
        except Exception as e:
            if response is None:
                DebugMode.log_http_outbound(
                    method="POST",
                    url=url,
                    request_headers=headers,
                    request_body=body,
                    status_code=None,
                    response_body=None,
                    duration_ms=(time.time() - started) * 1000,
                    error=str(e),
                )
            logger.error(f"Failed to connect to server: {e}")
            raise


def connect_server(key: Optional[MvupdateKey]):
    """Connect to an already running server instance (matches Java connectServer)."""
    start_time = time.time()
    logger.info("Another Instance Running")

    if key:
        server_config_repo = ServerConfigRepositoryProperties()
        server_config = server_config_repo.get_current_server_config()
        if server_config:
            client = MVUpdateClient(server_config)
            client.connect(key)

    elapsed_ms = (time.time() - start_time) * 1000
    logger.info(f"Finish [{elapsed_ms:.0f}] milliseconds")


def start_server(key: Optional[MvupdateKey]):
    """Start the server (first instance, matches Java startServer)."""
    env = EnvironmentConfiguration.get_environment()

    # Store the mvupdate key if present
    if key:
        key_repo = MvupdateKeyRepositoryImpl()
        key_repo.add_instance(key)

    start_time = time.time()

    # Find available port (matches Java AppServer.getServerPort)
    port = find_available_port(PORT_MIN, PORT_MAX)
    if port is None:
        logger.error("No available port found in range")
        sys.exit(1)

    logger.info(f"Starting server port \"{port}\"")

    # Create the server (matches Java new App(port, true))
    app = LasUpdateInstaller(port, enable_shutdown=True)

    # Generate or load server token
    token = env.get_property("discovery.server.token")
    if not token or token.strip() == "":
        token = str(uuid.uuid4())

    # Save server config (matches Java ServerConfigRepositoryProperties)
    server_config_repo = ServerConfigRepositoryProperties()
    server_config = ServerConfig(
        url=f"http://{LOCALHOST}:{port}",
        token=token,
    )
    server_config_repo.set_current_server_config(server_config)

    elapsed_ms = (time.time() - start_time) * 1000
    logger.info(f"Started [{elapsed_ms:.0f}] milliseconds port \"{port}\"")
    DebugMode.log_event(
        "server",
        "HTTP server starting",
        port=port,
        url=server_config.url,
        debug_dir=DebugMode.get_base_dir() if DebugMode.is_enabled() else None,
    )

    server_thread = threading.Thread(target=app.start, name="http-server")
    server_thread.start()
    _wait_until_server_listening(port)

    from discovery.discovery_client import DiscoveryClient, DiscoveryServerConfig

    if DiscoveryServerConfig().is_configured():
        try:
            DiscoveryClient(port=port).start()
        except Exception as e:
            logger.error(f"Discovery client failed to start: {e}")

    server_thread.join()


def _wait_until_server_listening(port: int, timeout: float = 10.0):
    """Wait until the HTTP server accepts connections on the given port."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((LOCALHOST, port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.05)
    raise TimeoutError(f"Server did not start listening on port {port} within {timeout}s")


def main():
    """Application entry point (matches Java App.main)."""
    sys.argv = init_debug_from_argv(sys.argv)

    # Setup logging
    try:
        product_logger()
    except Exception:
        logging.basicConfig(level=logging.INFO)
        print("[Error] - Not found logging.properties", file=sys.stderr)
        sys.exit(-1)

    if DebugMode.is_enabled():
        DebugMode.configure_logging()
        DebugMode.log_event("startup", "Application started in debug mode")

    # Register mvupdate:// protocol in Windows registry
    register_mvupdate_protocol()

    # Check if launched via URI schema (browser passes URI as command line arg)
    uri_args = [arg for arg in sys.argv[1:] if arg.startswith("mvupdate:")]
    if uri_args:
        uri_arg = uri_args[0]
        logger.info(f"Launched via URI schema: {uri_arg}")
        ApplicationEnvPropertySource().set_property("uriSchema", uri_arg)
        DebugMode.log_event("startup", "Launched via URI schema", uri=uri_arg)

    # Single instance check (matches Java SingleInstanceManager in constructor)
    instance_manager = SingleInstanceManager()

    # Load environment
    env = EnvironmentConfiguration.get_environment()
    uri_schema = env.get_property("uriSchema")
    logger.info(f"uriSchema=[{uri_schema}]")

    # Parse URI schema key
    key: Optional[MvupdateKey] = None
    if uri_schema:
        try:
            connect = UriSchemaConnect(uri_schema)
            key = connect.get_mvupdate_key()
        except Exception as e:
            logger.error(f"error uriSchema: {e}")

    # Check for another running instance
    if instance_manager.is_another_instance_running():
        connect_server(key)
    else:
        start_server(key)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        print("\nPressione Enter para fechar...")
        input()
        sys.exit(1)
