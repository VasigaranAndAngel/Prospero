"""Window-manager specific behaviour."""

from __future__ import annotations

from . import IS_LINUX, IS_WINDOWS, UnsupportedPlatformError

if IS_WINDOWS:
    from .windows.windowing import force_foreground
elif IS_LINUX:
    from .linux.windowing import force_foreground
else:
    raise UnsupportedPlatformError("window management")


__all__ = ["force_foreground"]
