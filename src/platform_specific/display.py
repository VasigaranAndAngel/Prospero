"""Desktop/session quirks that only apply to some platforms."""

from __future__ import annotations

import os

from . import IS_LINUX


def configure_qt_platform() -> None:
    """Prepare environment variables the Qt platform plugin needs.

    Wayland cannot position top-level windows (the spawn slide, dragging and saved
    position all silently do nothing), so on Linux we prefer XWayland when an X display
    is available. No-op everywhere else.
    """
    if not IS_LINUX or os.environ.get("QT_QPA_PLATFORM"):
        return

    wayland_session = (
        os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
        or bool(os.environ.get("WAYLAND_DISPLAY"))
    )
    if wayland_session and os.environ.get("DISPLAY"):
        os.environ["QT_QPA_PLATFORM"] = "xcb"


__all__ = ["configure_qt_platform"]
