"""Flask-based HTTP server with CORS support and authentication.

Matches Java AppServer behavior:
- CORS with Max-Age 151200, Allow-Credentials true, dynamic Allow-Headers
- Anti-cache headers on all responses
- TOKEN-based authentication via MvupdateKeyRepository
- Server token-based authentication for discovery
"""

from __future__ import annotations
import logging
import os
import tempfile
import threading
import time
from typing import Optional

from flask import Flask, Response, g, request, jsonify

from config import AUTH_HEADER, AUTH_TOKEN_PREFIX, TEMP_FILE_CLEANUP_DELAY, LOCALHOST
from environment import EnvironmentConfiguration
from repositories.mvupdate_key_repository import MvupdateKeyRepositoryImpl
from repositories.server_config_repository import ServerConfigRepositoryProperties

logger = logging.getLogger(__name__)

MIME_APPLICATION_JSON = "application/json"


class TempFileManager:
    """Manages temporary files for uploaded content."""

    def __init__(self):
        self._files: list[str] = []
        self._cleanup_timer: Optional[threading.Timer] = None

    def create_temp_file(self, suffix: str = ".tmp", prefix: str = "las_") -> str:
        fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
        os.close(fd)
        self._files.append(path)
        return path

    def schedule_cleanup(self):
        self._cleanup_timer = threading.Timer(TEMP_FILE_CLEANUP_DELAY, self._cleanup)
        self._cleanup_timer.daemon = True
        self._cleanup_timer.start()

    def _cleanup(self):
        for path in self._files:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass
        self._files.clear()


def _calculate_allow_headers() -> str:
    """Calculate Access-Control-Allow-Headers from environment (matches Java)."""
    env = EnvironmentConfiguration.get_environment()
    return env.get_property(
        "AccessControlAllowHeader",
        "origin,accept,content-type,authentication",
    )


class AppServer:
    """HTTP server with CORS, authentication, and route management."""

    def __init__(self, port: int, enable_shutdown: bool = True):
        self._port = port
        self._enable_shutdown = enable_shutdown
        self._app = Flask(__name__)
        self._running = False
        self._temp_file_manager = TempFileManager()
        self._allow_headers = _calculate_allow_headers()
        self._setup_cors()
        self._setup_anti_cache()
        self._setup_debug_tracing()
        self._setup_error_handlers()
        self.add_mappings()

    @property
    def port(self) -> int:
        return self._port

    @property
    def app(self) -> Flask:
        return self._app

    @property
    def enable_shutdown(self) -> bool:
        return self._enable_shutdown

    def _setup_cors(self):
        """Add CORS headers matching Java's addCORSHeaders."""

        @self._app.after_request
        def add_cors_headers(response: Response) -> Response:
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = self._allow_headers
            response.headers["Access-Control-Max-Age"] = "151200"
            return response

        @self._app.before_request
        def handle_options():
            if request.method == "OPTIONS":
                return Response(status=200)

    def _setup_anti_cache(self):
        """Add anti-caching headers matching Java's addConfigCache."""

        @self._app.after_request
        def add_no_cache_headers(response: Response) -> Response:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response

    def _setup_debug_tracing(self):
        """Log inbound HTTP requests/responses when debug mode is active."""
        from utils.debug_mode import DebugMode

        @self._app.before_request
        def debug_before_request():
            if not DebugMode.is_enabled():
                return None
            g._debug_started_at = time.time()
            parts = request.path.strip("/").split("/")
            g._debug_skip_body = (
                request.method == "POST"
                and len(parts) == 2
                and parts[0] == "modules"
            )
            return None

        @self._app.after_request
        def debug_after_request(response: Response) -> Response:
            if not DebugMode.is_enabled():
                return response

            started = getattr(g, "_debug_started_at", None)
            duration_ms = (time.time() - started) * 1000 if started else 0.0
            skip_body = getattr(g, "_debug_skip_body", False)

            if skip_body:
                req_body = {
                    "type": "multipart_or_binary",
                    "content_type": request.content_type,
                    "content_length": request.content_length,
                }
                if "file" in request.files:
                    uploaded = request.files["file"]
                    req_body["filename"] = uploaded.filename
            else:
                req_body = request.get_data(as_text=True) or None

            resp_body = response.get_data(as_text=True) or None

            DebugMode.log_http_inbound(
                method=request.method,
                path=request.path,
                query=request.query_string.decode("utf-8", errors="replace"),
                headers={k: v for k, v in request.headers.items()},
                request_body=req_body,
                status_code=response.status_code,
                response_body=resp_body,
                duration_ms=duration_ms,
            )
            return response

    def _setup_error_handlers(self):
        @self._app.errorhandler(404)
        def not_found(e):
            return jsonify({"error": "Not Found", "code": 404}), 404

        @self._app.errorhandler(500)
        def internal_error(e):
            return jsonify({"error": "Internal Server Error", "code": 500}), 500

    def is_authenticated(self) -> bool:
        """Validate the authentication token from the request header.

        Checks MvupdateKeyRepository (TOKEN prefix + key id).
        Accepts "TOKEN <value>" (with space) and "TOKEN<value>" (without space).
        """
        auth = request.headers.get(AUTH_HEADER, "")
        if not auth or not auth.startswith(AUTH_TOKEN_PREFIX):
            return False
        token = auth[len(AUTH_TOKEN_PREFIX):].strip()
        repo = MvupdateKeyRepositoryImpl()
        return repo.contains(token)

    def is_server_authenticated(self) -> bool:
        """Validate using server config token (for discovery routes).

        Accepts "TOKEN <value>" (with space) and "TOKEN<value>" (without space).
        """
        auth = request.headers.get(AUTH_HEADER, "")
        repo = ServerConfigRepositoryProperties()
        config = repo.get_current_server_config()
        if config and auth:
            token_part = auth[len(AUTH_TOKEN_PREFIX):].strip() if auth.startswith(AUTH_TOKEN_PREFIX) else auth
            if token_part == config.token:
                return True
        return False

    def require_auth(self):
        """Check MvupdateKeyRepository auth. Returns error response if not authenticated."""
        if not self.is_authenticated():
            return jsonify({"error": "Unauthorized", "code": 401}), 401
        return None

    def require_server_auth(self):
        """Check server config token auth. Returns error response if not authenticated."""
        if not self.is_server_authenticated():
            return jsonify({"error": "Unauthorized", "code": 401}), 401
        return None

    def add_mappings(self):
        """Register all routes. Override in subclasses."""
        pass

    def route(self, rule: str, **options):
        return self._app.route(rule, **options)

    def start(self):
        """Start the HTTP server."""
        self._running = True
        logger.info(f"Starting server on {LOCALHOST}:{self._port}")
        from waitress import serve as waitress_serve
        try:
            waitress_serve(self._app, host=LOCALHOST, port=self._port, _quiet=True)
        except Exception as e:
            logger.error(f"Server error: {e}")
            raise

    def stop(self):
        self._running = False
        logger.info("Server stopped")
