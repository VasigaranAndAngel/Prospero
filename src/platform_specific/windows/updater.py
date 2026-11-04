"""Launching the downloaded Windows installer."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from constants import APPLICATION_PATH
from platform_specific import CREATE_NO_WINDOW

import logging

logger = logging.getLogger(__name__)


def run_installer(installer_path: Path) -> bool:
    """Start the installer silently. Returns True when it was launched."""
    cmd = [str(installer_path)]

    if getattr(sys, "frozen", False):
        install_dir = APPLICATION_PATH.parent
    else:
        install_dir = Path("./install_dir").resolve()

    cmd.extend(["/silent", "/autostart", f"/dir={install_dir}"])

    logger.debug(f"Starting installer: {cmd=}")
    _ = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW,
    )
    return True


__all__ = ["run_installer"]
