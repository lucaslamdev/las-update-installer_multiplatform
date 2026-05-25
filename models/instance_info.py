"""InstanceInfo data model for discovery registration."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from config import LOCALHOST


@dataclass
class InstanceInfo:
    """Represents a registered service instance."""
    release: str
    instance_id: str
    url: str

    @staticmethod
    def builder(release: str = "", port: int = 0) -> InstanceInfo:
        """Build an InstanceInfo from release and port."""
        if release and port:
            url = f"http://{LOCALHOST}:{port}"
        else:
            url = ""
        return InstanceInfo(release=release, instance_id="", url=url)

    def to_dict(self) -> dict:
        return {
            "release": self.release,
            "instanceId": self.instance_id,
            "url": self.url,
        }

    @classmethod
    def from_dict(cls, data: dict) -> InstanceInfo:
        return cls(
            release=data.get("release", ""),
            instance_id=data.get("instanceId", ""),
            url=data.get("url", ""),
        )
