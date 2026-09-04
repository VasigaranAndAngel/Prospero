import fnmatch
import json
import logging
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Thread
from typing import Literal

from pydantic import BaseModel

from data_objects import IconLoadMethod, LoadMethod

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
    shortcuts = {s.Name: s for s in _get_shortcut_targets()}
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
    for name, s in shortcuts.items():
        full_list.append(
            AppDetail(
                app_name=name,
                type="desktop",
                path=s.LnkPath,
                icon=s.icon_load_method,
            )
        )

    logger.debug(f"full app list prepared in {time.perf_counter() - t3}")

    return full_list


class AppDetailsFetcher(Thread):
    def __init__(self, callback: Callable[[list[AppDetail]], None]) -> None:
        super().__init__(target=self.get_app_list)
        # self._app_list: list[AppDetail]
        self._callback: Callable[[list[AppDetail]], None] = callback

    def get_app_list(self) -> None:
        """Retrieves details of apps and included shortcuts and \
        calls given callback with detail list.

        Calling directly will block this thread. Call start method to fetch from separate thread.
        """
        self._callback(_build_full_app_list())
