"""Power actions implemented with Windows commands."""

from __future__ import annotations

import logging
import subprocess

from platform_specific import CREATE_NO_WINDOW

logger = logging.getLogger(__name__)


def _popen(args: list[str]) -> None:
    _ = subprocess.Popen(args, creationflags=CREATE_NO_WINDOW)


def shutdown(force: bool = True) -> None:
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


def restart(force: bool = True) -> None:
    """Restart the computer."""
    cmd = ["shutdown", "/r", "/t", "0"]
    if force:
        cmd.append("/f")
    _popen(cmd)


def hibernate() -> None:
    """Hibernate the computer."""
    _popen(["shutdown", "/h"])


def sleep() -> None:
    """Suspend the computer."""
    _popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])


def lock() -> None:
    """Lock the current user session."""
    _popen(["rundll32.exe", "user32.dll,LockWorkStation"])


__all__ = ["hibernate", "lock", "restart", "shutdown", "sleep"]
