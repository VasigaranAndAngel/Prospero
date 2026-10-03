"""
Data objects shared across modules.

Holds lightweight dataclasses and/or data related objects used by multiple modules. Isolated here
(low-level deps only, no imports from package modules) so other modules
can import them without triggering circular imports.

Currently defines:
    - IconLoadMethod: how an icon should be loaded (win32api, generic
      win32api, from file, or default), with optional file path.
"""

from enum import Enum, auto
from pathlib import Path
from typing import ClassVar, override


class LoadMethod(Enum):
    win32api = auto()
    "Fetch icon with win32 api of a file."
    win32api_generic = auto()
    "Fetch generic icon with win32 api of a file."
    win32api_windows_app = auto()
    "Retrieves the icon for a Windows application by its App User Model ID"
    load_file = auto()
    "Loads the icon from icon/image file path."
    default = auto()
    "Shows the default icon. (Doesn't look for any icons)"
    loading = auto()
    "Shows the loading animation. (Doesn't look for any icons)"


class IconLoadMethod:
    _cache: ClassVar[dict[int, "IconLoadMethod"]] = {}  # TODO: limit the cache count
    """
    how an icon should be loaded

    This is related to ui._result_box._icon.py
    """

    load_method: LoadMethod = LoadMethod.default
    file_path: Path | None = None
    app_id: str | None = None

    def __new__(
        cls, load_method: LoadMethod, file_path: Path | None = None, app_id: str | None = None
    ):
        if load_method in {LoadMethod.default, LoadMethod.loading}:
            # No need to store them if load method is default or loading.
            file_path = None
            app_id = None

        hsh = cls._get_hash(load_method, file_path, app_id)
        if hsh not in cls._cache:
            ins = cls._cache[hsh] = super().__new__(cls)
            ins.load_method = load_method
            ins.file_path = file_path
            ins.app_id = app_id
        return cls._cache[hsh]

    @override
    def __hash__(self) -> int:
        return self._get_hash(self.load_method, self.file_path, self.app_id)

    @staticmethod
    def _get_hash(load_method: LoadMethod, file_path: Path | None, app_id: str | None) -> int:
        return hash(f"{load_method}{file_path}{app_id}")
