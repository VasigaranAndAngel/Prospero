"""Automatic update installation is not implemented on Linux yet."""

from __future__ import annotations

from pathlib import Path


def run_installer(installer_path: Path) -> bool:
    """Report that the downloaded file was not started."""
    _ = installer_path
    return False


__all__ = ["run_installer"]
