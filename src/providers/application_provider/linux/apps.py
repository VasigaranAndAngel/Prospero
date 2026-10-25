"""Discover launchable applications on freedesktop systems (Linux/BSD).

Reads ``.desktop`` entries from the XDG data directories, resolves their icons to real
files (so no desktop-theme lookup is needed at draw time) and builds :class:`AppDetail`
objects. This is the Linux counterpart of the Windows Start Menu / UWP scan.
"""

from __future__ import annotations

import configparser
import glob as globmod
import logging
import os
import re
import shlex
from pathlib import Path

from data_objects import IconLoadMethod, LoadMethod

from .._types import AppDetail, Launch

logger = logging.getLogger(__name__)

supports_recent_files: bool = False
"Recent-document integration is not implemented for freedesktop systems."

_APPLICATIONS = "applications"
_ICON_EXTENSIONS = (".png", ".svg", ".xpm")
_FIELD_CODE_RE = re.compile(r"%[a-zA-Z]")
_ALLOWED_TYPES = {"Application", "Link"}


def _data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))


def _data_dirs() -> list[Path]:
    raw = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    return [Path(p) for p in raw.split(":") if p]


def _desktop_files() -> list[Path]:
    """``.desktop`` files, XDG precedence: user dir first, first name wins."""
    seen: set[str] = set()
    files: list[Path] = []
    for base in [_data_home(), *_data_dirs()]:
        app_dir = base / _APPLICATIONS
        if not app_dir.is_dir():
            continue
        try:
            entries = sorted(app_dir.glob("*.desktop"))
        except OSError:
            continue
        for path in entries:
            if path.name in seen:
                continue
            seen.add(path.name)
            files.append(path)
    return files


def _read_entry(path: Path) -> configparser.SectionProxy | None:
    """Parse the ``[Desktop Entry]`` section, or None when missing/unreadable."""
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        _ = parser.read(path, encoding="utf-8")
    except (configparser.Error, OSError, UnicodeDecodeError) as e:
        logger.debug("Skipping unreadable desktop file %s: %s", path, e)
        return None
    if "Desktop Entry" not in parser:
        return None
    return parser["Desktop Entry"]


def _get(entry: configparser.SectionProxy, key: str, default: str = "") -> str:
    """Case-insensitive lookup of a non-empty value."""
    for k, value in entry.items():
        if k.lower() == key.lower():
            stripped = value.strip()
            if stripped:
                return stripped
    return default


def _clean_exec(exec_line: str) -> list[str]:
    """Turn a desktop ``Exec`` value into an argv list with field codes stripped."""
    try:
        parts = shlex.split(exec_line)
    except ValueError as e:
        logger.debug("Could not split Exec %r: %s", exec_line, e)
        return []

    cleaned: list[str] = []
    for part in parts:
        part = part.replace("%%", "\x00")
        part = _FIELD_CODE_RE.sub("", part)
        part = part.replace("\x00", "%")
        if part:
            cleaned.append(part)
    return cleaned


# region icon lookup

_ICON_CACHE: dict[str, Path | None] = {}


def _icon_base_dirs() -> list[Path]:
    dirs: list[Path] = [_data_home() / "icons", _data_home() / "pixmaps"]
    dirs += [d / "icons" for d in _data_dirs()]
    dirs += [d / "pixmaps" for d in _data_dirs()]
    return [d for d in dirs if d.is_dir()]


def _candidate_names(name: str) -> list[str]:
    if Path(name).suffix:
        return [name]
    return [f"{name}{ext}" for ext in _ICON_EXTENSIONS]


def _find_icon_file(name: str) -> Path | None:
    direct = Path(name).expanduser()
    if direct.is_absolute() and direct.is_file():
        return direct

    for cand in _candidate_names(name):
        escaped = globmod.escape(cand)
        for base in _icon_base_dirs():
            if base.name == "pixmaps":
                hit = base / cand
                if hit.is_file():
                    return hit
                continue
            # <icons>/<theme>/<size>/apps/<name> and <icons>/<theme>/apps/<name>
            for pattern in (f"*/*/apps/{escaped}", f"*/apps/{escaped}", f"*/*/*/apps/{escaped}"):
                for hit in base.glob(pattern):
                    if hit.is_file():
                        return hit
    return None


def find_icon_file(name: str) -> Path | None:
    """Resolve a freedesktop icon name (or path) to a file, caching the result."""
    name = name.strip()
    if not name:
        return None
    if name not in _ICON_CACHE:
        _ICON_CACHE[name] = _find_icon_file(name)
    return _ICON_CACHE[name]


# endregion


def build_app_list() -> list[AppDetail]:
    """Build app details from XDG ``.desktop`` entries."""
    details: list[AppDetail] = []
    for path in _desktop_files():
        entry = _read_entry(path)
        if entry is None:
            continue

        entry_type = _get(entry, "Type", "Application")
        if entry_type not in _ALLOWED_TYPES:
            continue
        if _get(entry, "NoDisplay").lower() in {"true", "1"}:
            continue
        if _get(entry, "Hidden").lower() in {"true", "1"}:
            continue
        if _get(entry, "Terminal").lower() in {"true", "1"}:
            # Launching a terminal app without a terminal would just fail silently.
            continue

        exec_command = _clean_exec(_get(entry, "Exec"))
        if not exec_command:
            continue

        name = _get(entry, "Name") or path.stem
        icon_name = _get(entry, "Icon")
        icon_path = find_icon_file(icon_name) if icon_name else None
        icon = (
            IconLoadMethod(LoadMethod.load_file, icon_path)
            if icon_path is not None
            else IconLoadMethod(LoadMethod.default)
        )

        details.append(
            AppDetail(
                app_name=name,
                type="desktop",
                path=path,
                icon=icon,
                launch=Launch(exec_command),
            )
        )

    logger.debug("Discovered %d desktop entries", len(details))
    return details


def get_recent_files(details: list[AppDetail]) -> list[AppDetail]:
    """No-op: freedesktop has no jump-list equivalent implemented here."""
    return details


__all__ = ["build_app_list", "find_icon_file", "get_recent_files", "supports_recent_files"]
