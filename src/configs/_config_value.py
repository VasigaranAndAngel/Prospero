"""
Contains the base class of values of configs. This is for, keep track of what's changing and
trigger hooks when the value is updated.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar, Generic, TypeVar, override

from pydantic import BaseModel, ConfigDict, PrivateAttr, model_serializer, model_validator

type _ImmutablePrimitive = tuple[_ImmutablePrimitive, ...]
# ImmutablePrimitive = TypeVar("ImmutablePrimitive", str, int, float, bool, None, _ImmutablePrimitive)
ImmutablePrimitive = TypeVar(
    "ImmutablePrimitive"
)  # TODO: should only support convertible to json/toml and immutable


# region Observer
@dataclass(frozen=True)
class ChangeEvent:
    path: str  # e.g. "window_geometry.position.type"
    value: object
    "The new value"
    source: "ConfigValue"  # pyright: ignore[reportMissingTypeArgument]
    "The ConfigValue instance where the bubble emitted from."


class Observable(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(validate_assignment=True)

    _field_name: str = PrivateAttr(default="")
    _parent: "Observable | None" = PrivateAttr(default=None)
    _change_hooks: list[Callable[[ChangeEvent], None]] = PrivateAttr(default_factory=list)

    def subscribe(self, cb: Callable[[ChangeEvent], None]) -> None:
        self._change_hooks.append(cb)

    def _emit(self, event: ChangeEvent) -> None:
        for cb in self._change_hooks:
            cb(event)
        if self._parent is not None:
            self._parent._emit(event)

    def get_path(self) -> str:
        if self._parent is not None:
            return self._parent.get_path() + "." + self._field_name
        return self._field_name


class Container(Observable):
    @override
    def model_post_init(self, __context: object) -> None:
        for field_name in type(self).model_fields:
            child = getattr(self, field_name)  # pyright: ignore[reportAny]
            if isinstance(child, Observable):
                child._field_name = field_name
                child._parent = self


# endregion


class ConfigValue(Observable, Generic[ImmutablePrimitive]):
    value: ImmutablePrimitive

    @model_serializer
    def _serialize(self) -> ImmutablePrimitive:
        return self.value

    @model_validator(mode="before")
    @classmethod
    def _validate(cls, val: str | dict[str, str]) -> dict[str, str]:
        if isinstance(val, dict):
            return val
        else:
            return {"value": val}

    @override
    def __setattr__(self, name: str, value: object, /) -> None:
        super().__setattr__(name, value)
        if name == "value":
            self._emit(ChangeEvent(path=self.get_path(), value=value, source=self))

    def add_change_hook(self, func: Callable[[object], None]) -> None:
        self._change_hooks.append(func)

    @staticmethod
    def get_default_factory(
        default: ImmutablePrimitive,
    ) -> Callable[[], "ConfigValue[ImmutablePrimitive]"]:
        "Use this for generate default_factory which gives different ConfigValue on each call."

        def factory() -> ConfigValue[ImmutablePrimitive]:
            return ConfigValue(value=default)

        return factory
