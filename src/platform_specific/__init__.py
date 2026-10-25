"""Single home for every OS-specific decision in Prospero.

Nothing outside this package may branch on ``sys.platform`` or import win32/Unix
specific modules. Callers import the platform-neutral API from capability modules
and those modules select the implementation under :mod:`platform_specific.windows` or
:mod:`platform_specific.linux`.

This module deliberately stays stdlib-only. It is imported very early (through
:mod:`constants`) and must remain safe and cheap in ``--schtasks-handler`` mode.
"""

from __future__ import annotations

import os
import subprocess
import sys

IS_WINDOWS: bool = sys.platform == "win32"
"True when running on Windows."

IS_LINUX: bool = sys.platform.startswith("linux")
"True when running on Linux."

IS_MACOS: bool = sys.platform == "darwin"
"True when running on macOS."

SUPPORTED_PLATFORMS: tuple[str, ...] = ("win32", "linux")
"Platforms with an implementation. Anything else is rejected explicitly."

CREATE_NO_WINDOW: int = getattr(subprocess, "CREATE_NO_WINDOW", 0)
"""``subprocess`` creation flag that hides the console window on Windows.

``0`` on other platforms, which is the default and therefore safe to pass to
``subprocess.Popen(creationflags=...)`` anywhere.
"""


class UnsupportedPlatformError(RuntimeError):
    """Raised when platform-specific functionality is requested on an unsupported OS."""


def is_running_as_admin() -> bool:
    """Whether the current process has administrative/root privileges."""
    if IS_WINDOWS:
        import ctypes

        return ctypes.windll.shell32.IsUserAnAdmin() != 0  # pyright: ignore[reportAny]

    getuid = getattr(os, "getuid", None)
    return getuid is not None and getuid() == 0


def require_supported() -> None:
    """Raise :class:`UnsupportedPlatformError` unless this OS has an implementation."""
    if not (IS_WINDOWS or IS_LINUX):
        raise UnsupportedPlatformError(
            f"Prospero supports Windows and Linux only. Current platform: {sys.platform!r}."
        )


__all__ = [
    "CREATE_NO_WINDOW",
    "IS_LINUX",
    "IS_MACOS",
    "IS_WINDOWS",
    "SUPPORTED_PLATFORMS",
    "UnsupportedPlatformError",
    "is_running_as_admin",
    "require_supported",
]
