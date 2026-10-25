"""Where Prospero keeps user data and configuration on each platform.

Kept as a small branch inside the platform package rather than a backend module: both
sides are pure ``pathlib``/environment lookups with no imports worth isolating.
"""

from __future__ import annotations

import os
from pathlib import Path

from constants import APPLICATION_NAME

from . import IS_WINDOWS


def config_dir() -> Path:
    """Directory holding user configuration.

    Preserves the historical ``~/.config/<App>`` location on every platform so existing
    installations keep working. Change it here if native per-OS locations are wanted.
    """
    return Path.home() / ".config" / APPLICATION_NAME.title()


def data_dir() -> Path:
    """Directory holding application data (installed modules, caches, and so on)."""
    if IS_WINDOWS:
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / APPLICATION_NAME.title()

    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / APPLICATION_NAME


__all__ = ["config_dir", "data_dir"]
