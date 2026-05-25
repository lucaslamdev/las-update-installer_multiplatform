"""Logging configuration utility."""

import logging
import os
from typing import Optional


def setup_logging(config_file: Optional[str] = None):
    """Configure application logging.

    If a logging.properties file is found, it will be used.
    Otherwise, a default configuration is applied.
    """
    if config_file is None:
        config_file = os.path.join(os.path.dirname(__file__), "..", "logging.properties")

    if os.path.exists(config_file):
        try:
            import logging.config
            if config_file.endswith(".conf") or config_file.endswith(".ini"):
                logging.config.fileConfig(config_file)
            else:
                _configure_from_properties(config_file)
        except Exception as e:
            logging.basicConfig(level=logging.INFO)
            logging.getLogger(__name__).warning(f"Failed to load logging config: {e}")
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )


def _configure_from_properties(file_path: str):
    """Configure logging from a Java-style logging.properties file."""
    handlers = {}
    root_level = logging.INFO

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            if key == ".level" or key == "level":
                root_level = getattr(logging, value.upper(), logging.INFO)

    logging.basicConfig(level=root_level,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def product_logger():
    """Initialize product-level logging (called at startup)."""
    setup_logging()
