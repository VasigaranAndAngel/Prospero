"""App provider for the application launcher."""

from __future__ import annotations

import logging
from collections.abc import Callable, Collection
from dataclasses import dataclass
from functools import partial
from typing import override

from data_objects import IconLoadMethod, LoadMethod
from fuzzy_finder import BaseChoice, IncrementalMatcher

from .._base_provider import BaseProvider
from .._loading_request import LoadingRequest
from ..base_result import BaseResult, ExecutionAction, ResultAttributes
from ._get_app_details import AppDetail, AppDetailsFetcher
from ._types import Launch

logger = logging.getLogger(__name__)


@dataclass(kw_only=True)
class AppResult(BaseResult, BaseChoice):
    launch: Launch
    "Launch to be called to execute."
    description: str | None = None

    @override
    def execute(self, action: ExecutionAction) -> None:
        if action is ExecutionAction.Trigger:
            logger.debug(f"Launching: {self.launch}")
            self.launch()

    @override
    def __hash__(self) -> int:
        return hash(self.text + str(self.launch.args))


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

        self.matcher: IncrementalMatcher[AppResult] = IncrementalMatcher([], 5)
        self.app_details: AppDetailsFetcher = AppDetailsFetcher(self._update_choices)
        self.app_details.start()

    def _update_choices(self, details: list[AppDetail]) -> None:
        self._fetching_app_details = self.app_details.still_fetching

        choices: list[AppResult] = []
        for d in details:
            # if getattr(d, "launch", None) is not None:
            #     launch = d.launch
            #     path_or_app_id = d.path
            #     if launch.shell and isinstance(launch.args, str):
            #         command: str | Sequence[str] = launch.args
            #     elif isinstance(launch.args, (list, tuple)):
            #         command = list(launch.args)
            #     elif isinstance(launch.args, str):
            #         command = launch.args
            #     else:
            #         continue
            # elif d.type == "uwp":
            #     path_or_app_id = d.app_id
            #     command = f"start shell:appsFolder\\{path_or_app_id or ''}"
            # elif d.type == "desktop":
            #     path_or_app_id = d.path
            #     command = f'start "" "{path_or_app_id or Path()}"'
            # else:
            #     continue
            res = AppResult(
                text=d.app_name or "",
                launch=d.launch,
                description=str(d.app_id if d.type == "uwp" else d.path),
                icon_load_method=d.icon or IconLoadMethod(LoadMethod.default),
                attributes=ResultAttributes(suggestion_request=d.app_name or ""),
            )
            choices.append(res)

            rlist = d.recent_files
            if rlist:
                for r in rlist:
                    res = AppResult(
                        text=(d.app_name or "") + " Recent: " + getattr(r, "name", ""),
                        launch=r.launch,
                        description=str(getattr(r, "path", r)),
                        icon_load_method=IconLoadMethod(
                            LoadMethod.win32api, getattr(r, "path", None)
                        ),
                        attributes=ResultAttributes(suggestion_request=d.app_name or ""),
                    )
                    choices.append(res)

        self.matcher.update_choices(choices)
        if self._call_after_fetching is not None:
            self._call_after_fetching()

    @override
    def search(self, query: str) -> Collection[AppResult]:
        return self.matcher.search(query)

    @override
    def search_async(
        self, query: str, callback: Callable[[Collection[BaseResult] | LoadingRequest], None]
    ) -> None:
        if self._fetching_app_details:
            if not self._loading_request_sent:
                callback(self._loading_request)
                self._loading_request_sent = True

            def _wrapper(arg: Collection[BaseResult] | LoadingRequest) -> None:
                if not self._fetching_app_details:
                    self._loading_request.remove()
                    self._loading_request_sent = False
                callback(arg)

            self._call_after_fetching = partial(super().search_async, query, _wrapper)
        else:
            return super().search_async(query, callback)

    @override
    def disable_hook(self) -> None:
        if self.app_details.is_alive():
            self.app_details.join()
        return super().disable_hook()
