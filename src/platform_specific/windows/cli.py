"""Windows single-key read for the interactive CLI."""

from __future__ import annotations


def read_key() -> str:
    """Read a single keypress without echoing it."""
    import msvcrt

    return msvcrt.getwch()


__all__ = ["read_key"]
