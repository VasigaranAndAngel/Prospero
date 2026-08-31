from typing import Annotated

from pydantic import Field

from config_models import BaseCategory, ConfigValue

from ..._ui_info import SpinBox


class Point(BaseCategory):
    x: Annotated[ConfigValue[int], SpinBox(0)] = Field(
        default_factory=ConfigValue[int].get_default_factory(0)
    )
    y: Annotated[ConfigValue[int], SpinBox(0)] = Field(
        default_factory=ConfigValue[int].get_default_factory(0)
    )


class PointF(BaseCategory):
    x: Annotated[ConfigValue[float], SpinBox(0.5)] = Field(
        default_factory=ConfigValue[float].get_default_factory(0.5)
    )
    y: Annotated[ConfigValue[float], SpinBox(0.5)] = Field(
        default_factory=ConfigValue[float].get_default_factory(0.5)
    )
