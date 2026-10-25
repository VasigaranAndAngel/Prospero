"""Icon loading that hides the Windows shell APIs from the rest of the UI."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from data_objects import IconLoadMethod

from . import IS_LINUX, IS_WINDOWS, UnsupportedPlatformError

if TYPE_CHECKING:
    from PySide6.QtGui import QImage

if IS_WINDOWS:
    from .windows.icons import fetch_windows_app_icon, load_icon
elif IS_LINUX:
    from .linux.icons import load_icon

    def fetch_windows_app_icon(app_user_model_id: str, size: int = 32) -> "QImage":
        """Windows-only: resolve a UWP app icon by its App User Model ID."""
        _ = app_user_model_id, size
        raise NotImplementedError("fetch_windows_app_icon is only available on Windows")
else:
    raise UnsupportedPlatformError("icon loading")


__all__ = [
    "IconLoadMethod",
    "fetch_windows_app_icon",
    "load_icon",
]

# ``Path`` is re-exported for callers that annotate alongside the backend signatures.
_ = Path
