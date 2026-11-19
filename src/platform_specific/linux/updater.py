"""Linux update installation through versioned directories and a stable symlink."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

from platform_specific.paths import (
    current_version,
    current_version_file,
    install_root,
    launcher_path,
    previous_version_file,
    running_version,
    version_dir,
    versions_dir,
    write_text_atomic,
)

logger = logging.getLogger(__name__)

FILE_MATCH_PATS: tuple[str, ...] = (
    "*-linux-*.tar.xz",
    "*-linux-*.tar.gz",
)
"Release asset patterns for Linux updates, in order of preference."

FILE_MATCH_PAT: str = FILE_MATCH_PATS[0]
"Preferred release asset pattern for the Linux update archive."

APP_EXECUTABLE_NAME: str = "Prospero"
"Executable name inside a versioned app directory."


def commit_install(version: str) -> bool:
    """Atomically point ``current`` and ``current.txt`` at an extracted version."""
    app_dir = version_dir(version) / "Prospero"
    if not (app_dir / APP_EXECUTABLE_NAME).is_file():
        logger.error("Refusing to activate missing version %s", version)
        return False

    root = install_root()
    root.mkdir(parents=True, exist_ok=True)

    if (previous := current_version()) is not None:
        write_text_atomic(previous_version_file(), previous)

    current = root / "current"
    temporary = root / "current.tmp"
    temporary.unlink(missing_ok=True)
    os.symlink(Path("versions") / version / "Prospero", temporary)
    os.replace(temporary, current)
    write_text_atomic(current_version_file(), version)
    logger.debug("Activated version %s", version)
    return True


def restart_app() -> bool:
    """Wait for this process to exit, then start the stable ``prospero`` entry point."""
    command = launcher_path()
    if not command.exists():
        logger.error("Cannot restart: entry point not found at %s", command)
        return False

    script = 'while kill -0 "$1" 2>/dev/null; do sleep 0.1; done; shift; exec "$@"'
    logger.debug("Restarting through %s", command)
    _ = subprocess.Popen(
        [
            "/bin/sh",
            "-c",
            script,
            "prospero-restart",
            str(os.getpid()),
            str(command),
            *sys.argv[1:],
        ],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )
    return True


def cleanup_old_versions() -> None:
    """Remove staging directories and versions other than current/previous."""
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
            logger.debug("Could not remove old version directory %s: %s", child, exc)


__all__ = [
    "APP_EXECUTABLE_NAME",
    "FILE_MATCH_PAT",
    "FILE_MATCH_PATS",
    "cleanup_old_versions",
    "commit_install",
    "restart_app",
]
