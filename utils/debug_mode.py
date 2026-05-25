"""Debug mode utilities for tracing HTTP traffic, module lifecycle and archives."""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import sys
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
BASE64_RE = re.compile(r"^[A-Za-z0-9+/=\s]+$")
_lock = threading.Lock()
_print_lock = threading.Lock()


class DebugMode:
    """Central debug tracing (disabled by default in production)."""

    _enabled: Optional[bool] = None
    _base_dir: Optional[str] = None

    @classmethod
    def _activate(cls):
        cls._enabled = True
        cls._ensure_dirs()
        logger.info("Debug mode ENABLED — logs in %s", cls.get_base_dir())
        cls._console_banner()

    @classmethod
    def enable(cls, base_dir: Optional[str] = None):
        if base_dir:
            cls._base_dir = base_dir
        cls._activate()

    @classmethod
    def is_enabled(cls) -> bool:
        if cls._enabled is not None:
            return cls._enabled
        if os.environ.get(DEBUG_ENV, "").strip().lower() in ("1", "true", "yes", "on"):
            cls._activate()
            return True
        try:
            from environment import EnvironmentConfiguration

            value = EnvironmentConfiguration.get_environment().get_property(DEBUG_PROPERTY, "false")
            if str(value).strip().lower() in ("1", "true", "yes", "on"):
                cls._activate()
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
    def _console_banner(cls):
        cls._console_print(
            "\n".join(
                [
                    "",
                    "=" * 72,
                    " LAS UPDATE INSTALLER — MODO DEBUG ATIVO",
                    f" Arquivos: {cls.get_base_dir()}",
                    " HTTP recebido/enviado será exibido neste terminal em tempo real.",
                    "=" * 72,
                    "",
                ]
            )
        )

    @classmethod
    def _console_print(cls, text: str):
        with _print_lock:
            print(text, file=sys.stdout, flush=True)

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
    def _try_decode_base64(cls, value: str) -> Any:
        candidate = re.sub(r"\s+", "", value.strip())
        if len(candidate) < 4:
            return None
        if not BASE64_RE.match(candidate):
            return None
        try:
            padded = candidate + "=" * (-len(candidate) % 4)
            decoded_bytes = base64.b64decode(padded, validate=True)
            decoded_text = decoded_bytes.decode("utf-8")
        except Exception:
            return None
        try:
            return json.loads(decoded_text)
        except json.JSONDecodeError:
            return decoded_text

    @classmethod
    def _decode_mvupdate_uri(cls, uri: str) -> dict[str, Any]:
        result: dict[str, Any] = {"uri": uri}
        if not uri.startswith("mvupdate:"):
            return result

        encoded = uri.split("?", 1)[1] if "?" in uri else uri.replace("mvupdate:", "", 1)
        decoded = cls._try_decode_base64(encoded)
        if decoded is not None:
            result["base64_payload"] = encoded
            result["decoded"] = decoded
        else:
            result["base64_payload"] = encoded
            result["decode_error"] = "Não foi possível decodificar o payload Base64 da URI"
        return result

    @classmethod
    def _humanize_value(cls, value: Any, depth: int = 0) -> Any:
        if depth > 6:
            return value

        if isinstance(value, dict):
            enriched: dict[str, Any] = {}
            for key, item in value.items():
                enriched[key] = cls._humanize_value(item, depth + 1)
                if isinstance(item, str):
                    decoded = cls._try_decode_base64(item)
                    if decoded is not None:
                        enriched[f"{key}_decoded_base64"] = decoded
            return enriched

        if isinstance(value, list):
            return [cls._humanize_value(item, depth + 1) for item in value]

        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("mvupdate:"):
                return cls._decode_mvupdate_uri(stripped)

            if stripped.startswith("{") or stripped.startswith("["):
                try:
                    parsed = json.loads(stripped)
                    return cls._humanize_value(parsed, depth + 1)
                except json.JSONDecodeError:
                    pass

            decoded = cls._try_decode_base64(stripped)
            if decoded is not None:
                return {
                    "base64": stripped,
                    "decoded": cls._humanize_value(decoded, depth + 1),
                }

            return value

        return value

    @classmethod
    def _format_for_display(cls, value: Any) -> str:
        if value is None:
            return "(vazio)"
        humanized = cls._humanize_value(value)
        if isinstance(humanized, (dict, list)):
            return json.dumps(humanized, ensure_ascii=False, indent=2, default=str)
        return str(humanized)

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
    def _sanitize_install4j_args(cls, args: list[str]) -> list[str]:
        sanitized = []
        for arg in args:
            if "discovery.server.token=" in arg:
                prefix, _, token = arg.partition("=")
                suffix = token[-4:] if len(token) >= 4 else "****"
                sanitized.append(f"{prefix}=TOKEN***{suffix}")
            else:
                sanitized.append(arg)
        return sanitized

    @classmethod
    def _print_http_console(
        cls,
        *,
        direction_label: str,
        method: str,
        target: str,
        query: str,
        request_headers: dict[str, str],
        request_body: Any,
        status_code: Optional[int],
        response_body: Any,
        duration_ms: float,
        error: Optional[str] = None,
    ):
        lines = [
            "",
            "=" * 72,
            f" HTTP {direction_label}",
            f" {method} {target}{('?' + query) if query else ''}",
            f" Tempo: {duration_ms:.0f} ms",
        ]

        if request_headers:
            lines.append(" -- headers (request) --")
            for key, value in cls._sanitize_headers(request_headers).items():
                lines.append(f"   {key}: {value}")

        lines.append(" -- body (request) --")
        lines.append(cls._indent_block(cls._format_for_display(request_body)))

        lines.append(" -- resposta --")
        if error:
            lines.append(f"   ERRO: {error}")
        else:
            lines.append(f"   status: {status_code}")
        lines.append(" -- body (response) --")
        lines.append(cls._indent_block(cls._format_for_display(response_body)))
        lines.append("=" * 72)

        cls._console_print("\n".join(lines))

    @classmethod
    def _indent_block(cls, text: str) -> str:
        return "\n".join(f"   {line}" for line in text.splitlines()) if text else "   (vazio)"

    @classmethod
    def log_event(cls, category: str, message: str, **data: Any):
        if not cls.is_enabled():
            return
        logger.debug("[%s] %s %s", category, message, data or "")
        cls._write_jsonl("events.jsonl", {"category": category, "message": message, **data})

        if data:
            humanized = cls._humanize_value(data)
            payload = json.dumps(humanized, ensure_ascii=False, indent=2, default=str)
        else:
            payload = "(sem dados extras)"

        cls._console_print(
            "\n".join(
                [
                    "",
                    "-" * 72,
                    f" EVENTO [{category}] {message}",
                    cls._indent_block(payload),
                    "-" * 72,
                ]
            )
        )

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
            "request_body_decoded": cls._humanize_value(request_body),
            "status_code": status_code,
            "response_body": cls._truncate(response_body),
            "response_body_decoded": cls._humanize_value(response_body),
            "duration_ms": round(duration_ms, 2),
        }
        cls._write_jsonl("http_inbound.jsonl", entry)
        cls._save_request_snapshot("inbound", entry)

        cls._print_http_console(
            direction_label="RECEBIDO",
            method=method,
            target=path,
            query=query,
            request_headers=headers,
            request_body=request_body,
            status_code=status_code,
            response_body=response_body,
            duration_ms=duration_ms,
        )

        logger.debug("HTTP IN %s %s -> %s (%.0fms)", method, path, status_code, duration_ms)

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
            "request_body_decoded": cls._humanize_value(request_body),
            "status_code": status_code,
            "response_body": cls._truncate(response_body),
            "response_body_decoded": cls._humanize_value(response_body),
            "duration_ms": round(duration_ms, 2),
            "error": error,
        }
        cls._write_jsonl("http_outbound.jsonl", entry)
        cls._save_request_snapshot("outbound", entry)

        cls._print_http_console(
            direction_label="ENVIADO",
            method=method,
            target=url,
            query="",
            request_headers=request_headers,
            request_body=request_body,
            status_code=status_code,
            response_body=response_body,
            duration_ms=duration_ms,
            error=error,
        )

        logger.debug("HTTP OUT %s %s -> %s (%.0fms)", method, url, status_code, duration_ms)

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

        installer_name = os.path.basename(filename) if filename else release
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
            args=cls._sanitize_install4j_args(args),
            wait=wait,
        )

    @classmethod
    def print_uri_schema(cls, uri: str):
        """Print decoded mvupdate URI to console when debug is active."""
        if not cls.is_enabled():
            return
        decoded = cls._decode_mvupdate_uri(uri)
        cls._console_print(
            "\n".join(
                [
                    "",
                    "-" * 72,
                    " URI mvupdate:// recebida",
                    cls._indent_block(json.dumps(decoded, ensure_ascii=False, indent=2, default=str)),
                    "-" * 72,
                ]
            )
        )


def init_debug_from_argv(argv: list[str]) -> list[str]:
    """Parse --debug from argv, enable mode and return argv without the flag."""
    if "--debug" not in argv:
        return argv
    DebugMode.enable()
    DebugMode.configure_logging()
    return [arg for arg in argv if arg != "--debug"]
