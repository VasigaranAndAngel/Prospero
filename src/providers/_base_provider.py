from collections.abc import Collection

from ._base_result import BaseResult


class BaseProvider:
    def __init__(self, name: str) -> None:
        self.name: str = name

    def search(self, query: str) -> Collection[BaseResult]:  # pyright: ignore[reportUnusedParameter]
        raise NotImplementedError
