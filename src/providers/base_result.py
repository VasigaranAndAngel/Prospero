from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, override

# TODO: This module will be imported on cli mode too. which imports unwanted PySide6
from data_objects import IconLoadMethod, LoadMethod

if TYPE_CHECKING:
    from shared_ui_elements import BaseResultBoxWidget


class ExecutionAction(Enum):
    Trigger = auto()
    "The main trigger from KeyPress Enter or Mouse DoubleClick."
    Expand = auto()
    "More options trigger which tells the ResultBox to show more options/contexts."


@dataclass
class ResultAttributes:
    highlight_request: None = None
    "If need to highlight anything in query."
    suggestion_request: None | str = None
    "If anything is there to show as query suggestion."
    coloring_request: None = None
    "If need to colorized anything in query."
    close_after_enter: bool = False


@dataclass(kw_only=True)
class BaseResult(ABC):
    text: str
    score: int = 0
    highlighted_indexes: list[int] = field(default_factory=list)
    description: str | None = None
    attributes: ResultAttributes = field(default_factory=ResultAttributes)
    icon_load_method: IconLoadMethod = IconLoadMethod(LoadMethod.default)
    result_widget_factory: Callable[[str, "BaseResult"], "BaseResultBoxWidget"] | None = None

    def highlighted(self, open_tag: str = "**", close_tag: str = "**") -> str:
        ih = set(self.highlighted_indexes)
        return "".join(
            [f"{open_tag}{c}{close_tag}" if i in ih else f"{c}" for i, c in enumerate(self.text)]
        )

    @abstractmethod
    def execute(self, action: ExecutionAction) -> None:
        raise NotImplementedError

    @override
    def __hash__(self) -> int:
        return hash(self.text + (self.description or ""))


__all__ = ["ExecutionAction", "ResultAttributes", "BaseResult"]
