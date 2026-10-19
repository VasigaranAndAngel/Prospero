"""Icon fetching facade that picks the platform implementation.

Windows uses the shell/win32 APIs in :mod:`._fetch_icon_win`. On other platforms the
application provider resolves freedesktop icon names to real files, so a plain image
load is enough. Importing this module never touches win32 modules, so it is safe to
import on every platform.

``fetch_windows_app_icon`` stays in the API for callers that share code with Windows;
off Windows it raises ``NotImplementedError`` because there is no UWP equivalent.
"""

from __future__ import annotations

from PySide6.QtGui import QImage

from platform_utils import IS_WINDOWS

if IS_WINDOWS:
    from ._fetch_icon_win import fetch_icon, fetch_windows_app_icon
else:
    from ._fetch_icon_unix import fetch_icon

    def fetch_windows_app_icon(app_user_model_id: str, size: int = 32) -> QImage:
        """Windows-only: resolve a UWP app icon by its App User Model ID."""
        _ = app_user_model_id, size
        raise NotImplementedError("fetch_windows_app_icon is only available on Windows")


__all__ = ["fetch_icon", "fetch_windows_app_icon"]
