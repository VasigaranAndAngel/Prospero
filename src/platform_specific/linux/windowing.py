"""Linux/X11 window handling.

The window manager owns activation, so Qt's portable ``activateWindow()`` is the only
path available (and the main window already uses it).
"""

from __future__ import annotations


def force_foreground(hwnd: int) -> None:
    """No-op: X11/Wayland window managers control focus."""
    _ = hwnd


__all__ = ["force_foreground"]
