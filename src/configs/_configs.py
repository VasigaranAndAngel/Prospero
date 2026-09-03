from collections.abc import Callable, Generator
from pathlib import Path
from typing import Annotated, Any, ClassVar, override

import tomli_w
from pydantic import BaseModel, Field, PrivateAttr
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

from config_models import ChangeEvent, Observable
from constants import APPLICATION_NAME

from ._ui_info import Category, UIInfo
from .categories import AppearanceCategory, GeneralCategory, WindowGeometryCategory

CONFIG_FILE_PATH = Path.home() / ".config" / (APPLICATION_NAME.title() + ".toml")


class Configs(BaseSettings):
    _change_hooks: list[Callable[[ChangeEvent], None]] = PrivateAttr(default_factory=list)

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        toml_file=CONFIG_FILE_PATH,
        env_prefix=APPLICATION_NAME.upper() + "_",
        env_nested_delimiter="__",
        cli_parse_args=True,
        cli_ignore_unknown_args=True,
    )
    general: Annotated[GeneralCategory, Category()] = Field(
        default_factory=GeneralCategory,
        title="General",
        description="General Configurations.",
    )
    window_geometry: Annotated[WindowGeometryCategory, Category()] = Field(
        default_factory=WindowGeometryCategory,
        title="Window Geometry",
        description="Configurations related to geometry of the window.",
    )
    appearance: Annotated[AppearanceCategory, Category()] = Field(
        default_factory=AppearanceCategory,
        title="Appearance",
        description="Configurations related to Appearance.",
    )

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

    @override
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (TomlConfigSettingsSource(settings_cls),)

    def save_configs(self) -> None:
        _ = CONFIG_FILE_PATH.write_text(tomli_w.dumps(self.model_dump()))

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


CONFIGS = conf = Configs()
