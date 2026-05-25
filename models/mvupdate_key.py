"""MvupdateKey model for URI schema connection authentication."""

from __future__ import annotations
import json
from dataclasses import dataclass


@dataclass
class MvupdateKey:
    """Represents an authentication key from URI schema connections."""
    id: str

    def to_dict(self) -> dict:
        return {"id": self.id}

    @classmethod
    def from_json(cls, json_data: dict) -> MvupdateKey:
        return cls(id=json_data.get("id", ""))
