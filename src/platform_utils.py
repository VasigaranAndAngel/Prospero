"""Small platform helpers so Windows/Linux/macOS differences live in one place.

Kept dependency-free (stdlib only) so it can be imported from anywhere, including early in the
startup path and from ``--schtasks-handler`` style helper processes.
"""

from __future__ import annotations

import subprocess
import sys

IS_WINDOWS: bool = sys.platform == "win32"
"True when running on Windows."

IS_LINUX: bool = sys.platform.startswith("linux")
"True when running on Linux."

IS_MACOS: bool = sys.platform == "darwin"
"True when running on macOS."

CREATE_NO_WINDOW: int = getattr(subprocess, "CREATE_NO_WINDOW", 0)
"""``subprocess`` creation flag that hides the console window on Windows.

``0`` on other platforms, which is the default and therefore safe to pass to
``subprocess.Popen(creationflags=...)`` anywhere.
"""

__all__ = [
    "CREATE_NO_WINDOW",
    "IS_LINUX",
    "IS_MACOS",
    "IS_WINDOWS",
]
