from dataclasses import dataclass, field
from enum import Enum, auto
from typing import override

from data_objects import IconLoadMethod, LoadMethod


def _get_default_icon() -> "IconLoadMethod":
    return IconLoadMethod(LoadMethod.default)


class ExecutionActions(Enum):
    Enter = auto()


@dataclass
class ResultAttributes:
    highlight_request: None = None
    "If need to highlight anything in query."
    suggestion_request: None = None
    "If anything is there to show as query suggestion."
    coloring_request: None = None
    "If need to colorized anything in query."
    close_after_enter: bool = False


@dataclass
class BaseResult:
    result: str
    score: int
    highlighted_indexes: list[int]
    description: str | None = None
    attributes: ResultAttributes = field(default_factory=ResultAttributes)
    icon_load_method: IconLoadMethod = field(default_factory=_get_default_icon)

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
