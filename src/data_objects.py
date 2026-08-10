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
from pathlib import Path
from typing import Literal, override


@dataclass
class IconLoadMethod:
    """
    how an icon should be loaded

    This is related to ui._result_box._icon.py
    """

    load_method: Literal["win32api", "win32api_generic", "load_file", "default", "loading"]
    file_path: Path | None = None

    @override
    def __hash__(self) -> int:
        return hash(f"{self.load_method}{self.file_path}")
