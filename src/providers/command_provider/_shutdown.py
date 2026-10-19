"""Power actions (shutdown, restart, hibernate, suspend, lock) for every platform.

Windows calls ``shutdown.exe`` and keeps the Fast Startup (HiberbootEnabled) behaviour when
shutting down. Linux talks to ``systemd``/``logind`` and falls back to ``shutdown``. The
platform branches live here so callers stay platform agnostic, and no win32 module is
imported off Windows.
"""

from __future__ import annotations

import logging
import subprocess

from platform_utils import CREATE_NO_WINDOW, IS_WINDOWS

logger = logging.getLogger(__name__)


def _popen(args: list[str]) -> None:
    _ = subprocess.Popen(args, creationflags=CREATE_NO_WINDOW)


def _try_linux(candidates: list[list[str]], name: str) -> None:
    """Run the first available Linux command, skipping missing binaries."""
    for cmd in candidates:
        try:
            _popen(cmd)
            return
        except (FileNotFoundError, OSError) as e:
            logger.debug("Power action %r command %s failed: %s", name, cmd, e)
    logger.error("No working command found for power action %r", name)


# region Windows


def _shutdown_windows(force: bool) -> None:
    """Shut down Windows, honoring the current Fast Startup (HiberbootEnabled) setting.

    If Fast Startup is enabled -> hybrid shutdown (/hybrid)
    If Fast Startup is disabled -> full shutdown (no /hybrid)
    """
    import winreg

    key_path = r"SYSTEM\CurrentControlSet\Control\Session Manager\Power"

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            value, _ = winreg.QueryValueEx(key, "HiberbootEnabled")
            fast_startup_enabled = bool(value)
    except FileNotFoundError:
        # Key/value missing (older Windows, or hibernation unsupported) -> treat as disabled
        fast_startup_enabled = False

    cmd = ["shutdown", "/s", "/t", "0"]
    if fast_startup_enabled:
        cmd.append("/hybrid")
    if force:
        cmd.append("/f")
    _popen(cmd)


# endregion


# region Linux


def _shutdown_linux() -> None:
    _try_linux([["systemctl", "poweroff"], ["loginctl", "poweroff"]], "shutdown")


def _restart_linux() -> None:
    _try_linux([["systemctl", "reboot"], ["loginctl", "reboot"]], "restart")


def _hibernate_linux() -> None:
    _try_linux([["systemctl", "hibernate"]], "hibernate")


def _sleep_linux() -> None:
    _try_linux([["systemctl", "suspend"]], "sleep")


def _lock_linux() -> None:
    _try_linux(
        [
            ["loginctl", "lock-session"],
            ["xdg-screensaver", "lock"],
            ["xdg-screensaver", "activate-screensaver"],
        ],
        "lock",
    )


# endregion


def shutdown(force: bool = True) -> None:
    """Shut down the computer."""
    if IS_WINDOWS:
        _shutdown_windows(force)
    else:
        _shutdown_linux()


def shutdown_respect_hybrid(force: bool = True) -> None:
    """Backwards-compatible name for :func:`shutdown`."""
    shutdown(force)


def restart(force: bool = True) -> None:
    """Restart the computer."""
    if IS_WINDOWS:
        cmd = ["shutdown", "/r", "/t", "0"]
        if force:
            cmd.append("/f")
        _popen(cmd)
    else:
        _restart_linux()


def hibernate() -> None:
    """Hibernate the computer."""
    if IS_WINDOWS:
        _popen(["shutdown", "/h"])
    else:
        _hibernate_linux()


def sleep() -> None:
    """Suspend the computer."""
    if IS_WINDOWS:
        _popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
    else:
        _sleep_linux()


def lock() -> None:
    """Lock the current user session."""
    if IS_WINDOWS:
        _popen(["rundll32.exe", "user32.dll,LockWorkStation"])
    else:
        _lock_linux()


__all__ = [
    "hibernate",
    "lock",
    "restart",
    "shutdown",
    "shutdown_respect_hybrid",
    "sleep",
]
