"""Platform-dispatched power actions."""

from __future__ import annotations

from platform_specific import IS_LINUX, IS_WINDOWS, UnsupportedPlatformError

if IS_WINDOWS:
    from .windows.power import hibernate, lock, restart, shutdown, sleep
elif IS_LINUX:
    from .linux.power import hibernate, lock, restart, shutdown, sleep
else:
    raise UnsupportedPlatformError("power")

__all__ = ["hibernate", "lock", "restart", "shutdown", "sleep"]
