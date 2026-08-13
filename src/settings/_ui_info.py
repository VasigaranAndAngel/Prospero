from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field as dc_field

from ._validators import TValidator


@dataclass(frozen=True)
class UIInfo:
    show: Callable[[], bool] = dc_field(default=lambda: True, kw_only=True)
    "A callable which will be called on update to determine if the widget should show or not."
    changed: list[Callable[[], None]] = dc_field(default_factory=list, kw_only=True)
    "List of callables to be called as soon as the value is changed."


@dataclass(frozen=True)
class CheckBox(UIInfo):
    default: bool


@dataclass(frozen=True)
class ComboBox(UIInfo):
    values: list[str]
    default_idx: int  # default index or default value?

    @property
    def default_value(self) -> str:
        return self.values[self.default_idx]


@dataclass(frozen=True)
class LineEdit(UIInfo):
    default: str
    validator: TValidator | None


@dataclass(frozen=True)
class SpinBox(UIInfo):
    default: int | float


@dataclass(frozen=True)
class ColorEdit(UIInfo):
    default: str


@dataclass(frozen=True)
class Category(UIInfo):
    compact: bool = False
