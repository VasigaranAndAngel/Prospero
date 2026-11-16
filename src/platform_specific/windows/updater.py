"""Windows update installation through versioned directories and a stable launcher."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys

from platform_specific.paths import (
    current_version,
    install_root,
    launcher_path,
    pending_version_file,
    previous_version_file,
    running_version,
    version_dir,
    versions_dir,
    write_text_atomic,
)

logger = logging.getLogger(__name__)

FILE_MATCH_PAT: str = "*-windows-*.zip"
"Release asset pattern for the Windows update archive."

APP_EXECUTABLE_NAME: str = "Prospero.exe"
"Executable name inside a versioned app directory."

_DETACHED_PROCESS: int = 0x00000008
_CREATE_NEW_PROCESS_GROUP: int = 0x00000200


def commit_install(version: str) -> bool:
    """Stage a version for the launcher to activate on the next start.

    The launcher owns ``current.txt``. The app only writes ``pending.txt`` so a crash between
    extraction and restart leaves the old version runnable.
    """
    if not (version_dir(version) / "Prospero" / APP_EXECUTABLE_NAME).is_file():
        logger.error("Refusing to activate missing version %s", version)
        return False

    root = install_root()
    root.mkdir(parents=True, exist_ok=True)

    if (previous := current_version()) is not None:
        write_text_atomic(previous_version_file(), previous)
    write_text_atomic(pending_version_file(), version)
    logger.debug("Staged %s for activation; current is %s", version, current_version())
    return True


def restart_app() -> bool:
    """Start the stable launcher, which waits for this process and starts the new version."""
    launcher = launcher_path()
    if not launcher.is_file():
        logger.error("Cannot restart: launcher not found at %s", launcher)
        return False

    command = [str(launcher), "--wait-pid", str(os.getpid()), *sys.argv[1:]]
    logger.debug("Restarting through %s", command)
    _ = subprocess.Popen(
        command,
        cwd=str(install_root()),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=_DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )
    return True


def cleanup_old_versions() -> None:
    """Remove staging directories and versions other than current/previous."""
    if pending_version_file().exists():
        # A pending update has not been activated yet; never delete its directory.
        return

    def installed(version: str | None) -> bool:
        return bool(
            version
            and (version_dir(version) / "Prospero" / APP_EXECUTABLE_NAME).is_file()
        )

    keep = {
        version
        for version in (current_version(), running_version())
        if installed(version)
    }
    try:
        previous = previous_version_file().read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        previous = ""
    if previous and installed(previous):
        keep.add(previous)

    if not keep:
        logger.warning("No current or running version; skipping version cleanup.")
        return

    versions = versions_dir()
    if not versions.is_dir():
        return
    for child in versions.iterdir():
        if not child.is_dir():
            continue
        if child.name in keep:
            continue
        if child.name.startswith(".staging-"):
            shutil.rmtree(child, ignore_errors=True)
            continue
        try:
            shutil.rmtree(child)
            logger.debug("Removed old version directory %s", child)
        except OSError as exc:
            # A locked directory is normal if another copy of the app is still running.
            logger.debug("Could not remove old version directory %s: %s", child, exc)


__all__ = [
    "APP_EXECUTABLE_NAME",
    "FILE_MATCH_PAT",
    "cleanup_old_versions",
    "commit_install",
    "restart_app",
]
