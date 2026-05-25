"""IO utilities."""

from typing import Optional


def input_stream_to_string(stream) -> str:
    """Read an input stream (or file-like object) into a string."""
    if hasattr(stream, 'read'):
        data = stream.read()
        if isinstance(data, bytes):
            return data.decode("utf-8")
        return data
    return str(stream)
