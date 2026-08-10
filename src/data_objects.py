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
    win32api_generic = auto()
    win32api_windows_app = auto()
    load_file = auto()
    default = auto()
    loading = auto()


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
