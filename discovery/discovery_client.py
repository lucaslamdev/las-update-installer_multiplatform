"""Discovery client for registering with and sending heartbeats to a remote discovery server.

Matches Java DiscoveryClient behavior:
- Constructor takes Environment, creates DiscoveryServerConfig and ServerInfo internally
- Generates UUID instanceId and stores in ApplicationEnvPropertySource
- start() calls registry() first, then starts daemon heartbeat thread
- registry() checks for 202 ACCEPTED response
- sendHeartBeat() checks for 200 OK response
- unregistry() checks for 200 OK response
- Validates discovery server config (throws on missing url/token)
"""

from __future__ import annotations
import json
import logging
import os
import threading
import time
import uuid
from typing import Optional, Any

import requests

from config import AUTH_TOKEN_PREFIX, HEARTBEAT_INTERVAL, LOCALHOST
from environment import EnvironmentConfiguration, ApplicationEnvPropertySource
from models.dto import ServerInfo
from models.instance_info import InstanceInfo
from models.server_config import ServerConfig
from utils.debug_mode import DebugMode

logger = logging.getLogger(__name__)


def _log_outbound(method: str, url: str, headers: dict, body: Any, response: Optional[requests.Response], started: float, error: Optional[str] = None):
    try:
        duration_ms = (time.time() - started) * 1000
        status = response.status_code if response is not None else None
        resp_body = None
        if response is not None:
            try:
                resp_body = response.text
            except Exception:
                resp_body = None
        DebugMode.log_http_outbound(
            method=method,
            url=url,
            request_headers=headers,
            request_body=body,
            status_code=status,
            response_body=resp_body,
            duration_ms=duration_ms,
            error=error,
        )
    except Exception as e:
        logger.warning("Debug outbound logging failed: %s", e)


class DiscoveryServerConfig:
    """Configuration for connecting to a remote discovery server.

    Java throws IllegalArgumentException if url or token is null/empty.
    """

    def __init__(self):
        env = EnvironmentConfiguration.get_environment()
        self.url = env.get_property("discovery.server.url", "")
        self.token = env.get_property("discovery.server.token", "")

        # Ensure trailing slash on URL (Java appends "/" if missing)
        if self.url and not self.url.endswith("/"):
            self.url = self.url + "/"

    def is_configured(self) -> bool:
        return bool(self.url and self.token)

    def get_server_url(self, path: str):
        """Build full URL from server base URL + path."""
        return f"{self.url}{path}"

    def get_header_authentication(self) -> str:
        """Build authentication header value."""
        return f"{AUTH_TOKEN_PREFIX}{self.token}"


class DiscoveryClient:
    """Client for communicating with a remote discovery server.

    Matches Java: constructed from Environment, generates instanceId,
    start() calls registry() then starts heartbeat.
    """

    def __init__(self, env=None, port: int = 0):
        """Initialize from Environment (matches Java constructor)."""
        if env is None:
            env = EnvironmentConfiguration.get_environment()

        self._discovery_server = DiscoveryServerConfig()
        self._self = ServerInfo.from_environment(env, port=port)
        self._instance_id = str(uuid.uuid4())

        # Store instanceId in ApplicationEnvPropertySource (Java does this)
        app_env = ApplicationEnvPropertySource()
        app_env.set_property("instanceId", self._instance_id)

    @property
    def instance_id(self) -> str:
        return self._instance_id

    def _auth_header(self) -> dict[str, str]:
        return {"Authentication": self._discovery_server.get_header_authentication()}

    def start(self):
        """Register and start heartbeat (matches Java start())."""
        self.registry()
        thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
            name="discovery-heartBeat",
        )
        # Java sets priority 10 (max normal), not directly replicable in Python
        thread.start()

    def registry(self):
        """Register this instance with the discovery server.

        Java checks for 202 ACCEPTED response code.
        """
        if not self._discovery_server.is_configured():
            logger.warning("Discovery server not configured, skipping registry")
            return

        payload = {
            "instanceId": self._instance_id,
            "release": self._self.release,
            "url": self._self.url,
        }

        url = self._discovery_server.get_server_url(f"discovery/{self._self.release}")
        logger.info(f"connect to server discovery url {url}")

        headers = {"Content-Type": "application/json", **self._auth_header()}
        started = time.time()
        response = None
        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=10,
            )
            _log_outbound("POST", url, headers, payload, response, started)
            # Java checks response == 202
            if response.status_code != 202:
                raise Exception(f"Registry failed with status {response.status_code}")
            logger.info(f"Registered with discovery server: {self._self.release}")
        except Exception as e:
            if response is None:
                _log_outbound("POST", url, headers, payload, None, started, error=str(e))
            logger.error(f"Failed to register with discovery server: {e}")
            raise

    def unregistry(self):
        """Unregister this instance from the discovery server.

        Java checks for 200 OK response.
        """
        if not self._discovery_server.is_configured():
            return

        url = self._discovery_server.get_server_url(
            f"discovery/{self._self.release}/{self._instance_id}"
        )
        headers = self._auth_header()
        started = time.time()
        response = None
        try:
            response = requests.delete(url, headers=headers, timeout=10)
            _log_outbound("DELETE", url, headers, None, response, started)
            if response.status_code != 200:
                raise Exception(f"Unregistry failed with status {response.status_code}")
            logger.info(f"Unregistered from discovery server: {self._self.release}")
        except Exception as e:
            if response is None:
                _log_outbound("DELETE", url, headers, None, None, started, error=str(e))
            logger.error(f"Failed to unregister from discovery server: {e}")
            raise

    def send_heartbeat(self):
        """Send a heartbeat to the discovery server.

        Java checks for 200 OK response.
        """
        payload = {
            "instanceId": self._instance_id,
            "release": self._self.release,
            "url": self._self.url,
        }

        url = self._discovery_server.get_server_url(f"discovery/{self._self.release}")
        headers = {"Content-Type": "application/json", **self._auth_header()}
        started = time.time()
        response = None
        try:
            response = requests.put(
                url,
                json=payload,
                headers=headers,
                timeout=10,
            )
            _log_outbound("PUT", url, headers, payload, response, started)
            if response.status_code != 200:
                raise Exception(f"Heartbeat failed with status {response.status_code}")
            logger.debug(f"Heartbeat sent: {self._self.release}")
        except Exception as e:
            if response is None:
                _log_outbound("PUT", url, headers, payload, None, started, error=str(e))
            logger.error(f"Heartbeat failed: {e}")
            raise

    def _heartbeat_loop(self):
        """Background loop matching Java DiscoveryClient$1.run()."""
        while True:
            try:
                self.send_heartbeat()
            except Exception as e:
                logger.error(
                    "error in discovery heartBeat. The process will be closed"
                )
                os._exit(1)
            time.sleep(HEARTBEAT_INTERVAL)
