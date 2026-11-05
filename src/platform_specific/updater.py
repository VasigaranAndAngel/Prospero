"""Installing a downloaded update the way the current platform expects."""

from __future__ import annotations

from pathlib import Path

from . import IS_LINUX, IS_WINDOWS, UnsupportedPlatformError

if IS_WINDOWS:
    from .windows.updater import FILE_MATCH_PAT, run_installer
elif IS_LINUX:
    from .linux.updater import FILE_MATCH_PAT, run_installer
else:
    raise UnsupportedPlatformError("automatic update installation")


__all__ = ["Path", "run_installer", "FILE_MATCH_PAT"]
