from abc import ABC, abstractmethod
from collections.abc import Callable, Collection

from global_threading import THREAD_POOL

from ._base_result import BaseResult
from ._loading_request import LoadingRequest


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
