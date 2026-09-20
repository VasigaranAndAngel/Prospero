from abc import ABC, abstractmethod
from collections.abc import Callable, Collection
from typing import override

from global_threading import THREAD_POOL

from ._loading_request import LoadingRequest
from .base_result_and_widgets import BaseResult


class BaseProvider(ABC):
    @abstractmethod
    def __init__(self, name: str) -> None:
        self.name: str = name

    @abstractmethod
    def search(self, query: str) -> Collection[BaseResult]: ...

    def _search_async(self, query: str, callback: Callable[[Collection[BaseResult]], None]) -> None:
        callback(self.search(query))

    def search_async(
        self, query: str, callback: Callable[[Collection[BaseResult] | LoadingRequest], None]
    ) -> None:
        """Does the search in a separate thread and calls the given callback with results.

        Args:
            query (str): The query.
            callback (Callable): Callable to be call with results.
        """
        _ = THREAD_POOL.apply_async(self._search_async, (query, callback))

    def enable_hook(self) -> None:
        "Override this to be called after provider enabled."
        pass

    def disable_hook(self) -> None:
        "Override this to be called when provider is about to disable."
        pass

    @override
    def __repr__(self) -> str:
        return self.__str__() + f" ({type(self)})"

    @override
    def __str__(self) -> str:
        return f"Provider: {self.name}"
