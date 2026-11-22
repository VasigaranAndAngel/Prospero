"""Environment handling for processes started by Prospero."""

from __future__ import annotations

import os
import sys

_PYI_PREFIXES = ("_PYI_", "PYINSTALLER_")


def child_environment() -> dict[str, str]:
    """Return a clean environment for applications launched by Prospero.

    PyInstaller's bootloader prepends the bundle directory to ``LD_LIBRARY_PATH`` and saves the
    original value in ``LD_LIBRARY_PATH_ORIG``. It also injects ``_PYI_*`` variables. Passing that
    environment to other apps makes them load Prospero's bundled shared libraries, which can break
    them (for example, ``kde-open`` fails on a Qt version mismatch and ``xdg-open`` then exits 4).

    Outside a frozen build the current environment is returned unchanged.
    """
    env = dict(os.environ)
    if not getattr(sys, "frozen", False):
        return env

    original = env.pop("LD_LIBRARY_PATH_ORIG", None)
    if original:
        env["LD_LIBRARY_PATH"] = original
    else:
        _ = env.pop("LD_LIBRARY_PATH", None)

    for key in tuple(env):
        if key.startswith(_PYI_PREFIXES):
            del env[key]

    return env


__all__ = ["child_environment"]
