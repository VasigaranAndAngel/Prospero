"""Platform-neutral data shared by the per-platform app discovery backends."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from data_objects import IconLoadMethod


@dataclass(frozen=True)
class Launch:
    """Execute application or document.

    Call this to execute the application or document.
    ``args`` is either a ready argv sequence (POSIX) or a shell command string (Windows),
    and ``shell`` says which of the two ``subprocess`` should be given.
    """

    args: str | Sequence[str]
    shell: bool = False

    def __call__(self) -> None:
        if self.shell and isinstance(self.args, str):
            cmd = self.args
        elif isinstance(self.args, (list, tuple)):
            cmd = list(self.args)
        elif isinstance(self.args, str):
            cmd = self.args
        else:
            return

        _ = subprocess.Popen(
            args=cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=isinstance(cmd, str),
        )


@dataclass(frozen=True)
class RecentFile:
    """A recently used document together with the platform's way to open it."""

    name: str
    launch: Launch
    path: Path | None = None
    icon: IconLoadMethod | None = None


@dataclass
class AppDetail:
    """A launchable application discovered by a platform backend.

    Backends fill ``launch`` so callers never have to know how a platform starts
    programs. ``type``, ``app_id`` and ``lnk_detail`` are backend bookkeeping and are
    not interpreted outside the platform package.
    """

    launch: Launch
    app_name: str
    app_id: str | None = None
    type: Literal["uwp", "desktop", "unknown"] = "unknown"
    path: Path | None = None
    icon: IconLoadMethod | None = None
    lnk_detail: object | None = None
    recent_files: list[RecentFile] | None = None


__all__ = ["AppDetail", "Launch", "RecentFile"]
