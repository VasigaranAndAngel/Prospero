from dataclasses import dataclass
from enum import Enum, auto
from typing import override


class ExecutionActions(Enum):
    Enter = auto()


@dataclass
class BaseResult:
    result: str
    score: int
    highlighted_indexes: list[int]
    description: str | None = None

    def highlighted(self, open_tag: str = "**", close_tag: str = "**") -> str:
        ih = set(self.highlighted_indexes)
        return "".join(
            [f"{open_tag}{c}{close_tag}" if i in ih else f"{c}" for i, c in enumerate(self.result)]
        )

    def execute(self, action: ExecutionActions) -> None:  # pyright: ignore[reportUnusedParameter]
        raise NotImplementedError

    @override
    def __hash__(self) -> int:
        return hash(self.result + (self.description or ""))
