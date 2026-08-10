from collections.abc import Collection
from dataclasses import dataclass
from typing import override

from data_objects import IconLoadMethod, LoadMethod
from fuzzy_finder import BaseChoice, IncrementalMatcher

from ._base_provider import BaseProvider
from ._base_result import BaseResult


@dataclass
class DebugChoice(BaseChoice):
    icon: IconLoadMethod


class DebugResult(BaseResult):
    pass


class DebugProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__("Debug Provider")

        choices: list[DebugChoice] = []
        for i in range(10):
            choices.append(DebugChoice(f"Debug: Loading Icon {i}", IconLoadMethod(LoadMethod.loading)))

        choices.append(DebugChoice("Debug: Loading Icon", IconLoadMethod(LoadMethod.loading)))
        choices.append(DebugChoice("Debug: Default Icon", IconLoadMethod(LoadMethod.loading)))

        self._matcher: IncrementalMatcher[DebugChoice] = IncrementalMatcher(choices)

    @override
    def search(self, query: str) -> Collection[DebugResult]:
        res = self._matcher.search(query)
        return [
            DebugResult(r.choice.text, r.score, [], icon_load_method=r.choice.icon) for r in res
        ]
