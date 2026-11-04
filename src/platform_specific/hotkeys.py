"""Global hotkey listener, including platform-specific key suppression."""

from __future__ import annotations

from . import IS_LINUX, IS_WINDOWS, UnsupportedPlatformError

if IS_WINDOWS:
    from .windows.hotkeys import HotkeyListener
elif IS_LINUX:
    from .linux.hotkeys import HotkeyListener
else:
    raise UnsupportedPlatformError("global hotkeys")


__all__ = ["HotkeyListener"]
