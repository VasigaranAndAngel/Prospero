import logging
import subprocess
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Literal, override

from data_objects import IconLoadMethod
from fuzzy_finder import BaseChoice, IncrementalMatcher

from .._base_provider import BaseProvider
from .._base_result import BaseResult, ExecutionActions, ResultAttributes
from .._loading_request import LoadingRequest
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
        self._fetching_app_details: bool = True
        "Whether the app details are being fetched or not."
        self._call_after_fetching: Callable[[], None] | None = None
        "A callback that will be called after the details are fetched."
        self._loading_request: LoadingRequest = LoadingRequest(score=100)
        "The loading request that will be given to UI from this provider."
        self._loading_request_sent: bool = False
        "Whether the LoadingRequest instance is sent to UI or not."

        self.matcher: IncrementalMatcher[AppChoice] = IncrementalMatcher([], 5)
        self.app_details: AppDetailsFetcher = AppDetailsFetcher(self._update_choices)
        self.app_details.start()

    def _update_choices(self, details: list[AppDetail]) -> None:
        self._fetching_app_details = False
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
        if self._call_after_fetching is not None:
            self._call_after_fetching()

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

    @override
    def search_async(
        self, query: str, callback: Callable[[Collection[BaseResult] | LoadingRequest], None]
    ) -> None:
        # NOTE: This method will be called on each query update. self._call_after_fetching will
        # contain the partial which has the latest query.
        if self._fetching_app_details:
            if not self._loading_request_sent:
                # Send the loading request instance to the UI. (only if not sent already)
                callback(self._loading_request)
                self._loading_request_sent = True

            # Using a wrapper that will be called as soon as search is completed to remove loading request
            def _wrapper(arg: Collection[BaseResult] | LoadingRequest) -> None:
                "To remove LoadingRequest before giving results."
                self._loading_request.remove()
                self._loading_request_sent = False
                callback(arg)

            self._call_after_fetching = partial(super().search_async, query, _wrapper)
        else:
            return super().search_async(query, callback)
