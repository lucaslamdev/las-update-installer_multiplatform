"""ServerInfo and related DTOs for discovery and API responses."""

from __future__ import annotations
import json
import platform
from dataclasses import dataclass

from config import BUILD_NAME, BUILD_VERSION, LOCALHOST


@dataclass
class ServerInfo:
    """Server information DTO.

    In Java, constructed from Environment with:
    - url: http://127.0.0.1:{port} (mountUrl)
    - release: {info.build.name}-{info.build.version} (mountRelease)
    """
    url: str
    release: str

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "release": self.release,
        }

    @classmethod
    def from_environment(cls, env, port: int = 0) -> ServerInfo:
        """Build ServerInfo from Environment (matches Java constructor)."""
        # mountRelease: info.build.name + "-" + info.build.version
        build_name = env.get_property("info.build.name", "")
        build_version = env.get_property("info.build.version", "")
        release = f"{build_name}-{build_version}" if build_name and build_version else ""

        # mountUrl: http://127.0.0.1 + (port ? ":" + port : "")
        url = f"http://{LOCALHOST}"
        if port:
            url = f"{url}:{port}"

        return cls(url=url, release=release)


@dataclass
class LinkResource:
    """HATEOAS link resource."""
    href: str

    def to_dict(self) -> dict:
        return {"href": self.href}


@dataclass
class ErrorInfo:
    """Error information DTO."""
    url: str
    code: int
    reason: str

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "code": self.code,
            "reason": self.reason,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())
