"""Environment configuration module.

Provides hierarchical property resolution across multiple sources:
1. Application runtime properties
2. OS environment variables
3. System properties (not applicable in Python - skipped)
4. application.properties file
"""

import os
from typing import Optional


class PropertySource:
    """Base class for property sources."""

    def get_property(self, key: str) -> Optional[str]:
        raise NotImplementedError

    def contains_property(self, key: str) -> bool:
        return self.get_property(key) is not None


class MapPropertySource(PropertySource):
    """Property source backed by a dictionary."""

    def __init__(self, properties: dict[str, str] | None = None):
        self._properties: dict[str, str] = properties or {}

    def get_property(self, key: str) -> Optional[str]:
        return self._properties.get(key)

    def set_property(self, key: str, value: str):
        self._properties[key] = value

    @property
    def properties(self) -> dict[str, str]:
        return self._properties


class ApplicationEnvPropertySource(PropertySource):
    """Singleton mutable property source for runtime application environment."""

    _instance: Optional["ApplicationEnvPropertySource"] = None
    _properties: dict[str, str]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._properties = {}
        return cls._instance

    def get_property(self, key: str) -> Optional[str]:
        return self._properties.get(key)

    def set_property(self, key: str, value: str):
        self._properties[key] = value


class StandardEnvironment:
    """Resolves properties from multiple sources in priority order."""

    def __init__(self, property_sources: list[PropertySource]):
        self._property_sources = property_sources

    def contains_property(self, key: str) -> bool:
        return any(source.contains_property(key) for source in self._property_sources)

    def get_property(self, key: str, default: Optional[str] = None) -> Optional[str]:
        for source in self._property_sources:
            value = source.get_property(key)
            if value is not None:
                return value
        return default


class EnvironmentConfiguration:
    """Singleton factory for creating the application Environment."""

    _environment: Optional[StandardEnvironment] = None

    @classmethod
    def get_environment(cls) -> StandardEnvironment:
        if cls._environment is None:
            sources = [
                ApplicationEnvPropertySource(),
                MapPropertySource(dict(os.environ)),
                _load_application_properties(),
            ]
            cls._environment = StandardEnvironment(sources)
        return cls._environment


def _load_application_properties() -> PropertySource:
    """Load properties from application.properties file."""
    properties = {}
    props_file = os.path.join(os.path.dirname(__file__), "application.properties")
    if os.path.exists(props_file):
        with open(props_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    properties[key.strip()] = value.strip()
    return MapPropertySource(properties)
