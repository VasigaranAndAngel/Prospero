"""Single-key reads for the CLI without echoing the pressed key."""

from __future__ import annotations

from . import IS_LINUX, IS_WINDOWS, UnsupportedPlatformError

if IS_WINDOWS:
    from .windows.cli import read_key
elif IS_LINUX:
    from .linux.cli import read_key
else:
    raise UnsupportedPlatformError("interactive CLI")


__all__ = ["read_key"]
