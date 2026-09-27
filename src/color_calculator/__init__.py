"""
The color backend: a ColorAide based color type, its settings, and its named colors.

Importing this package has no effect beyond reading the settings file. Call ``apply_settings`` to
push the configured values into ColorAide's state, which is deliberately separate so that importing
it can never quietly change how colors parse.

This package is Qt free. The one place Qt is needed, ``Color.to_qcolor``, imports PySide6 lazily for
that reason, and nothing here needs a QApplication.
"""

import logging
from pathlib import Path

from coloraide import Color as ColorAideColor

from ._color import Color
from ._named_colors import (
    DEFAULT_NAMED_COLORS_FILE,
    RESERVED_NAMES,
    apply_named_colors,
    default_named_colors,
    ensure_named_colors_file,
    load_named_colors,
    named_color_names,
    save_named_colors,
)
from ._settings import (
    COLOR_SETTINGS,
    COLOR_SETTINGS_FILE,
    ColorCategory,
    ColorSettings,
    load_color_settings,
)

logger = logging.getLogger(__name__)


def apply_settings(settings: ColorSettings | None = None) -> dict[str, str]:
    """Pushes settings into ColorAide and installs the named color table.

    Seeds the named color file with the css defaults when it does not exist yet, so a first run
    leaves an editable table behind rather than an empty one.

    Args:
        settings (ColorSettings | None): Settings to apply. Defaults to COLOR_SETTINGS.

    Returns:
        dict[str, str]: The name to hex table that ended up installed.
    """
    active = COLOR_SETTINGS if settings is None else settings

    file = Path(active.general.named_colors_file.value)
    names = ensure_named_colors_file(file)
    installed = apply_named_colors(names)
    logger.debug("Applied color settings from '%s', %d names installed.", file, installed)
    return names


__all__ = [
    "COLOR_SETTINGS",
    "COLOR_SETTINGS_FILE",
    "DEFAULT_NAMED_COLORS_FILE",
    "RESERVED_NAMES",
    "Color",
    "ColorAideColor",
    "ColorCategory",
    "ColorSettings",
    "apply_named_colors",
    "apply_settings",
    "default_named_colors",
    "ensure_named_colors_file",
    "load_color_settings",
    "load_named_colors",
    "named_color_names",
    "save_named_colors",
]
