from typing import Annotated, Literal

from pydantic import BaseModel, Field

from .._ui_info import Category, ComboBox
from .shared import Point


class PositionCategory(BaseModel):
    type: Annotated[
        Literal["relative", "absolute"], ComboBox(values=["relative", "absolute"], default_idx=0)
    ] = Field(
        default="relative",
        description="How the launcher window is positioned on screen.",
    )
    abs_value: Annotated[Point, Category(compact=True)] = Field(
        default_factory=Point,
        title="Absolute Position",
        description="Absolute values of the position of the launcher window.",
    )
    rel_value: Annotated[Point, Category(compact=True)] = Field(
        default_factory=Point,
        title="Relative Position",
        description="Relative values of the position of the launcher window.",
    )


class WindowGeometryCategory(BaseModel):
    Position: Annotated[PositionCategory, Category()] = Field(
        default_factory=PositionCategory, title="Window Position"
    )
