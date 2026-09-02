from pathlib import Path
from typing import Annotated

from pydantic import Field
from PySide6.QtCore import Qt

from config_models import BaseCategory, ConfigValue

from .._ui_info import ComboBox, FilePath


class AppearanceCategory(BaseCategory):
    theme_mode: Annotated[ConfigValue[str], ComboBox(["System", "Dark", "Light"], 0)] = Field(
        default=ConfigValue(value="System"), title="Theme Mode"
    )
    dark_theme: Annotated[ConfigValue[str], FilePath()] = Field(
        default=ConfigValue(value="default-dark-theme.toml")
    )
    light_theme: Annotated[ConfigValue[str], FilePath()] = Field(
        default=ConfigValue(value="default-light-theme.toml")
    )

    def get_theme_file(self, system_mode: Qt.ColorScheme) -> Path:
        tm = self.theme_mode.value
        if tm == "System":
            if system_mode in {Qt.ColorScheme.Light, Qt.ColorScheme.Unknown}:
                return Path(self.light_theme.value)
            else:
                return Path(self.dark_theme.value)
        elif tm == "Dark":
            return Path(self.dark_theme.value)
        elif tm == "Light":
            return Path(self.light_theme.value)
        else:
            raise ValueError(
                f"Value of {self.theme_mode.get_path()} is {tm} unexpectedly. It should be one of 'System', 'Dark', 'Light'"
            )
