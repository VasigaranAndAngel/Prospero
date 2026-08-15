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
ImmutablePrimitive = TypeVar("ImmutablePrimitive")


# region Observer
@dataclass(frozen=True)
class ChangeEvent:
    path: str  # e.g. "Position.type" — relative to the subscriber
    value: object
    "The new value"
    source: "ConfigValue"  # pyright: ignore[reportMissingTypeArgument]
    "The ConfigValue instance where the bubble emitted from."


class Observable(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(validate_assignment=True)

    _field_name: str = PrivateAttr(default="")
    _change_hooks: list[Callable[[ChangeEvent], None]] = PrivateAttr(default_factory=list)

    def subscribe(self, cb: Callable[[ChangeEvent], None]) -> None:
        self._change_hooks.append(cb)

    def _emit(self, event: ChangeEvent) -> None:
        for cb in self._change_hooks:
            cb(event)


class Container(Observable):
    """Wires child change events to bubble upward."""

    @override
    def model_post_init(self, __context: object) -> None:
        for field_name in type(self).model_fields:
            self._wire_child(field_name, getattr(self, field_name))  # pyright: ignore[reportAny]

    def _wire_child(self, field_name: str, child: object) -> None:
        if isinstance(child, Observable):
            child._field_name = field_name
            child.subscribe(self._bubbler(field_name))

    def _bubbler(self, field_name: str) -> Callable[[ChangeEvent], None]:
        def _bubble(event: ChangeEvent) -> None:
            path = f"{field_name}.{event.path}" if event.path else field_name
            self._emit(ChangeEvent(path=path, value=event.value, source=event.source))

        return _bubble

    @override
    def __setattr__(self, name: str, val: object) -> None:
        super().__setattr__(name, val)
        if name in type(self).model_fields:
            self._wire_child(name, val)  # re-wire on whole-field reassignment


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
            self._emit(ChangeEvent(path=self._field_name, value=value, source=self))

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
