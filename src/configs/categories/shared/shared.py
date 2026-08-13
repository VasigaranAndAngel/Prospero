from typing import Annotated

from pydantic import BaseModel, Field

from ..._ui_info import SpinBox


class Point(BaseModel):
    x: Annotated[int, SpinBox(0)] = Field(default=0)
    y: Annotated[int, SpinBox(0)] = Field(default=0)
