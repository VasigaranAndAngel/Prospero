"""Windows foreground-window handling."""

from __future__ import annotations


def force_foreground(hwnd: int) -> None:
    """Bring ``hwnd`` to the foreground, working around focus-stealing protection."""
    import ctypes

    user32 = ctypes.windll.user32
    fg_hwnd = user32.GetForegroundWindow()  # pyright: ignore[reportAny]
    if not fg_hwnd:
        user32.SetForegroundWindow(hwnd)
        return
    fg_thread = user32.GetWindowThreadProcessId(fg_hwnd, None)  # pyright: ignore[reportAny]
    current_thread = ctypes.windll.kernel32.GetCurrentThreadId()  # pyright: ignore[reportAny]
    if fg_thread == current_thread:
        user32.SetForegroundWindow(hwnd)
        return
    user32.AttachThreadInput(fg_thread, current_thread, True)
    try:
        user32.SetForegroundWindow(hwnd)
    finally:
        user32.AttachThreadInput(fg_thread, current_thread, False)


__all__ = ["force_foreground"]
