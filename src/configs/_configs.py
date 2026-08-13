from collections.abc import Generator
from pathlib import Path
from typing import Annotated, Any, ClassVar, override

import tomli_w
from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

from constants import APPLICATION_NAME

from ._ui_info import Category, UIInfo
from .categories import WindowGeometryCategory

CONFIG_FILE_PATH = Path.home() / ".config" / (APPLICATION_NAME.title() + ".toml")


class BaseCategory(BaseModel):
    pass
    # depends: "BaseCategory | BaseSetting | None" = None


class Configs(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        toml_file=CONFIG_FILE_PATH,
        env_prefix=APPLICATION_NAME.upper() + "_",
        env_nested_delimiter="__",
        cli_parse_args=True,
    )
    WindowGeometry: Annotated[WindowGeometryCategory, Category()] = Field(
        default_factory=WindowGeometryCategory,
        title="Window Geometry",
        description="Configurations related to geometry of the window.",
    )

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


CONFIGS = Configs()
