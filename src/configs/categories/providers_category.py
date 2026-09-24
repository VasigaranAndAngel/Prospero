from typing import Annotated

from pydantic import Field

from config_models import BaseCategory, ConfigValue

from .._ui_info import Category, CheckBox


class AppProviderCategory(BaseCategory):
    show_recent_files: Annotated[ConfigValue[bool], CheckBox(False)] = Field(
        default=ConfigValue(value=False),
        title="Show Recent Files",
        description=(
            "Shows each app's Windows jump list recents as extra results. "
            "Approximation of Start Menu; off by default."
        ),
    )


class ProvidersCategory(BaseCategory):
    app_provider: Annotated[AppProviderCategory, Category()] = Field(
        default_factory=AppProviderCategory,
        title="App Provider",
        description="Configurations for the App Provider.",
    )