"""Installs optional modules the application can use at runtime.

Only packages on the allowlist can be installed, only at a pinned version, and only when the wheel
matches the running interpreter. See ``_allowlist.py`` for the pins and ``_manager.py`` for the
flow.

Currently defines:
    - PackageManager: installs, tracks and removes modules.
    - PackageError: a module could not be resolved, installed or removed.
    - AllowedPackage, AllowedWheel: the allowlist entries.
"""

from ._allowlist import (
    ALLOWLIST,
    AllowedPackage,
    AllowedWheel,
    PackageError,
    allowed_import_names,
    get_allowed,
    select_wheel,
)
from ._finder import ModuleFinder
from ._manager import PackageManager
from ._storage import InstalledPackage, modules_root

__all__ = [
    "ALLOWLIST",
    "AllowedPackage",
    "AllowedWheel",
    "InstalledPackage",
    "ModuleFinder",
    "PackageError",
    "PackageManager",
    "allowed_import_names",
    "get_allowed",
    "modules_root",
    "select_wheel",
]
