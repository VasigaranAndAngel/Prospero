import logging
import subprocess
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, override

from data_objects import IconLoadMethod
from fuzzy_finder import BaseChoice, IncrementalMatcher

from .._base_provider import BaseProvider
from .._base_result import BaseResult, ExecutionActions, ResultAttributes
from ._get_app_details import AppDetail, AppDetailsFetcher

logger = logging.getLogger(__name__)


@dataclass
class AppChoice(BaseChoice):
    app_id_or_path: str | Path
    type: Literal["uwp", "desktop", "unknown"] | None
    icon_load_method: IconLoadMethod | None

    @override
    def __hash__(self) -> int:
        return hash(self.text + str(self.app_id_or_path))


@dataclass
class AppResult(BaseResult):
    def __init__(
        self,
        result: str,
        command: str | Sequence[str],
        score: int,
        highlighted_indexes: list[int],
        description: str | None,
        icon_load_method: IconLoadMethod | None,
    ) -> None:
        attrs = ResultAttributes(close_after_enter=True)
        if icon_load_method is None:
            super().__init__(result, score, highlighted_indexes, description, attrs)
        else:
            super().__init__(
                result, score, highlighted_indexes, description, attrs, icon_load_method
            )

        self.command: str | Sequence[str] = command
        "Command that will be sent to the subprocess.Popen."

    @override
    def execute(self, action: ExecutionActions) -> None:
        # os.startfile(self.start)
        logger.debug(f"Launching: {self.command}")
        _ = subprocess.Popen(
            self.command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True
        )

    @override
    def __hash__(self) -> int:
        return hash(self.result + str(self.command))


class AppProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__("Application Provider")
        self.matcher: IncrementalMatcher[AppChoice] = IncrementalMatcher([], 5)
        self.app_details: AppDetailsFetcher = AppDetailsFetcher(self._update_choices)
        self.app_details.start()

    def _update_choices(self, details: list[AppDetail]) -> None:
        self.matcher.update_choices(
            [
                AppChoice(
                    a.app_name or "",
                    a.path or Path() if a.type != "uwp" else a.app_id or "",
                    a.type,
                    a.icon,
                )
                for a in details
            ]
        )

    @override
    def search(self, query: str) -> Collection[AppResult]:
        res = self.matcher.search(query)
        return list(
            map(
                lambda x: AppResult(
                    x.choice.text,
                    f'start "" "{_p.as_posix()}"'
                    if isinstance((_p := x.choice.app_id_or_path), Path) and x.choice.type != "uwp"
                    else f"start shell:appsFolder\\{_p}",  # NOTE: Assuming the str is App ID
                    x.score,
                    x.positions,
                    str(x.choice.app_id_or_path),
                    x.choice.icon_load_method,
                ),
                res,
            )
        )
