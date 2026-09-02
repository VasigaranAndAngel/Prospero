import logging
import tomllib
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any, ClassVar, override

from pydantic import BaseModel, Field, PrivateAttr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from tomli_w import dumps as toml_dumps

from config_models import BaseCategory, ChangeEvent, ConfigValue, Observable
from configs import UIInfo, conf

logger = logging.getLogger(__name__)


class BaseFontConfigs(BaseCategory):
    font_face: ConfigValue[str | None] = Field(default=ConfigValue(value=None))
    font_size: ConfigValue[str | None] = Field(default=ConfigValue(value=None))
    font_color: ConfigValue[str | None] = Field(default=ConfigValue(value=None))


class CornerRadiusConfigs(BaseCategory):
    split_values: ConfigValue[bool] = Field(default=ConfigValue(value=False))
    single_value: ConfigValue[int] = Field(default=ConfigValue(value=15))
    top_left: ConfigValue[int] = Field(default=ConfigValue(value=15))
    top_right: ConfigValue[int] = Field(default=ConfigValue(value=15))
    bottom_right: ConfigValue[int] = Field(default=ConfigValue(value=15))
    bottom_left: ConfigValue[int] = Field(default=ConfigValue(value=15))


class BaseWidget(BaseCategory):
    background_color: ConfigValue[str | None] = Field(default=ConfigValue(value=None))
    font: BaseFontConfigs = Field(default_factory=BaseFontConfigs)
    corner_radius: CornerRadiusConfigs = Field(default_factory=CornerRadiusConfigs)


class Theme(BaseSettings):
    _change_hooks: list[Callable[[ChangeEvent], None]] = PrivateAttr(default_factory=list)
    _theme_file: Path | None = PrivateAttr(None)

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(extra="ignore")

    main_window: BaseWidget = Field(default_factory=BaseWidget)
    query_bar: BaseWidget = Field(default_factory=BaseWidget)
    results_area: BaseWidget = Field(default_factory=BaseWidget)
    result: BaseWidget = Field(default_factory=BaseWidget)

    @classmethod
    def load_theme(cls, system_theme: Qt.ColorScheme) -> "Theme":
        """Loads the theme from theme file as theme configurations.

        Returns an instance of Theme with values validated from correct theme file which is
        configured in configs. Returns Theme instance with default values if anything goes wrong.

        Args:
            system_theme (Qt.ColorScheme): The color scheme of system.

        returns (Theme): A Theme with selected theme file's values.
        """
        file = conf.appearance.get_theme_file(system_theme)
        if not file.exists():
            logger.warning(
                f"Default theme values returned instead values from '{file}' since that file isn't exists."
            )
            cls._theme_file = None
            return DEFAULT_THEME
        try:
            data = tomllib.loads(file.read_text())
            cls._theme_file = file
            return Theme.model_validate(data)
        except ValidationError as e:
            logger.warning(
                f"Default theme values returned since not able to validate from file {file}. Error: {e}"
            )
            cls._theme_file = None
            return DEFAULT_THEME

    def save_theme(self, file: Path) -> None:
        "Saves the theme parameters to a toml file."
        _ = file.write_text(toml_dumps(self.model_dump()))

    # Since BaseSettings doesn't allow multiple inheritance,
    # model_post_init (to add field names to children), subscribe, and _emit are declared again here.
    @override
    def model_post_init(self, context: object, /) -> None:
        for field_name in type(self).model_fields:
            field = getattr(self, field_name)
            if isinstance(field, Observable):
                field._field_name = field_name
                # adding this Configs._emit to each field of Configs as hooks which emits on every
                # config change.
                field.subscribe(self._emit)

    def subscribe(self, cb: Callable[[ChangeEvent], None]) -> None:
        self._change_hooks.append(cb)

    def _emit(self, event: ChangeEvent) -> None:
        for func in self._change_hooks:
            func(event)

    def walk(self) -> Generator[tuple[BaseModel | Any, UIInfo | None, tuple[str, ...]], Any, None]:
        return self._walk(self)

    @classmethod
    def _walk(
        cls, model: BaseModel, /, path: tuple[str, ...] = ()
    ) -> Generator[tuple[BaseModel | Any, UIInfo | None, tuple[str, ...]], Any, None]:
        for name, ins in model:
            field_path = path + (name,)
            field_info = type(model).model_fields[name]
            ui_info = next((x for x in field_info.metadata if isinstance(x, UIInfo)), None)

            yield ins, ui_info, field_path

            if isinstance(ins, BaseModel):
                yield from cls._walk(ins, field_path)


DEFAULT_THEME = Theme()
theme: Theme = DEFAULT_THEME


def update_theme() -> None:
    global theme
    cs = QApplication.styleHints().colorScheme()
    # TODO: creating new instance will ignore all the connections. so change the method of updating
    theme = Theme.load_theme(cs)


conf.appearance.theme_mode.subscribe(update_theme)
conf.appearance.dark_theme.subscribe(update_theme)
conf.appearance.light_theme.subscribe(update_theme)
_ = QApplication.styleHints().colorSchemeChanged.connect(update_theme)
