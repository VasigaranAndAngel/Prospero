from typing import Annotated, Literal

from pydantic import Field

from config_models import BaseCategory, ConfigValue

from .._ui_info import Category, CheckBox, ComboBox, SpinBox
from .shared import Point, PointF


class PositionCategory(BaseCategory):
    remember: Annotated[ConfigValue[bool], CheckBox(False)] = Field(
        default=ConfigValue(value=False),
        description="Whether remember last window position or not.",
    )
    type: Annotated[
        ConfigValue[Literal["relative", "absolute"]],
        ComboBox(values=["relative", "absolute"], default_idx=0),
    ] = Field(
        default=ConfigValue(value="relative"),
        description="How the launcher window is positioned on screen.",
    )
    abs_value: Annotated[Point, Category(compact=True)] = Field(
        default_factory=Point,
        title="Absolute Position",
        description="Absolute values of the position of the launcher window.",
    )
    rel_value: Annotated[PointF, Category(compact=True)] = Field(
        default_factory=PointF,
        title="Relative Position",
        description="Relative values of the position of the launcher window.",
    )

    def get_pos(self, screen_width: int, screen_height: int) -> tuple[int, int]:
        if self.type.value == "absolute":
            return self.abs_value.x.value, self.abs_value.y.value
        return int(self.rel_value.x.value * screen_width), int(
            self.rel_value.y.value * screen_height
        )

    def set_pos(self, screen_width: int, screen_height: int, x: int, y: int) -> None:
        # Update both absolute value and relative value
        self.abs_value.x.value = x
        self.abs_value.y.value = y
        self.rel_value.x.value = x / screen_width
        self.rel_value.y.value = y / screen_height


class SizePoint(BaseCategory):
    width: Annotated[ConfigValue[int], SpinBox(400)] = Field(default=ConfigValue(value=400))
    height: Annotated[ConfigValue[int], SpinBox(400)] = Field(default=ConfigValue(value=400))


class SizePointF(BaseCategory):
    width: Annotated[ConfigValue[float], SpinBox(0.35)] = Field(default=ConfigValue(value=0.35))
    height: Annotated[ConfigValue[float], SpinBox(0.5)] = Field(default=ConfigValue(value=0.5))


class SizeCategory(BaseCategory):
    type: Annotated[
        ConfigValue[Literal["relative", "absolute"]],
        ComboBox(values=["relative", "absolute"], default_idx=0),
    ] = Field(
        default=ConfigValue(value="relative"),
        description="How the launcher window is sized on screen.",
    )
    abs_value: Annotated[SizePoint, Category(compact=True)] = Field(
        default_factory=SizePoint,
        title="Absolute Size",
        description="Absolute values of the pixel size of the launcher window.",
    )
    rel_value: Annotated[SizePointF, Category(compact=True)] = Field(
        default_factory=SizePointF,
        title="Relative Size",
        description="Relative values of the size of the launcher window.",
    )

    def get_size(self, screen_width: int, screen_height: int) -> tuple[int, int]:
        if self.type.value == "absolute":
            return self.abs_value.width.value, self.abs_value.height.value
        return int(self.rel_value.width.value * screen_width), int(
            self.rel_value.height.value * screen_height
        )

    def set_size(self, screen_width: int, screen_height: int, x: int, y: int) -> None:
        # Update both absolute value and relative value
        self.abs_value.width.value = x
        self.abs_value.height.value = y
        self.rel_value.width.value = x / screen_width
        self.rel_value.height.value = y / screen_height


class WindowGeometryCategory(BaseCategory):
    position: Annotated[PositionCategory, Category()] = Field(
        default_factory=PositionCategory, title="Window Position"
    )
    size: Annotated[SizeCategory, Category()] = Field(
        default_factory=SizeCategory, title="Window Size"
    )
