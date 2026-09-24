import fnmatch
import json
import logging
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Thread
from typing import Literal, override

from pydantic import BaseModel

from configs import conf
from data_objects import IconLoadMethod, LoadMethod

from ._lnk_parser import LnkDetail, parse_lnk

logger = logging.getLogger(__name__)

_START_MENU_PATH: Path = Path("Microsoft/Windows/Start Menu/")

SHORTCUT_PATHS: list[Path] = [
    Path.home() / "AppData" / "Roaming" / _START_MENU_PATH,
    Path("C:/ProgramData") / _START_MENU_PATH,
]
"List of Path of shortcuts to include. Add or remove paths as needed."

EXCLUDE_LIST: list[str] = [  # TODO: more robust exclude list which accepts Path, appID, etc.
    "*/desktop.ini",
    "*/Desktop.ini",
]


class StartApp(BaseModel):
    Name: str
    AppID: str


@dataclass
class ShortcutTarget:
    Name: str
    LnkPath: Path
    icon_load_method: "IconLoadMethod"


@dataclass
class AppDetail:
    app_name: str | None = None
    app_id: str | None = None
    type: Literal["uwp", "desktop", "unknown"] | None = None
    path: Path | None = None
    icon: IconLoadMethod | None = None
    lnk_detail: LnkDetail | None = None
    recent_files: list[Path] | None = None


def _run_ps(command: str):
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        shell=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return result.stdout


def _get_start_apps() -> list[StartApp]:
    out = _run_ps("Get-StartApps | ConvertTo-Json -Depth 3")
    data: list[dict[str, str]] | dict[str, str] = json.loads(out)  # pyright: ignore[reportAny]
    return (
        [StartApp.model_validate(x) for x in data]
        if isinstance(data, list)
        else [StartApp.model_validate(data)]
    )


def _get_shortcut_targets() -> list[ShortcutTarget]:
    "Retrieves launch targets (files) from SHORTCUT_PATHS and returns as list of ShortcutTarget."
    paths: list[ShortcutTarget] = []

    # Get all the files
    for path in SHORTCUT_PATHS:
        for root, _dirs, _files in path.walk():
            for _file in _files:
                _p = root / _file
                _con = False
                for _ex in EXCLUDE_LIST:
                    if fnmatch.fnmatch(_p.as_posix(), _ex):
                        _con = True
                        break
                if _con:
                    continue
                icon = IconLoadMethod(LoadMethod.win32api, _p)
                paths.append(ShortcutTarget(Name=_p.stem, LnkPath=_p, icon_load_method=icon))

    return paths


def _build_full_app_list() -> list[AppDetail]:
    "Retrieves Start apps, appx packages, and shortcut files. then combines data and returns a list"
    t1 = time.perf_counter()
    start_apps = _get_start_apps()
    logger.debug(f"start app retrieving took: {time.perf_counter() - t1}")
    t2 = time.perf_counter()
    shortcuts = _get_shortcut_targets()
    logger.debug(f"shortcuts retrieving took: {time.perf_counter() - t2}")
    t3 = time.perf_counter()

    full_list: list[AppDetail] = []

    # all uwp apps.
    for sa in filter(lambda x: "!" in x.AppID, start_apps):  # filtering only uwp apps.
        full_list.append(
            AppDetail(
                app_name=sa.Name,
                app_id=sa.AppID,
                type="uwp",
                icon=IconLoadMethod(LoadMethod.win32api_windows_app, app_id=sa.AppID),
            )
        )

    # all shortcut entries
    seen: set[tuple[str, str, str, str]] = set()
    for s in shortcuts:
        is_lnk = s.LnkPath.suffix.casefold() == ".lnk"
        ld = parse_lnk(s.LnkPath) if is_lnk else None
        if ld is not None:
            # drop dupe .lnk files.
            k = ld.dedupe_key
            if k in seen:
                continue
            seen.add(k)

        full_list.append(
            AppDetail(
                app_name=s.Name,
                type="desktop",
                path=s.LnkPath,
                icon=s.icon_load_method,
                lnk_detail=ld,
            )
        )

    logger.debug(f"full app list prepared in {time.perf_counter() - t3}")

    return full_list


def _get_recent_files(detail: list[AppDetail]) -> list[AppDetail]:
    "Fills recent_file on each app from its Windows jump list. Modifies and returns detail."
    t1 = time.perf_counter()
    from ._get_recents import get_recent_files

    res = get_recent_files(detail)
    logger.debug(f"recent files retrieving took: {time.perf_counter() - t1}")
    return res


class AppDetailsFetcher(Thread):
    def __init__(self, callback: Callable[[list[AppDetail]], None]) -> None:
        super().__init__()
        self.still_fetching: bool = False
        self._callback: Callable[[list[AppDetail]], None] = callback

    @override
    def run(self) -> None:
        """Retrieves details of apps and included shortcuts and \
        calls given callback with detail list.

        Calling directly will block this thread. Call start method to fetch from separate thread.
        """
        recent_on = conf.providers.app_provider.show_recent_files.value
        self.still_fetching = recent_on
        self._callback(x := _build_full_app_list())  # give app list. finding recent takes a while
        self.still_fetching = False  # this will used when calling next callback
        if recent_on:
            self._callback(_get_recent_files(x))
