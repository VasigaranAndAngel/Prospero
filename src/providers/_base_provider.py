from abc import ABC, abstractmethod
from collections.abc import Collection

from ._base_result import BaseResult


class BaseProvider(ABC):
    @abstractmethod
    def __init__(self, name: str) -> None:
        self.name: str = name

    @abstractmethod
    def search(self, query: str) -> Collection[BaseResult]: ...
