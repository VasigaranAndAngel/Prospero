import logging
from collections.abc import Callable, Collection
from dataclasses import dataclass
from typing import override

from data_objects import IconLoadMethod, LoadMethod
from fuzzy_finder import BaseChoice, IncrementalMatcher
from helpers import task_schedule_handler

from ._base_provider import BaseProvider
from ._loading_request import LoadingRequest
from .base_result_and_widgets import BaseResult, ExecutionAction

logger = logging.getLogger(__name__)


@dataclass
class DebugChoice(BaseChoice):
    icon: IconLoadMethod = IconLoadMethod(LoadMethod.default)
    loading_line: bool = False
    execute: Callable[[], None] | None = None


@dataclass
class DebugResult(BaseResult):
    loading_line: bool = False
    execute_: Callable[[], None] | None = None

    @override
    def __hash__(self) -> int:
        return super().__hash__()

    @override
    def execute(self, action: ExecutionAction) -> None:
        logger.debug(
            f"executed; {action in ExecutionAction.Trigger=}; {self.execute_ is not None=}"
        )
        if action in ExecutionAction.Trigger and self.execute_ is not None:
            self.execute_()


class DebugProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__("Debug Provider")

        self._loading_request: LoadingRequest = LoadingRequest(100)

        choices: list[DebugChoice] = []
        for i in range(10):
            choices.append(
                DebugChoice(f"Debug: Loading Icon {i}", IconLoadMethod(LoadMethod.loading))
            )

        choices.append(DebugChoice("Debug: Loading Icon", IconLoadMethod(LoadMethod.loading)))
        choices.append(DebugChoice("Debug: Default Icon", IconLoadMethod(LoadMethod.loading)))
        choices.append(
            DebugChoice(
                "Debug: Loading Line", IconLoadMethod(LoadMethod.loading), loading_line=True
            )
        )
        choices.append(
            DebugChoice(
                "Debug: Add Prospero Startup", execute=lambda: task_schedule_handler.add_task(print)
            )
        )
        choices.append(
            DebugChoice(
                "Debug: Query Prospero Startup",
                execute=lambda: task_schedule_handler.query_task(print),
            )
        )
        choices.append(
            DebugChoice(
                "Debug: Remove Prospero Startup",
                execute=lambda: task_schedule_handler.remove_task(print),
            )
        )

        self._matcher: IncrementalMatcher[DebugChoice] = IncrementalMatcher(choices)

    @override
    def search(self, query: str) -> Collection[DebugResult]:
        res = self._matcher.search(query)
        return [
            DebugResult(
                r.choice.text,
                r.score,
                [],
                icon_load_method=r.choice.icon,
                loading_line=r.choice.loading_line,
                execute_=r.choice.execute,
            )
            for r in res
        ]

    @override
    def search_async(
        self, query: str, callback: Callable[[Collection[BaseResult] | LoadingRequest], None]
    ) -> None:

        def _wrapper(arg: Collection[BaseResult] | LoadingRequest) -> None:
            if isinstance(arg, (list, tuple)) and arg:
                try:
                    first_arg = arg[0]
                    if first_arg and isinstance(first_arg, DebugResult) and first_arg.loading_line:
                        callback(self._loading_request)
                    else:
                        self._loading_request.remove()
                except Exception as e:
                    print(e)
            callback(arg)

        return super().search_async(query, _wrapper)
