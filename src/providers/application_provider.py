import fnmatch
import json
import logging
import subprocess
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, override

from fuzzy_finder import BaseChoice, IncrementalMatcher

from ._base_provider import BaseProvider
from ._base_result import BaseResult, ExecutionActions

ROAMING: Path = Path.home() / "AppData" / "Roaming"
PROGRAM_DATA: Path = Path("C:/") / "ProgramData"
APP_PATHS: list[Path] = []

for i in {ROAMING, PROGRAM_DATA}:
    APP_PATHS.append(i / "Microsoft" / "Windows" / "Start Menu")

APP_PATHS.append(Path("C:/_My/Other/EnvDir"))

EXCLUDE_LIST: list[Path | str] = [
    "*/desktop.ini",
    "*/Desktop.ini",
]

logger = logging.getLogger(__name__)


def get_apps() -> list[dict[Literal["Name", "AppID"], str]]:
    command = "Get-StartApps | ConvertTo-Json"
    res = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True
    )
    # TODO: should fallback to another method to get apps if this fails
    return json.loads(res.stdout)  # pyright: ignore[reportAny]


@dataclass
class AppChoice(BaseChoice):
    app_id_or_path: str | Path


class AppResult(BaseResult):
    def __init__(
        self,
        result: str,
        command: str | Sequence[str],
        score: int,
        highlighted_indexes: list[int],
        description: str | None,
    ) -> None:
        super().__init__(result, score, highlighted_indexes, description)

        self.command: str | Sequence[str] = command
        "Command that will be sent to the subprocess.Popen."

    @override
    def execute(self, action: ExecutionActions) -> None:
        # os.startfile(self.start)
        logger.debug(f"Launching: {self.command}")
        _ = subprocess.Popen(
            self.command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True
        )


class AppProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__("Application Provider")
        self.paths: list[Path] = []
        self.matcher: IncrementalMatcher[AppChoice] = IncrementalMatcher([], 5)
        self._update_choices()

    def _update_choices(self) -> None:
        def _is_excluded(file: dict[Literal["Name", "AppID"], str]) -> bool:
            for i in EXCLUDE_LIST:
                if isinstance(i, Path):
                    raise NotImplementedError

                if fnmatch.fnmatch(file["Name"], i):
                    return False
                if fnmatch.fnmatch(file["AppID"], i):
                    return False
            return True

        filtered = filter(_is_excluded, get_apps())

        self.matcher.update_choices([AppChoice(p["Name"], p["AppID"]) for p in filtered])

    @override
    def search(self, query: str) -> Collection[AppResult]:
        res = self.matcher.search(query)
        return list(
            map(
                lambda x: AppResult(
                    x.choice.text,
                    f"start {_p.as_posix()}"
                    if isinstance((_p := x.choice.app_id_or_path), Path)
                    else f"start shell:appsFolder\\{_p}",  # NOTE: Assuming the str is App ID
                    x.score,
                    x.positions,
                    str(x.choice.app_id_or_path),
                ),
                res,
            )
        )
