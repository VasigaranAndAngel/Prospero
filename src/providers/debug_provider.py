import logging
from collections.abc import Callable, Collection
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from data_objects import IconLoadMethod, LoadMethod
from fuzzy_finder import BaseChoice, IncrementalMatcher
from helpers import task_schedule_handler

from ._base_provider import BaseProvider
from ._loading_request import LoadingRequest
from .base_result_and_widgets import BaseResult, ExecutionAction

logger = logging.getLogger(__name__)


@dataclass
class DebugResult(BaseResult, BaseChoice):
    loading_line: bool = False
    execute_: Callable[[], None] | None = None

    @override
    def __hash__(self) -> int:
        return super().__hash__()

    @override
    def execute(self, action: ExecutionAction) -> None:
        if action is ExecutionAction.Trigger and self.execute_ is not None:
            self.execute_()


class DebugProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__("Debug Provider")

        self._loading_request: LoadingRequest = LoadingRequest(100)
        if TYPE_CHECKING:
            from ui._query_box._placeholder_formatter import PlaceholderFormatter
        self._place_fmt: "PlaceholderFormatter | None" = None

        choices: list[DebugResult] = []
        for i in range(10):
            choices.append(
                DebugResult(
                    text=f"Debug: Loading Icon {i}",
                    icon_load_method=IconLoadMethod(LoadMethod.loading),
                )
            )

        choices.append(
            DebugResult(
                text="Debug: Loading Icon", icon_load_method=IconLoadMethod(LoadMethod.loading)
            )
        )
        choices.append(
            DebugResult(
                text="Debug: Default Icon", icon_load_method=IconLoadMethod(LoadMethod.loading)
            )
        )
        choices.append(
            DebugResult(
                text="Debug: Loading Line",
                icon_load_method=IconLoadMethod(LoadMethod.loading),
                loading_line=True,
            )
        )
        choices.append(
            DebugResult(
                text="Debug: Add Prospero Startup",
                execute_=lambda: task_schedule_handler.add_task(print),
            )
        )
        choices.append(
            DebugResult(
                text="Debug: Query Prospero Startup",
                execute_=lambda: task_schedule_handler.query_task(print),
            )
        )
        choices.append(
            DebugResult(
                text="Debug: Remove Prospero Startup",
                execute_=lambda: task_schedule_handler.remove_task(print),
            )
        )
        choices.append(DebugResult(text="Debug: Get first snapshot", execute_=_get_first_snapshot))
        choices.append(
            DebugResult(
                text="Debug: Compare with second snapshot", execute_=_get_and_compare_snapshot
            )
        )

        choices.extend(_prepare_provider_switch_command_choices())
        self._matcher: IncrementalMatcher[DebugResult] = IncrementalMatcher(choices)

    @override
    def search(self, query: str) -> Collection[DebugResult]:
        results = self._matcher.search(query)

        _q = query.strip()
        if _q.lower().startswith("ph:"):
            fmt = _q[3:]

            if self._place_fmt is None:
                from ui._query_box._placeholder_formatter import PlaceholderFormatter

                self._place_fmt = PlaceholderFormatter(fmt)
                _ = self._place_fmt.updated.connect(print)
                self._place_fmt.start()

            self._place_fmt._fmt = fmt
            res = self._place_fmt.format(fmt)
            print(f"starts with ph. {fmt=}; {res=}")
            results.append(DebugResult(text=res, description=fmt, score=100))

        return results

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


first_snapshot = None


def _get_first_snapshot() -> None:
    global first_snapshot
    import tracemalloc

    tracemalloc.start()
    first_snapshot = tracemalloc.take_snapshot()


def _get_and_compare_snapshot() -> None:
    import tracemalloc

    sec_snap = tracemalloc.take_snapshot()
    com = sec_snap.compare_to(first_snapshot, "lineno")  # pyright: ignore[reportArgumentType]

    print("\n" + "=" * 100)
    for stat in com[:10]:
        print(stat)
        logger.debug(stat)


def _prepare_provider_switch_command_choices() -> list[DebugResult]:
    from functools import partial

    from providers import PROVIDERS

    choices: list[DebugResult] = []
    for p in PROVIDERS:
        for ed, func in ("enable", _enable_provider), ("disable", _disable_provider):
            choices.append(
                DebugResult(
                    text=f"{ed.title()} Provider: " + p.__name__,
                    execute_=partial(func, p.__name__),
                )
            )
    return choices


def _disable_provider(provider: str) -> None:
    from providers import disable_provider

    disable_provider(provider)


def _enable_provider(provider: str) -> None:
    from providers import enable_provider

    enable_provider(provider)
