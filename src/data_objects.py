"""
Data objects shared across modules.

Holds lightweight dataclasses and/or data related objects used by multiple modules. Isolated here
(low-level deps only, no imports from package modules) so other modules
can import them without triggering circular imports.

Currently defines:
    - IconLoadMethod: how an icon should be loaded (win32api, generic
      win32api, from file, or default), with optional file path.
"""

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import override


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


@dataclass
class IconLoadMethod:
    """
    how an icon should be loaded

    This is related to ui._result_box._icon.py
    """

    load_method: LoadMethod
    file_path: Path | None = None
    app_id: str | None = None

    @override
    def __hash__(self) -> int:
        return hash(f"{self.load_method}{self.file_path}{self.app_id}")
