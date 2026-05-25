"""ModuleStatus DTO for API responses.

Java behavior: always includes token and _links keys in serialized output
(even if null/empty), using JSONObject bean serialization.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Optional, Any

from models.module import Module


@dataclass
class ModuleStatus:
    """Represents the status of a module in API responses (HATEOAS-style)."""
    status: str
    release: str
    token: Optional[str] = None
    _links: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_module(cls, module: Module) -> ModuleStatus:
        """Create a ModuleStatus from a Module instance."""
        status = module.get_status()
        url = module.get_url()
        token = module.get_token()

        links = {}
        if url:
            links["self"] = {"href": url}

        return cls(
            status=status.value,
            release=module.get_release_module(),
            token=token,
            _links=links,
        )

    def to_dict(self) -> dict:
        """Serialize to dict. Java always includes token and _links keys."""
        return {
            "status": self.status,
            "release": self.release,
            "token": self.token,
            "_links": self._links,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())
