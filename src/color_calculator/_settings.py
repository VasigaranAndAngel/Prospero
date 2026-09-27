"""
Settings for the color backend, kept in their own toml file.

Mirrors how ``theme`` reads a secondary file: parse the toml, validate it, and fall back to defaults
with a warning rather than failing. Deliberately does not enable pydantic settings' cli parsing,
because this module is importable before argument parsing runs and in modes like
``--schtasks-handler`` where sys.argv means something else entirely.
"""

import logging
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import ClassVar, override

from pydantic import Field, PrivateAttr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from tomli_w import dumps as toml_dumps

from config_models import BaseCategory, ChangeEvent, ConfigValue, Observable
from constants import APPLICATION_NAME

from ._named_colors import DEFAULT_NAMED_COLORS_FILE

logger = logging.getLogger(__name__)

COLOR_SETTINGS_FILE: Path = Path.home() / ".config" / APPLICATION_NAME.title() / "color.toml"
"Where the color backend's settings live."


class ColorCategory(BaseCategory):
    """Everything about how colors themselves are handled."""

    named_colors_file: ConfigValue[str] = Field(
        default=ConfigValue(value=str(DEFAULT_NAMED_COLORS_FILE))
    )
    "The toml file the named color table is read from."


class ColorSettings(BaseSettings):
    """Top level color settings. Sibling sections for calc, contrast and icc belong here."""

    _change_hooks: list[Callable[[ChangeEvent], None]] = PrivateAttr(default_factory=list)
    _source: Path | None = PrivateAttr(None)

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(extra="ignore")

    general: ColorCategory = Field(default_factory=ColorCategory)

    # Since BaseSettings doesn't allow multiple inheritance, model_post_init (to add field
    # names to children), subscribe, and _emit are declared again here.
    @override
    def model_post_init(self, context: object, /) -> None:
        for field_name in type(self).model_fields:
            field = getattr(self, field_name)  # pyright: ignore[reportAny]
            if isinstance(field, Observable):
                field._field_name = field_name  # pyright: ignore[reportPrivateUsage]
                # adding self._emit to each field as hooks which emits on every config
                # change.
                field.subscribe(self._emit)

    def subscribe(self, cb: Callable[[ChangeEvent], None]) -> None:
        self._change_hooks.append(cb)

    def _emit(self, event: ChangeEvent) -> None:
        for func in self._change_hooks:
            func(event)

    def source(self) -> Path | None:
        """The file these settings were read from, or None when defaults are in use."""
        return self._source

    def save(self, file: Path | None = None) -> None:
        """Writes the settings to their own file.

        Args:
            file (Path | None): Where to write. Defaults to the file they were read from, falling
                back to COLOR_SETTINGS_FILE when there was no such file.
        """
        target = file or self._source or COLOR_SETTINGS_FILE
        target.parent.mkdir(parents=True, exist_ok=True)
        _ = target.write_text(toml_dumps(self.model_dump()), encoding="utf-8")
        self._source = target


def load_color_settings(file: Path | None = None) -> ColorSettings:
    """Loads color settings from disk, falling back to defaults when unusable.

    Args:
        file (Path | None): The toml file to read. Defaults to COLOR_SETTINGS_FILE.

    Returns:
        ColorSettings: Validated settings, or defaults if the file is missing, unreadable
        or does not validate.
    """
    target = file or COLOR_SETTINGS_FILE
    if not target.is_file():
        logger.info("No color settings at '%s', using defaults.", target)
        return ColorSettings()

    try:
        data = tomllib.loads(target.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        logger.warning("Default color settings used, '%s' is unreadable: %s", target, e)
        return ColorSettings()

    try:
        settings = ColorSettings.model_validate(data)
    except ValidationError as e:
        logger.warning("Default color settings used, '%s' did not validate: %s", target, e)
        return ColorSettings()

    settings._source = target  # pyright: ignore[reportPrivateUsage]
    return settings


COLOR_SETTINGS: ColorSettings = load_color_settings()
"""The settings instance the backend reads. Call ``load_color_settings`` to re-read."""

__all__ = [
    "COLOR_SETTINGS",
    "COLOR_SETTINGS_FILE",
    "ColorCategory",
    "ColorSettings",
    "load_color_settings",
]
