"""Debug mode utilities for tracing HTTP traffic, module lifecycle and archives."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

from utils.path_utils import get_tmp_directory_path

logger = logging.getLogger(__name__)

DEBUG_ENV = "LAS_DEBUG"
DEBUG_DIR_ENV = "LAS_DEBUG_DIR"
DEBUG_PROPERTY = "las.debug"
MAX_BODY_LOG_BYTES = 8192
_lock = threading.Lock()


class DebugMode:
    """Central debug tracing (disabled by default in production)."""

    _enabled: Optional[bool] = None
    _base_dir: Optional[str] = None

    @classmethod
    def enable(cls, base_dir: Optional[str] = None):
        cls._enabled = True
        if base_dir:
            cls._base_dir = base_dir
        cls._ensure_dirs()
        logger.info("Debug mode ENABLED — logs in %s", cls.get_base_dir())

    @classmethod
    def is_enabled(cls) -> bool:
        if cls._enabled is not None:
            return cls._enabled
        if os.environ.get(DEBUG_ENV, "").strip().lower() in ("1", "true", "yes", "on"):
            cls._enabled = True
            cls._ensure_dirs()
            return True
        try:
            from environment import EnvironmentConfiguration

            value = EnvironmentConfiguration.get_environment().get_property(DEBUG_PROPERTY, "false")
            if str(value).strip().lower() in ("1", "true", "yes", "on"):
                cls._enabled = True
                cls._ensure_dirs()
                return True
        except Exception:
            pass
        cls._enabled = False
        return False

    @classmethod
    def get_base_dir(cls) -> str:
        if cls._base_dir:
            return cls._base_dir
        custom = os.environ.get(DEBUG_DIR_ENV, "").strip()
        if custom:
            cls._base_dir = custom
        else:
            cls._base_dir = os.path.join(get_tmp_directory_path(), "debug")
        return cls._base_dir

    @classmethod
    def get_modules_dir(cls) -> str:
        return os.path.join(cls.get_base_dir(), "modules")

    @classmethod
    def get_requests_dir(cls) -> str:
        return os.path.join(cls.get_base_dir(), "requests")

    @classmethod
    def _ensure_dirs(cls):
        for path in (cls.get_base_dir(), cls.get_modules_dir(), cls.get_requests_dir()):
            os.makedirs(path, exist_ok=True)

    @classmethod
    def configure_logging(cls):
        if not cls.is_enabled():
            return
        root = logging.getLogger()
        root.setLevel(logging.DEBUG)
        for handler in root.handlers:
            handler.setLevel(logging.DEBUG)

    @classmethod
    def _write_jsonl(cls, filename: str, payload: dict[str, Any]):
        if not cls.is_enabled():
            return
        cls._ensure_dirs()
        path = os.path.join(cls.get_base_dir(), filename)
        payload.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        line = json.dumps(payload, ensure_ascii=False, default=str)
        with _lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    @classmethod
    def log_event(cls, category: str, message: str, **data: Any):
        if not cls.is_enabled():
            return
        logger.debug("[%s] %s %s", category, message, data or "")
        cls._write_jsonl("events.jsonl", {"category": category, "message": message, **data})

    @classmethod
    def _truncate(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, bytes):
            if len(value) <= MAX_BODY_LOG_BYTES:
                return {"size": len(value), "preview_hex": value[:256].hex()}
            return {
                "size": len(value),
                "preview_hex": value[:256].hex(),
                "truncated": True,
            }
        text = value if isinstance(value, str) else str(value)
        if len(text) <= MAX_BODY_LOG_BYTES:
            return text
        return text[:MAX_BODY_LOG_BYTES] + f"... [truncated, total={len(text)} chars]"

    @classmethod
    def _sanitize_headers(cls, headers: dict[str, str]) -> dict[str, str]:
        sanitized = {}
        for key, value in headers.items():
            if key.lower() == "authentication" and value:
                token = value.replace("TOKEN", "", 1).strip()
                suffix = token[-4:] if len(token) >= 4 else "****"
                sanitized[key] = f"TOKEN***{suffix}"
            else:
                sanitized[key] = value
        return sanitized

    @classmethod
    def log_http_inbound(
        cls,
        *,
        method: str,
        path: str,
        query: str,
        headers: dict[str, str],
        request_body: Any,
        status_code: int,
        response_body: Any,
        duration_ms: float,
    ):
        if not cls.is_enabled():
            return
        entry = {
            "direction": "inbound",
            "method": method,
            "path": path,
            "query": query,
            "request_headers": cls._sanitize_headers(headers),
            "request_body": cls._truncate(request_body),
            "status_code": status_code,
            "response_body": cls._truncate(response_body),
            "duration_ms": round(duration_ms, 2),
        }
        cls._write_jsonl("http_inbound.jsonl", entry)
        cls._save_request_snapshot("inbound", entry)
        logger.debug(
            "HTTP IN %s %s -> %s (%.0fms)",
            method,
            path,
            status_code,
            duration_ms,
        )

    @classmethod
    def log_http_outbound(
        cls,
        *,
        method: str,
        url: str,
        request_headers: dict[str, str],
        request_body: Any,
        status_code: Optional[int],
        response_body: Any,
        duration_ms: float,
        error: Optional[str] = None,
    ):
        if not cls.is_enabled():
            return
        entry = {
            "direction": "outbound",
            "method": method,
            "url": url,
            "request_headers": cls._sanitize_headers(request_headers),
            "request_body": cls._truncate(request_body),
            "status_code": status_code,
            "response_body": cls._truncate(response_body),
            "duration_ms": round(duration_ms, 2),
            "error": error,
        }
        cls._write_jsonl("http_outbound.jsonl", entry)
        cls._save_request_snapshot("outbound", entry)
        logger.debug(
            "HTTP OUT %s %s -> %s (%.0fms)",
            method,
            url,
            status_code,
            duration_ms,
        )

    @classmethod
    def _save_request_snapshot(cls, direction: str, entry: dict[str, Any]):
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%f")
        safe_path = entry.get("path", entry.get("url", "request")).replace("/", "_").replace(":", "_")
        filename = f"{ts}_{direction}_{safe_path}.json"
        path = os.path.join(cls.get_requests_dir(), filename)
        with _lock:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False, indent=2, default=str)

    @classmethod
    def archive_module_upload(
        cls,
        release: str,
        data: bytes,
        *,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> str:
        if not cls.is_enabled():
            return ""
        cls._ensure_dirs()
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        archive_dir = os.path.join(cls.get_modules_dir(), release, ts)
        os.makedirs(archive_dir, exist_ok=True)

        installer_name = filename or release
        installer_path = os.path.join(archive_dir, installer_name)
        with open(installer_path, "wb") as f:
            f.write(data)

        metadata = {
            "release": release,
            "archived_at": datetime.now(timezone.utc).isoformat(),
            "size_bytes": len(data),
            "filename": installer_name,
            "content_type": content_type,
            "installer_path": installer_path,
        }
        meta_path = os.path.join(archive_dir, "metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        cls.log_event(
            "module",
            "Module upload archived for analysis",
            release=release,
            archive_dir=archive_dir,
            size_bytes=len(data),
        )
        logger.info("Debug archive: module '%s' saved to %s", release, archive_dir)
        return archive_dir

    @classmethod
    def log_install4j(cls, action: str, release: str, executable: str, args: list[str], wait: bool):
        cls.log_event(
            "install4j",
            f"{action} module via install4j",
            release=release,
            executable=executable,
            args=args,
            wait=wait,
        )


def init_debug_from_argv(argv: list[str]) -> list[str]:
    """Parse --debug from argv, enable mode and return argv without the flag."""
    if "--debug" not in argv:
        return argv
    DebugMode.enable()
    DebugMode.configure_logging()
    return [arg for arg in argv if arg != "--debug"]
