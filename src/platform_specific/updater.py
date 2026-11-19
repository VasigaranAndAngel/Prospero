"""Platform-specific pieces of the versioned update installer."""

from __future__ import annotations

from . import IS_LINUX, IS_WINDOWS, UnsupportedPlatformError

if IS_WINDOWS:
    from .windows.updater import (
        APP_EXECUTABLE_NAME,
        FILE_MATCH_PAT,
        FILE_MATCH_PATS,
        cleanup_old_versions,
        commit_install,
        restart_app,
    )
elif IS_LINUX:
    from .linux.updater import (
        APP_EXECUTABLE_NAME,
        FILE_MATCH_PAT,
        FILE_MATCH_PATS,
        cleanup_old_versions,
        commit_install,
        restart_app,
    )
else:
    raise UnsupportedPlatformError("automatic update installation")


__all__ = [
    "APP_EXECUTABLE_NAME",
    "FILE_MATCH_PAT",
    "FILE_MATCH_PATS",
    "cleanup_old_versions",
    "commit_install",
    "restart_app",
]
