"""Linux autostart via the XDG Autostart specification.

Windows launches at logon through the Task Scheduler
(:mod:`windows_task_schedule_handler`); Linux desktops read
``$XDG_CONFIG_HOME/autostart/*.desktop`` when the session starts. This module mirrors the
Windows handler's public API (``add_task``/``remove_task``/``query_task``) so callers such
as the command provider can stay platform agnostic. Unlike the Windows version, these
helpers need no elevation and invoke their callback synchronously.
"""

from __future__ import annotations

import logging
import os
import shlex
import sys
from collections.abc import Callable
from pathlib import Path

from constants import APPLICATION_NAME, APPLICATION_PATH

logger = logging.getLogger(__name__)

_ENTRY_NAME = f"{APPLICATION_NAME.title()}.desktop"
_CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
_AUTOSTART_DIR = _CONFIG_HOME / "autostart"
_ENTRY_PATH = _AUTOSTART_DIR / _ENTRY_NAME


def _exec_command() -> list[str]:
    """Command a desktop session should run to start Prospero."""
    if getattr(sys, "frozen", False):
        return [str(APPLICATION_PATH)]
    # src/helpers/linux_autostart.py -> project root is parents[2]
    entry = Path(__file__).resolve().parents[2] / "src" / "main.py"
    return [sys.executable, str(entry)]


def _entry_contents() -> str:
    exec_line = shlex.join(_exec_command())
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APPLICATION_NAME.title()}\n"
        f"Comment=Start {APPLICATION_NAME.title()} at login\n"
        f"Exec={exec_line}\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )


def _add_task() -> bool:
    """Write the XDG autostart entry. Returns True on success."""
    try:
        _AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
        _ = _ENTRY_PATH.write_text(_entry_contents(), encoding="utf-8")
    except OSError as e:
        logger.error("Failed to create autostart entry %s: %s", _ENTRY_PATH, e)
        return False
    logger.debug("Autostart entry created at %s", _ENTRY_PATH)
    return True


def _remove_task() -> bool:
    """Delete the XDG autostart entry. Returns True when it is gone afterwards."""
    try:
        _ENTRY_PATH.unlink(missing_ok=True)
    except OSError as e:
        logger.error("Failed to remove autostart entry %s: %s", _ENTRY_PATH, e)
        return False
    logger.debug("Autostart entry removed from %s", _ENTRY_PATH)
    return True


def _query_task() -> tuple[bool, str]:
    """Return ``(exists, contents)`` for the autostart entry."""
    if not _ENTRY_PATH.is_file():
        return False, f"Autostart entry not found: {_ENTRY_PATH}"
    try:
        return True, _ENTRY_PATH.read_text(encoding="utf-8")
    except OSError as e:
        return False, str(e)


def add_task(callback: Callable[[bool], None]) -> None:
    """Add the autostart entry and report success to ``callback``."""
    callback(_add_task())


def remove_task(callback: Callable[[bool], None]) -> None:
    """Remove the autostart entry and report success to ``callback``."""
    callback(_remove_task())


def query_task(callback: Callable[[tuple[bool, str]], None]) -> None:
    """Report the autostart entry status to ``callback``."""
    callback(_query_task())


__all__ = [
    "add_task",
    "query_task",
    "remove_task",
]
