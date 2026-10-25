"""Power actions implemented with systemd/logind, with command fallbacks."""

from __future__ import annotations

import logging
import subprocess

from platform_specific import CREATE_NO_WINDOW

logger = logging.getLogger(__name__)


def _popen(args: list[str]) -> None:
    _ = subprocess.Popen(args, creationflags=CREATE_NO_WINDOW)


def _try(candidates: list[list[str]], name: str) -> None:
    """Run the first available command, skipping missing binaries."""
    for cmd in candidates:
        try:
            _popen(cmd)
            return
        except (FileNotFoundError, OSError) as e:
            logger.debug("Power action %r command %s failed: %s", name, cmd, e)
    logger.error("No working command found for power action %r", name)


def shutdown(force: bool = True) -> None:
    """Shut down the computer."""
    _ = force
    _try([["systemctl", "poweroff"], ["loginctl", "poweroff"]], "shutdown")


def restart(force: bool = True) -> None:
    """Restart the computer."""
    _ = force
    _try([["systemctl", "reboot"], ["loginctl", "reboot"]], "restart")


def hibernate() -> None:
    """Hibernate the computer."""
    _try([["systemctl", "hibernate"]], "hibernate")


def sleep() -> None:
    """Suspend the computer."""
    _try([["systemctl", "suspend"]], "sleep")


def lock() -> None:
    """Lock the current user session."""
    _try(
        [
            ["loginctl", "lock-session"],
            ["xdg-screensaver", "lock"],
            ["xdg-screensaver", "activate-screensaver"],
        ],
        "lock",
    )


__all__ = ["hibernate", "lock", "restart", "shutdown", "sleep"]
