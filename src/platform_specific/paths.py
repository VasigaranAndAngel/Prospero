"""Where Prospero keeps user data, configuration and installed versions.

The application itself is installed as a set of versioned directories.  A small
pointer file (``current.txt``) selects the version to run; Windows uses a stable
launcher executable, while Linux uses a stable ``current`` symlink and a
``prospero`` symlink on ``PATH``.

User data and configuration live outside the install root so updating or
uninstalling the application never touches them.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from constants import APPLICATION_NAME

from . import IS_WINDOWS

INSTALL_ROOT_ENV: str = "PROSPERO_INSTALL_ROOT"
"Environment override used by installers, the launcher and tests."


def install_root() -> Path:
    """Directory containing ``current.txt`` and ``versions/``."""
    if override := os.environ.get(INSTALL_ROOT_ENV):
        return Path(override).expanduser()

    if IS_WINDOWS:
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        # Keep the install separate from data_dir(), which is LOCALAPPDATA/Prospero.
        return Path(base) / "Programs" / APPLICATION_NAME.title()

    return Path.home() / ".local" / "opt" / APPLICATION_NAME


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


def versions_dir() -> Path:
    """Directory containing one subdirectory per installed version."""
    return install_root() / "versions"


def version_dir(version: str) -> Path:
    """Directory for one version. It contains a ``Prospero/`` app directory."""
    return versions_dir() / version


def app_dir(version: str) -> Path:
    """The PyInstaller output directory of one version."""
    return version_dir(version) / APPLICATION_NAME.title()


def executable_name() -> str:
    """Name of the application executable inside :func:`app_dir`."""
    return f"{APPLICATION_NAME.title()}.exe" if IS_WINDOWS else APPLICATION_NAME.title()


def app_executable(version: str) -> Path:
    """Path to the executable of one installed version."""
    return app_dir(version) / executable_name()


def current_version_file() -> Path:
    """Pointer file containing the version that should be started."""
    return install_root() / "current.txt"


def pending_version_file() -> Path:
    """Set by the app after extraction; the Windows launcher promotes it."""
    return install_root() / "pending.txt"


def previous_version_file() -> Path:
    """Last version that was current before an update was staged."""
    return install_root() / "previous.txt"


def current_version() -> str | None:
    """Read the current version pointer, or ``None`` when not installed.

    On Linux the ``current`` symlink is checked first. That keeps the pointer correct even if a
    process is interrupted after the atomic symlink swap but before ``current.txt`` is written.
    """
    if not IS_WINDOWS:
        current = install_root() / "current"
        if current.is_symlink():
            try:
                relative = current.resolve(strict=False).relative_to(
                    versions_dir().resolve(strict=False)
                )
            except (OSError, RuntimeError, ValueError):
                pass
            else:
                parts = relative.parts
                if len(parts) >= 2 and parts[-1] == APPLICATION_NAME.title():
                    return parts[0]

    try:
        version = current_version_file().read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return None
    return version or None


def running_version() -> str | None:
    """Version directory of the currently running executable, if it is installed."""
    try:
        relative = Path(sys.executable).resolve(strict=False).relative_to(
            versions_dir().resolve(strict=False)
        )
    except (OSError, RuntimeError, ValueError):
        return None
    if len(relative.parts) < 2:
        return None
    version = relative.parts[0]
    return version if version and not version.startswith(".") else None


def current_executable() -> Path | None:
    """Path to the executable selected by ``current.txt``."""
    version = current_version()
    if version is None:
        return None
    return app_executable(version)


def is_installed_layout() -> bool:
    """Whether the running application belongs to a versioned installation."""
    executable = current_executable()
    return executable is not None and executable.is_file()


def launcher_path() -> Path:
    """Stable entry point used to start the current version."""
    if IS_WINDOWS:
        return install_root() / "ProsperoLauncher.exe"

    bin_home = Path(os.environ.get("XDG_BIN_HOME") or (Path.home() / ".local" / "bin"))
    stable = bin_home / APPLICATION_NAME
    if stable.exists():
        return stable
    return install_root() / "current" / APPLICATION_NAME.title()


def write_text_atomic(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` through a sibling temporary file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


__all__ = [
    "INSTALL_ROOT_ENV",
    "app_dir",
    "app_executable",
    "config_dir",
    "current_executable",
    "current_version",
    "current_version_file",
    "data_dir",
    "executable_name",
    "install_root",
    "is_installed_layout",
    "launcher_path",
    "pending_version_file",
    "previous_version_file",
    "running_version",
    "version_dir",
    "versions_dir",
    "write_text_atomic",
]
