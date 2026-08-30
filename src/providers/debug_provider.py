from collections.abc import Callable, Collection
from dataclasses import dataclass
from typing import override

from data_objects import IconLoadMethod, LoadMethod
from fuzzy_finder import BaseChoice, IncrementalMatcher
from providers import LoadingRequest

from ._base_provider import BaseProvider
from ._base_result import BaseResult


@dataclass
class DebugChoice(BaseChoice):
    icon: IconLoadMethod
    loading_line: bool = False


@dataclass
class DebugResult(BaseResult):
    loading_line: bool = False

    @override
    def __hash__(self) -> int:
        return super().__hash__()


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
            )
            for r in res
        ]

    @override
    def search_async(
        self, query: str, callback: Callable[[Collection[BaseResult] | LoadingRequest], None]
    ) -> None:

        def _wrapper(arg: Collection[BaseResult] | LoadingRequest) -> None:
            if not isinstance(arg, LoadingRequest):
                try:
                    last_arg = arg[0]
                    if last_arg and isinstance(last_arg, DebugResult) and last_arg.loading_line:
                        callback(self._loading_request)
                    else:
                        self._loading_request.remove()
                except Exception as e:
                    print(e)
            callback(arg)

        return super().search_async(query, _wrapper)
