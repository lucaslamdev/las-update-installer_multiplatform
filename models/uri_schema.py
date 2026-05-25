"""UriSchemaConnect for parsing URI schema connections (mvupdate:connect?...)."""

from __future__ import annotations
import base64
import json
from dataclasses import dataclass

from models.mvupdate_key import MvupdateKey


@dataclass
class UriSchemaConnect:
    """Parses mvupdate:connect?{base64} URI schema connections."""
    uri: str

    def get_mvupdate_key(self) -> MvupdateKey:
        """Extract the MvupdateKey from the URI."""
        # Expected format: mvupdate:connect?{base64_encoded_json}
        if "?" in self.uri:
            _, encoded = self.uri.split("?", 1)
        else:
            encoded = self.uri

        decoded = base64.b64decode(encoded).decode("utf-8")
        json_data = json.loads(decoded)
        return MvupdateKey.from_json(json_data)
