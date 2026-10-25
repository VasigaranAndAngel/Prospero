"""Start-at-login registration, with the same API on every supported platform."""

from __future__ import annotations

from collections.abc import Callable

from . import IS_LINUX, IS_WINDOWS, UnsupportedPlatformError

if IS_WINDOWS:
    from .windows.startup import add_task, query_task, remove_task, start_listener
elif IS_LINUX:
    from .linux.startup import add_task, query_task, remove_task

    def start_listener(auth_key: str, port: str) -> None:
        """Windows-only: the elevated start-at-login helper process."""
        _ = auth_key, port
        raise NotImplementedError("The elevated startup helper is only used on Windows")
else:
    raise UnsupportedPlatformError("start-at-login integration")


__all__ = ["add_task", "query_task", "remove_task", "start_listener"]

# Keep the callback types visible to type checkers without importing backends twice.
StartupCallback = Callable[[bool], None]
QueryCallback = Callable[[tuple[bool, str]], None]
