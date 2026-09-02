from typing import Annotated

from pydantic import Field

from config_models import BaseCategory, ConfigValue

from .._ui_info import Category, SpinBox


class ResultsBox(BaseCategory):
    maximum_results: Annotated[ConfigValue[int], SpinBox(5)] = Field(default=ConfigValue(value=5))


class GeneralCategory(BaseCategory):
    results_box: Annotated[ResultsBox, Category()] = Field(default_factory=ResultsBox)
